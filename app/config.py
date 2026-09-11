from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATABASE_DIR = DATA_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "jmdb.db"

HOST = "127.0.0.1"
DEFAULT_PORT = 18932

DATABASE_DIR.mkdir(parents=True, exist_ok=True)
