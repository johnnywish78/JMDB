import logging
import sys
from pathlib import Path

def setup_logging(log_level: str = "info", logs_dir: str = ""):
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger("jmdb")
    root.setLevel(level)
    
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        root.addHandler(handler)
        
        if logs_dir:
            log_path = Path(logs_dir) / "jmdb.log"
            fh = logging.FileHandler(log_path)
            fh.setFormatter(handler.formatter)
            root.addHandler(fh)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jmdb.{name}")
