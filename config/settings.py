"""
Settings — Environment Bootstrap Pattern (Tier A)

Immutable application settings loaded from environment variables.
Uses dataclass with frozen=True for thread safety and immutability.

Usage:
    from config import get_settings
    settings = get_settings()
    data_path = settings.data_dir / "my_file.parquet"
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root at import time
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    # Optional API / LLM Configuration
    api_client_id: str | None = field(default_factory=lambda: os.environ.get("API_CLIENT_ID"))
    api_client_secret: str | None = field(
        default_factory=lambda: os.environ.get("API_CLIENT_SECRET")
    )
    api_base_url: str | None = field(default_factory=lambda: os.environ.get("API_BASE_URL"))
    api_scope: str | None = field(default_factory=lambda: os.environ.get("API_SCOPE"))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "your-model-name"))
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.0

    # Proxy Configuration
    https_proxy: str | None = field(default_factory=lambda: os.environ.get("HTTPS_PROXY"))

    # --- Derived Paths ---

    @property
    def data_dir(self) -> Path:
        """Directory for local data files."""
        return self.project_root / "data"

    @property
    def assets_dir(self) -> Path:
        """Directory for static assets (logos, icons)."""
        return self.project_root / "assets"

    @property
    def config_dir(self) -> Path:
        """Directory for configuration files."""
        return self.project_root / "config"

    @property
    def logo_path(self) -> Path:
        """Path to the Specter logo image."""
        return self.assets_dir / "Specter_logo_black_on_white.png"

    @property
    def icon_path(self) -> Path:
        """Path to the app icon."""
        return self.assets_dir / "Rules.ico"

    # --- Methods ---

    def configure_proxy(self) -> None:
        """Configure proxy settings for outbound network access.

        Sets HTTP_PROXY, HTTPS_PROXY, and NO_PROXY environment variables
        when a proxy is configured in the environment.
        """
        if self.https_proxy:
            os.environ["HTTP_PROXY"] = self.https_proxy
            os.environ["HTTPS_PROXY"] = self.https_proxy
            os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Validate settings and return list of warnings.

        Returns:
            List of warning messages (empty if all settings valid).
        """
        warnings = []

        if not self.data_dir.exists():
            warnings.append(f"Data directory does not exist: {self.data_dir}")

        if not self.assets_dir.exists():
            warnings.append(f"Assets directory does not exist: {self.assets_dir}")

        # Check API settings if any credential is set
        if self.api_client_id or self.api_client_secret:
            if not self.api_client_id:
                warnings.append("API_CLIENT_ID not set but API_CLIENT_SECRET is present")
            if not self.api_client_secret:
                warnings.append("API_CLIENT_SECRET not set but API_CLIENT_ID is present")

        return warnings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings singleton.

    The settings object is created once and cached for the lifetime of
    the application. Proxy settings are configured automatically.

    Returns:
        Immutable Settings instance.
    """
    settings = Settings()
    settings.configure_proxy()
    return settings
