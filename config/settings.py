"""
Configuration management for Media Downloader App
"""

import json
from pathlib import Path

# Settings file path
SETTINGS_FILE = Path.home() / '.media_downloader_settings.json'

class Settings:
    """Manage application settings"""
    
    @staticmethod
    def load():
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'use_custom_location': False,
            'custom_location': str(Path.home() / 'Downloads' / 'Media'),
            'encode_vp9': True,
            'keep_original': False,
            'organize_by_platform': True,
            'metadata_option': 'none',
            'window_geometry': {
                'x': None,  # Will be set to top-right corner by default
                'y': None,
                'width': 500,
                'height': 600
            }
        }
    
    @staticmethod
    def save(settings):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")