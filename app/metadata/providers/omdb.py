"""
OMDb (Open Movie Database) metadata provider.
Requires API key from http://www.omdbapi.com/apikey.aspx
"""
import httpx
from typing import List, Dict, Optional
from app.logging import get_logger

logger = get_logger("metadata.omdb")

class OMDbProvider:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "http://www.omdbapi.com/"
        self.client = httpx.Client(timeout=10)
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def search(self, query: str, media_type: str = "movie") -> List[Dict]:
        """Search for media on OMDb."""
        if not self.api_key:
            return []
        
        try:
            response = self.client.get(
                self.base_url,
                params={
                    "s": query,
                    "apikey": self.api_key,
                    "type": media_type
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("Response") == "True":
                    return data.get("Search", [])
            return []
                
        except Exception as e:
            logger.error(f"OMDb search error: {e}")
            return []
    
    def get_details(self, external_id: str) -> Optional[Dict]:
        """Get detailed information by IMDb ID."""
        if not self.api_key:
            return None
        
        try:
            response = self.client.get(
                self.base_url,
                params={
                    "i": external_id,
                    "apikey": self.api_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("Response") == "True":
                    return data
            return None
                
        except Exception as e:
            logger.error(f"OMDb details error: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check if OMDb API is accessible."""
        return bool(self.api_key)
