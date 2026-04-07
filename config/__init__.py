"""
Config package — Application settings and environment bootstrap.

Usage:
    from config import Settings, get_settings

    settings = get_settings()
    print(settings.data_dir)
"""

from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
