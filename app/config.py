from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "JMDB"
    app_version: str = "1.0.0"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8765
    data_dir: str = str(Path(__file__).parent.parent / "data")
    db_path: str = ""
    log_level: str = "info"
    
    # Metadata API Keys
    tmdb_api_key: str = ""
    omdb_api_key: str = ""
    
    # Player Settings
    mpv_path: str = ""
    default_player: str = "mpv"
    
    # Browser Settings
    browser_homepage: str = "https://www.google.com"

    class Config:
        env_prefix = "JMDB_"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        base = Path(self.data_dir)
        base.mkdir(parents=True, exist_ok=True)
        
        if not self.db_path:
            self.db_path = str(base / "database" / "jmdb.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        for d in ["cache", "artwork", "backups", "logs"]:
            (base / d).mkdir(parents=True, exist_ok=True)

def get_settings() -> Settings:
    return Settings()
