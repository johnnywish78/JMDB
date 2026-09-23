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


def select_best_trailer(videos: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Select the most useful YouTube trailer from TMDB's videos response.

    We intentionally require type=Trailer so JMDB does not accidentally
    display interviews, clips, teasers, or unrelated videos as the trailer.
    """
    results = (videos or {}).get("results") or []

    candidates = [
        video
        for video in results
        if str(video.get("site") or "").lower() == "youtube"
        and video.get("key")
        and str(video.get("type") or "").lower() == "trailer"
    ]

    if not candidates:
        return None

    def score(video: Dict[str, Any]) -> int:
        name = str(video.get("name") or "").lower()

        score_value = 0

        if video.get("official") is True:
            score_value += 100

        if "official trailer" in name:
            score_value += 30
        elif "trailer" in name:
            score_value += 10

        if str(video.get("language") or "").lower() == "en":
            score_value += 5

        return score_value

    return max(candidates, key=score)


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

        if season is None or episode is None:
            logger.warning(
                f"Episode metadata missing season/episode numbers: "
                f"media_id={media_item_id}, parsed={parsed}"
            )
            return False

        episode_details = await fetch_episode_details(
            tmdb_id,
            season,
            episode,
            api_key,
        )

        if not episode_details:
            logger.warning(
                f"Episode metadata fetch failed; preserving existing "
                f"metadata: media_id={media_item_id}, "
                f"tmdb_id={tmdb_id}, S{season:02d}E{episode:02d}"
            )
            return False

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

    # --------------------------------------------------------
    # Trailer
    # --------------------------------------------------------
    #
    # Prefer episode-level videos when available. For movies/TV,
    # use the main details response.
    if effective_type == "episode":
        trailer_source = episode_details.get("videos")
    else:
        trailer_source = details.get("videos")

    trailer = select_best_trailer(trailer_source)

    # Refreshing metadata must also clear a previously stored trailer
    # if TMDB no longer returns one.
    item.trailer_key = None
    item.trailer_name = None
    item.trailer_site = None
    item.trailer_type = None
    item.trailer_official = False

    if trailer:
        item.trailer_key = str(trailer.get("key"))
        item.trailer_name = trailer.get("name")
        item.trailer_site = trailer.get("site")
        item.trailer_type = trailer.get("type")
        item.trailer_official = bool(trailer.get("official"))

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

    # Episodes have their own IMDb ID.  The series-level
    # `details.external_ids` points to the parent TV series, while
    # `episode_details.external_ids` contains the actual episode ID.
    if effective_type == "episode":
        external_id_source = episode_details
    else:
        external_id_source = details
    external_ids = external_id_source.get("external_ids") or {}
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

    credits = details.get("credits", {}) or {}

    cast_source = credits.get("cast", []) or []
    crew_source = credits.get("crew", []) or []

    if episode_details:
        episode_credits = episode_details.get("credits", {}) or {}
        episode_cast = episode_credits.get("cast", []) or []

        if episode_cast:
            cast_source = episode_cast

    # Keep the UI useful without exploding the number of people
    # attached to a single title.
    cast_entries = cast_source[:10]
    crew_entries = crew_source[:10]

    people_entries = []

    for cast in cast_entries:
        people_entries.append({
            "person": cast,
            "role": "actor",
            "character_name": cast.get("character"),
        })

    for crew in crew_entries:
        people_entries.append({
            "person": crew,
            "role": (
                crew.get("job")
                or crew.get("department")
                or "crew"
            ),
            "character_name": None,
        })

    for entry in people_entries:
        person_data = entry["person"]
        name = person_data.get("name")

        if not name:
            continue

        tmdb_person_id = person_data.get("id")

        person = None

        if tmdb_person_id:
            person = (
                db_session.query(Person)
                .filter(Person.tmdb_id == tmdb_person_id)
                .first()
            )

        if not person:
            person = (
                db_session.query(Person)
                .filter(Person.name == name)
                .first()
            )

        if not person:
            person = Person(name=name)

        # Refresh the external metadata whenever TMDB gives us
        # a stronger value. Existing biography/details remain intact.
        person.name = name

        if tmdb_person_id:
            person.tmdb_id = tmdb_person_id

        if person_data.get("profile_path"):
            person.profile_path = person_data["profile_path"]

        if person_data.get("known_for_department"):
            person.known_for_department = (
                person_data["known_for_department"]
            )

        if person_data.get("popularity") is not None:
            person.popularity = person_data["popularity"]

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
                "role": entry["role"],
                "character_name": entry["character_name"],
            },
        )

    db_session.commit()

    logger.info(
        f"Metadata enriched successfully: media_id={media_item_id}"
    )

    return True
