"""
Real media file scanner.
Recursively scans directories for video/audio files.
"""
from pathlib import Path
import re
from typing import List, Dict, Callable, Optional
from app.logging import get_logger

logger = get_logger("scanner")

# Supported file extensions
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", 
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".vob"
}

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".aac", ".m4a", ".ogg", ".wav", ".wma", ".opus"
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp"
}

SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS

def get_media_type(extension: str) -> str:
    """Determine media type from file extension."""
    ext = extension.lower()
    if ext in VIDEO_EXTENSIONS:
        return "movie"
    elif ext in AUDIO_EXTENSIONS:
        return "music"
    elif ext in IMAGE_EXTENSIONS:
        return "image"
    return "other"

def classify_video_file(filename: str, full_path: str = "") -> str:
    """
    Classify a video file as a movie or TV show.

    Only explicit episode markers are treated as TV shows:
      - S01E01, S1E2, etc.
      - 1x01, 01x02, etc.

    Other video files remain movies.
    """
    name = Path(filename).stem

    # S01E01, S1E2, S02E08, etc.
    if re.search(
        r"(?i)(?:^|[.\\s_-])s\d{1,2}e\d{1,3}(?:$|[.\\s_-])",
        name,
    ):
        return "tv_show"

    # 1x01, 01x02, etc.
    if re.search(
        r"(?i)(?:^|[.\\s_-])\d{1,2}x\d{1,3}(?:$|[.\\s_-])",
        name,
    ):
        return "tv_show"

    return "movie"


def scan_directory(
    directory: str,
    progress_callback: Optional[Callable] = None,
    cancel_callback: Optional[Callable] = None
) -> List[Dict]:
    """
    Recursively scan directory for media files.
    
    Args:
        directory: Path to scan
        progress_callback: Callback(processed, total, current_file)
        cancel_callback: Callback() -> bool (return True to cancel)
    
    Returns:
        List of file info dicts
    """
    results = []
    path = Path(directory)
    
    if not path.exists():
        logger.error(f"Directory does not exist: {directory}")
        return results
    
    if not path.is_dir():
        logger.error(f"Path is not a directory: {directory}")
        return results
    
    # Collect all files first for progress tracking
    logger.info(f"Starting scan of {directory}...")
    all_files = list(path.rglob("*"))
    total_files = sum(1 for f in all_files if f.is_file())
    
    processed = 0
    errors = 0
    
    for file_path in all_files:
        # Check for cancellation
        if cancel_callback and cancel_callback():
            logger.info("Scan cancelled by user")
            break
        
        if not file_path.is_file():
            continue
        
        processed += 1
        
        # Report progress
        if progress_callback:
            progress_callback(processed, total_files, str(file_path))
        
        # Check if supported
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        
        try:
            stat = file_path.stat()
            file_info = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_size": stat.st_size,
                "file_format": file_path.suffix.lstrip(".").upper(),
                "media_type": (
                    classify_video_file(file_path.name, str(file_path))
                    if file_path.suffix.lower() in VIDEO_EXTENSIONS
                    else get_media_type(file_path.suffix)
                ),
                "modified_at": datetime.fromtimestamp(stat.st_mtime)
            }
            results.append(file_info)
            
        except Exception as e:
            errors += 1
            logger.error(f"Error processing {file_path}: {e}")
    
    logger.info(f"Scan complete: {len(results)} media files found, {errors} errors")
    return results

from datetime import datetime
