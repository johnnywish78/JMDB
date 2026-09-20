import re
import httpx
from typing import Optional, Dict, Any

from sqlalchemy import text

from app.logging import get_logger
from app.database.repositories.services import SettingsRepository

logger = get_logger("metadata.fetcher")


async def _tmdb_get(
    endpoint: str,
    api_key: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:

    if not api_key:
        return None

    request_params = dict(params or {})
    request_params["api_key"] = api_key

    try:
        import os

        proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("http_proxy")
        )

        client_kwargs = {
            "timeout": 15.0,
            "trust_env": False,
        }

        if proxy:
            client_kwargs["proxy"] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(
                f"https://api.themoviedb.org/3/{endpoint.lstrip('/')}",
                params=request_params,
            )

        if response.status_code != 200:
            logger.warning(
                f"TMDB request failed: {response.status_code} {endpoint}"
            )
            return None

        return response.json()

    except Exception as e:
        logger.error(f"TMDB request error for {endpoint}: {e}")
        return None


def extract_year_and_clean_title(filename: str):
    """Compatibility wrapper around the real scanner parser."""
    from app.scanner.scanner import parse_media_filename

    parsed = parse_media_filename(filename)
    return parsed["title"], parsed.get("year")


async def fetch_from_tmdb(
    title: str,
    year: Optional[int],
    media_type: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:

    search_type = "movie" if media_type == "movie" else "tv"

    candidates = [title.strip()]

    stripped_title = re.sub(
        r"^\d{1,2}\s+",
        "",
        title.strip(),
    ).strip()

    if stripped_title and stripped_title != candidates[0]:
        candidates.append(stripped_title)

    for candidate in candidates:
        params = {"query": candidate}

        if year:
            if search_type == "movie":
                params["year"] = str(year)
            else:
                params["first_air_date_year"] = str(year)

        data = await _tmdb_get(
            f"search/{search_type}",
            api_key,
            params,
        )

        results = data.get("results", []) if data else []

        if results:
            return results[0]

    return None


async def fetch_details_from_tmdb(
    tmdb_id: int,
    media_type: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:

    search_type = "movie" if media_type == "movie" else "tv"

    return await _tmdb_get(
        f"{search_type}/{tmdb_id}",
        api_key,
        {
            "append_to_response": "credits,videos,external_ids"
        },
    )


async def fetch_episode_details(
    tmdb_id: int,
    season_number: int,
    episode_number: int,
    api_key: str,
) -> Optional[Dict[str, Any]]:

    return await _tmdb_get(
        f"tv/{tmdb_id}/season/{season_number}/episode/{episode_number}",
        api_key,
        {
            "append_to_response": "credits,videos,external_ids"
        },
    )


async def enrich_media_metadata(
    media_item_id: int,
    filename: str,
    media_type: str,
    db_session,
    parsed: Optional[Dict[str, Any]] = None,
) -> bool:

    from app.database.repositories.media import MediaRepository
    from app.database.models import (
        ExternalID,
        Artwork,
        Genre,
        Person,
    )

    repo = MediaRepository(db_session)
    settings = SettingsRepository(db_session).get_all()

    api_key = str(settings.get("tmdb_api_key", "") or "").strip()

    if not api_key:
        logger.info(
            "TMDB API key not configured; metadata fetch skipped."
        )
        return False

    item = repo.get_by_id(media_item_id)

    if not item:
        return False

    if parsed is None:
        from app.scanner.scanner import parse_media_filename
        parsed = parse_media_filename(filename)

    effective_type = parsed.get("media_type") or media_type
    title = parsed.get("title") or item.title
    year = parsed.get("year")

    logger.info(
        f"Fetching TMDB metadata: '{title}' [{effective_type}]"
    )

    search_media_type = (
        "movie" if effective_type == "movie" else "tv"
    )

    search_result = await fetch_from_tmdb(
        title,
        year,
        search_media_type,
        api_key,
    )

    if not search_result:
        logger.warning(
            f"No TMDB result found for '{title}'"
        )
        return False

    tmdb_id = search_result.get("id")

    if not tmdb_id:
        return False

    details = await fetch_details_from_tmdb(
        tmdb_id,
        search_media_type,
        api_key,
    )

    if not details:
        return False

    episode_details = None

    if effective_type == "episode":
        season = parsed.get("season_number")
        episode = parsed.get("episode_number")

        if season is not None and episode is not None:
            episode_details = await fetch_episode_details(
                tmdb_id,
                season,
                episode,
                api_key,
            )

    # --------------------------------------------------------
    # MediaItem
    # --------------------------------------------------------

    item.title = (
        details.get("title")
        or details.get("name")
        or title
    )

    item.original_title = (
        details.get("original_title")
        or details.get("original_name")
    )

    item.description = details.get("overview")

    date_value = (
        details.get("release_date")
        or details.get("first_air_date")
        or ""
    )

    if isinstance(date_value, str) and date_value[:4].isdigit():
        item.year = int(date_value[:4])

    if date_value:
        item.release_date = date_value

    item.rating = details.get("vote_average")
    item.votes = details.get("vote_count", 0)

    runtime = details.get("runtime")

    if not runtime:
        runtimes = details.get("episode_run_time") or []
        runtime = runtimes[0] if runtimes else None

    item.runtime = runtime

    # Keep the database media type aligned with the parsed media type.
    if effective_type == "episode":
        from app.database.models import MediaType

        item.media_type = MediaType.EPISODE
        item.season_number = parsed.get("season_number")
        item.episode_number = parsed.get("episode_number")

        if episode_details:
            item.episode_title = (
                episode_details.get("name")
                or item.episode_title
            )

            if episode_details.get("overview"):
                item.description = episode_details["overview"]

            if episode_details.get("vote_average") is not None:
                item.rating = episode_details["vote_average"]

            if episode_details.get("vote_count") is not None:
                item.votes = episode_details["vote_count"]

            if episode_details.get("runtime"):
                item.runtime = episode_details["runtime"]

            if episode_details.get("air_date"):
                item.release_date = episode_details["air_date"]

    repo.update(item)

    # --------------------------------------------------------
    # External IDs
    # --------------------------------------------------------

    db_session.query(ExternalID).filter(
        ExternalID.media_item_id == media_item_id,
        ExternalID.provider.in_(["tmdb", "imdb"]),
    ).delete(synchronize_session=False)

    db_session.add(
        ExternalID(
            media_item_id=media_item_id,
            provider="tmdb",
            external_id=str(tmdb_id),
            url=(
                f"https://www.themoviedb.org/"
                f"{search_media_type}/{tmdb_id}"
            ),
        )
    )

    external_ids = details.get("external_ids") or {}
    imdb_id = external_ids.get("imdb_id")

    if imdb_id:
        db_session.add(
            ExternalID(
                media_item_id=media_item_id,
                provider="imdb",
                external_id=imdb_id,
                url=f"https://www.imdb.com/title/{imdb_id}/",
            )
        )

    # --------------------------------------------------------
    # Artwork
    # --------------------------------------------------------

    db_session.query(Artwork).filter(
        Artwork.media_item_id == media_item_id
    ).delete(synchronize_session=False)

    poster_path = details.get("poster_path")
    backdrop_path = details.get("backdrop_path")

    if poster_path:
        db_session.add(
            Artwork(
                media_item_id=media_item_id,
                type="poster",
                url=f"https://image.tmdb.org/t/p/w500{poster_path}",
                is_primary=True,
            )
        )

    if backdrop_path:
        db_session.add(
            Artwork(
                media_item_id=media_item_id,
                type="backdrop",
                url=f"https://image.tmdb.org/t/p/original{backdrop_path}",
                is_primary=False,
            )
        )

    # --------------------------------------------------------
    # Genres
    # --------------------------------------------------------

    item.genres.clear()

    for genre_data in details.get("genres", []):
        name = genre_data.get("name")

        if not name:
            continue

        genre = (
            db_session.query(Genre)
            .filter(Genre.name == name)
            .first()
        )

        if not genre:
            genre = Genre(name=name)
            db_session.add(genre)
            db_session.flush()

        if genre not in item.genres:
            item.genres.append(genre)

    # --------------------------------------------------------
    # Cast
    # --------------------------------------------------------

    db_session.execute(
        text(
            "DELETE FROM media_people "
            "WHERE media_id = :media_id"
        ),
        {"media_id": media_item_id},
    )

    cast_source = (
        details.get("credits", {}).get("cast", [])
    )

    if episode_details:
        episode_cast = (
            episode_details.get("credits", {}).get("cast", [])
        )

        if episode_cast:
            cast_source = episode_cast

    for cast in cast_source[:10]:
        name = cast.get("name")

        if not name:
            continue

        person = (
            db_session.query(Person)
            .filter(Person.name == name)
            .first()
        )

        if not person:
            person = Person(
                name=name,
                profile_path=cast.get("profile_path"),
            )
            db_session.add(person)
            db_session.flush()

        db_session.execute(
            text(
                """
                INSERT INTO media_people
                    (id, media_id, person_id, role, character_name)
                VALUES
                    (
                        COALESCE((SELECT MAX(id) + 1 FROM media_people), 1),
                        :mid,
                        :pid,
                        :role,
                        :character_name
                    )
                """
            ),
            {
                "mid": media_item_id,
                "pid": person.id,
                "role": "actor",
                "character_name": cast.get("character"),
            },
        )

    db_session.commit()

    logger.info(
        f"Metadata enriched successfully: media_id={media_item_id}"
    )

    return True
