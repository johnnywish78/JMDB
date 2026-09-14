"""
TMDB (The Movie Database) metadata provider.
Requires API key from https://www.themoviedb.org/settings/api
"""
import httpx
from typing import List, Dict, Optional
from app.logging import get_logger

logger = get_logger("metadata.tmdb")

class TMDBProvider:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.client = httpx.Client(timeout=10)
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def search(self, query: str, media_type: str = "movie") -> List[Dict]:
        """Search for media on TMDB."""
        if not self.api_key:
            return []
        
        try:
            response = self.client.get(
                f"{self.base_url}/search/{media_type}",
                params={
                    "query": query,
                    "api_key": self.api_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                logger.error(f"TMDB search failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"TMDB search error: {e}")
            return []
    
    def get_details(self, external_id: str, media_type: str = "movie") -> Optional[Dict]:
        """Get detailed information for a media item."""
        if not self.api_key:
            return None
        
        try:
            response = self.client.get(
                f"{self.base_url}/{media_type}/{external_id}",
                params={
                    "api_key": self.api_key,
                    "append_to_response": "credits,videos"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"TMDB details failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"TMDB details error: {e}")
            return None
    
    def get_artwork(self, external_id: str, media_type: str = "movie") -> List[Dict]:
        """Get artwork (posters, backdrops) for a media item."""
        details = self.get_details(external_id, media_type)
        if not details:
            return []
        
        artwork = []
        base_url = "https://image.tmdb.org/t/p"
        
        # Poster
        if details.get("poster_path"):
            artwork.append({
                "type": "poster",
                "url": f"{base_url}/w500{details['poster_path']}",
                "is_primary": True
            })
        
        # Backdrop
        if details.get("backdrop_path"):
            artwork.append({
                "type": "backdrop",
                "url": f"{base_url}/original{details['backdrop_path']}",
                "is_primary": False
            })
        
        return artwork
    
    def get_external_ids(self, external_id: str, media_type: str = "movie") -> Dict:
        """Get external IDs (IMDb, etc.) for a media item."""
        if not self.api_key:
            return {}
        
        try:
            response = self.client.get(
                f"{self.base_url}/{media_type}/{external_id}/external_ids",
                params={"api_key": self.api_key}
            )
            
            if response.status_code == 200:
                return response.json()
            return {}
            
        except Exception as e:
            logger.error(f"TMDB external IDs error: {e}")
            return {}
    
    def health_check(self) -> bool:
        """Check if TMDB API is accessible."""
        if not self.api_key:
            return False
        
        try:
            response = self.client.get(
                f"{self.base_url}/configuration",
                params={"api_key": self.api_key}
            )
            return response.status_code == 200
        except Exception:
            return False
