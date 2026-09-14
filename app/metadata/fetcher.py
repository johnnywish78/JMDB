import httpx
import re
from typing import Optional, Dict, Any
from app.logging import get_logger
from app.database.repositories.services import SettingsRepository

logger = get_logger("metadata.fetcher")

def extract_year_and_clean_title(filename: str) -> tuple[str, Optional[int]]:
    """Extract year and clean title from filename (e.g., 'Movie.Name.2020.1080p.mkv' -> 'Movie Name', 2020)"""
    # Remove extension and common tags
    clean = re.sub(r'\.(mkv|mp4|avi|mov|webm|srt|nfo)$', '', filename, flags=re.IGNORECASE)
    clean = re.sub(r'\.(1080p|720p|480p|2160p|4k|bluray|webrip|hdtv|x264|x265|hevc)', '', clean, flags=re.IGNORECASE)
    clean = clean.replace('.', ' ').replace('_', ' ').strip()
    
    # Try to find a 4-digit year
    year_match = re.search(r'\b(19|20)\d{2}\b', clean)
    year = int(year_match.group()) if year_match else None
    
    if year:
        clean = clean.replace(str(year), '').strip()
        # Remove trailing punctuation
        clean = re.sub(r'[\-\s]+$', '', clean)
        
    return clean, year

async def fetch_from_tmdb(title: str, year: Optional[int], media_type: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Fetch metadata from TMDB"""
    if not api_key:
        return None
    
    search_type = "movie" if media_type == "movie" else "tv"
    url = f"https://api.themoviedb.org/3/search/{search_type}"
    
    try:
        async with httpx.AsyncClient() as client:
            params = {"query": title, "api_key": api_key}
            if year:
                params["year" if search_type == "movie" else "first_air_date_year"] = str(year)
            
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    # Return the first match
                    return data["results"][0]
    except Exception as e:
        logger.error(f"TMDB fetch error: {e}")
    
    return None

async def fetch_details_from_tmdb(tmdb_id: int, media_type: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Fetch detailed metadata and artwork from TMDB"""
    if not api_key:
        return None
    
    search_type = "movie" if media_type == "movie" else "tv"
    url = f"https://api.themoviedb.org/3/{search_type}/{tmdb_id}"
    
    try:
        async with httpx.AsyncClient() as client:
            params = {"api_key": api_key, "append_to_response": "credits,videos"}
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"TMDB details fetch error: {e}")
    
    return None

async def enrich_media_metadata(media_item_id: int, filename: str, media_type: str, db_session) -> bool:
    """Main function to enrich a media item with real metadata"""
    from app.database.repositories.media import MediaRepository
    from app.database.repositories.services import SettingsRepository
    from app.database.models import ExternalID, Artwork, Genre, Person
    from datetime import datetime
    
    repo = MediaRepository(db_session)
    settings_repo = SettingsRepository(db_session)
    settings = settings_repo.get_all()
    
    api_key = settings.get("tmdb_api_key", "")
    if not api_key:
        logger.warning("No TMDB API key configured. Skipping metadata fetch.")
        return False
    
    title, year = extract_year_and_clean_title(filename)
    logger.info(f"Fetching metadata for: '{title}' ({year})")
    
    # 1. Search TMDB
    search_result = await fetch_from_tmdb(title, year, media_type, api_key)
    if not search_result:
        logger.warning(f"No TMDB results found for '{title}'")
        return False
    
    tmdb_id = search_result.get("id")
    
    # 2. Get detailed info
    details = await fetch_details_from_tmdb(tmdb_id, media_type, api_key)
    if not details:
        return False
    
    # 3. Update MediaItem
    item = repo.get_by_id(media_item_id)
    if not item:
        return False
    
    item.title = details.get("title") or details.get("name") or title
    item.original_title = details.get("original_title") or details.get("original_name")
    item.description = details.get("overview")
    item.year = year or (details.get("release_date") or details.get("first_air_date", ""))[:4]
    item.rating = details.get("vote_average")
    item.votes = details.get("vote_count", 0)
    item.runtime = details.get("runtime") or (details.get("episode_run_time", [0])[0] if details.get("episode_run_time") else 0)
    repo.update(item)
    
    # 4. Add External ID
    db_session.query(ExternalID).filter(ExternalID.media_item_id == media_item_id, ExternalID.provider == "tmdb").delete()
    ext_id = ExternalID(
        media_item_id=media_item_id,
        provider="tmdb",
        external_id=str(tmdb_id),
        url=f"https://www.themoviedb.org/{'movie' if media_type == 'movie' else 'tv'}/{tmdb_id}"
    )
    db_session.add(ext_id)
    
    # 5. Add Artwork
    base_img_url = "https://image.tmdb.org/t/p/w500"
    base_img_url_orig = "https://image.tmdb.org/t/p/original"
    
    if details.get("poster_path"):
        db_session.add(Artwork(
            media_item_id=media_item_id, type="poster", 
            url=f"{base_img_url}{details['poster_path']}", is_primary=True
        ))
    if details.get("backdrop_path"):
        db_session.add(Artwork(
            media_item_id=media_item_id, type="backdrop", 
            url=f"{base_img_url_orig}{details['backdrop_path']}", is_primary=False
        ))
    
    # 6. Add Genres
    for g in details.get("genres", []):
        genre = db_session.query(Genre).filter(Genre.name == g["name"]).first()
        if not genre:
            genre = Genre(name=g["name"])
            db_session.add(genre)
            db_session.flush()
        if genre not in item.genres:
            item.genres.append(genre)
    
    # 7. Add People (Cast)
    for cast in details.get("credits", {}).get("cast", [])[:10]: # Top 10 cast
        person = db_session.query(Person).filter(Person.name == cast["name"]).first()
        if not person:
            person = Person(name=cast["name"], profile_path=cast.get("profile_path"))
            db_session.add(person)
            db_session.flush()
        
        # Check if association already exists
        exists = db_session.execute(
            "SELECT 1 FROM media_people WHERE media_id = :mid AND person_id = :pid",
            {"mid": media_item_id, "pid": person.id}
        ).fetchone()
        
        if not exists:
            # We need to use the association table directly or via relationship
            # For simplicity in this script, we'll rely on the relationship if set up correctly, 
            # but let's do a direct insert to be safe with the secondary table
            from sqlalchemy import text
            db_session.execute(
                text("INSERT INTO media_people (media_id, person_id, role, character_name) VALUES (:mid, :pid, :role, :char)"),
                {"mid": media_item_id, "pid": person.id, "role": "actor", "char": cast.get("character")}
            )
    
    db_session.commit()
    logger.info(f"Successfully enriched metadata for '{item.title}'")
    return True
