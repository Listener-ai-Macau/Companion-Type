"""Canonical absolute local paths, including Windows app-cache paths over MAX_PATH."""
from pathlib import Path
import os

def local_path(value):
    path=Path(value).resolve()
    text=str(path)
    if os.name=='nt' and not text.startswith('\\\\?\\'):
        text='\\\\?\\UNC\\'+text[2:] if text.startswith('\\\\') else '\\\\?\\'+text
        path=Path(text)
    return path
