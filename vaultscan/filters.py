import os
from typing import Optional, List

class FilterChain:
    MANDATORY_EXCLUDE_PATHS = {
        "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"
    }
    MANDATORY_EXCLUDE_EXTS = {
        ".lock", ".min.js", ".map", ".svg", ".png", ".wasm", ".bin"
    }
    FAKE_VALUES_DENYLIST = {
        "AKIAIOSFODNN7EXAMPLE",
        "ghp_000000000000000000000000000000000000"
    }
    
    def __init__(self, exclude_paths: Optional[List[str]] = None, exclude_exts: Optional[List[str]] = None):
        self.exclude_paths = set(exclude_paths or []) | self.MANDATORY_EXCLUDE_PATHS
        self.exclude_exts = set(exclude_exts or []) | self.MANDATORY_EXCLUDE_EXTS
        
    def should_scan_file(self, file_path: str) -> bool:
        """
        Returns True if the file should be scanned, False if it is excluded
        by path or extension.
        """
        # Check extensions
        file_lower = file_path.lower()
        for ext in self.exclude_exts:
            if file_lower.endswith(ext):
                return False

        # Check paths
        # Normalize slashes
        normalized_path = file_path.replace('\\', '/')
        parts = set(normalized_path.split('/'))
        
        # If any part of the path is in the exclude list, don't scan
        if self.exclude_paths.intersection(parts):
            return False
            
        return True
        
    def is_fake_value(self, value: str) -> bool:
        """
        Returns True if the value is a known fake credential from the denylist.
        """
        return value in self.FAKE_VALUES_DENYLIST
