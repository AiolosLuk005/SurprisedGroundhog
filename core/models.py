from dataclasses import dataclass
from typing import Optional

CATEGORIES = {
    "TEXT": ["docx","doc","txt","md"],
    "DATA": ["xlsx","xlsm","xls","csv","xml"],
    "SLIDES": ["pptx","ppt"],
    "PDF": ["pdf"],
    "IMAGE": ["jpg","jpeg","gif","png","tif","tiff","bmp","svg","webp"],
    "AUDIO": ["mp3","wav","flac","m4a","aac","ogg"],
    "VIDEO": ["mp4","mkv","avi","mov","wmv","webm"]
}

@dataclass
class FileRow:
    full_path: str
    dir_path: str
    name: str
    ext: str
    category: str
    size_bytes: int
    mtime_iso: str
    sha256: Optional[str] = None
    keywords: Optional[str] = None
    previewable: bool = False
