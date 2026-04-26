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
import shutil
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root at import time
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
_RUNTIME_BUNDLE_ROOT = (
    Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT))
    if getattr(sys, "frozen", False)
    else _PROJECT_ROOT
)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    runtime_bundle_root: Path = field(default_factory=lambda: _RUNTIME_BUNDLE_ROOT)

    # Ford LLM Configuration (optional — only needed for LLM-enabled projects)
    ford_client_id: str | None = field(default_factory=lambda: os.environ.get("FORD_CLIENT_ID"))
    ford_client_secret: str | None = field(
        default_factory=lambda: os.environ.get("FORD_CLIENT_SECRET")
    )
    base_endpoint: str | None = field(
        default_factory=lambda: os.environ.get(
            "BASE_ENDPOINT", "https://api.pivpn.core.ford.com/fordllmapi/secret_data_api/v1"
        )
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
    )
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.0

    # Proxy Configuration
    https_proxy: str | None = field(default_factory=lambda: os.environ.get("HTTPS_PROXY"))

    # --- Matchup Optimizer Configuration ---
    variance_threshold_percent: float = field(
        default_factory=lambda: float(os.environ.get("VARIANCE_THRESHOLD_PERCENT", "40.0"))
    )
    cross_grade_margin_trigger: float = field(
        default_factory=lambda: float(os.environ.get("CROSS_GRADE_MARGIN_TRIGGER", "30.0"))
    )
    min_games_for_cross_grade: int = field(
        default_factory=lambda: int(os.environ.get("MIN_GAMES_FOR_CROSS_GRADE", "2"))
    )
    confidence_decay_factor: float = field(
        default_factory=lambda: float(os.environ.get("CONFIDENCE_DECAY_FACTOR", "0.9"))
    )

    # --- Derived Paths ---

    @property
    def data_dir(self) -> Path:
        """Directory for local data files."""
        if getattr(sys, "frozen", False):
            return self.app_data_root / "data"
        return self.project_root / "data"

    @property
    def assets_dir(self) -> Path:
        """Directory for static assets (logos, icons)."""
        if getattr(sys, "frozen", False):
            return self.runtime_bundle_root / "assets"
        return self.project_root / "assets"

    @property
    def runtime_data_dir(self) -> Path:
        """Read-only data directory bundled with the executable."""
        return self.runtime_bundle_root / "data"

    @property
    def app_data_root(self) -> Path:
        """Writable application data root for packaged runs."""
        if getattr(sys, "frozen", False):
            local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return local_app_data / "Basketball_Grader_Wizard"
        return self.project_root

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
        """Configure proxy settings for corporate network access.

        Sets HTTP_PROXY, HTTPS_PROXY, and NO_PROXY environment variables
        for outbound requests through Ford's corporate proxy.
        """
        if self.https_proxy:
            os.environ["HTTP_PROXY"] = self.https_proxy
            os.environ["HTTPS_PROXY"] = self.https_proxy
            os.environ["NO_PROXY"] = (
                "localhost,127.0.0.0/8,19.0.0.0/8,10.0.0.0/8,"
                "169.254.0.0/16,ford.com,googleapis.com,gcr.io,"
                "pkg.dev,gstatic.com,run.app"
            )

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.app_data_root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def ensure_seed_data(self) -> None:
        """Copy bundled seed data into the writable runtime directory when packaged."""
        if not getattr(sys, "frozen", False):
            return

        runtime_data_dir = self.runtime_data_dir
        if not runtime_data_dir.exists():
            return

        self.data_dir.mkdir(parents=True, exist_ok=True)

        for item in runtime_data_dir.iterdir():
            destination = self.data_dir / item.name
            if destination.exists():
                continue
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)

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

        # Check LLM settings if any LLM credential is set
        if self.ford_client_id or self.ford_client_secret:
            if not self.ford_client_id:
                warnings.append("FORD_CLIENT_ID not set but FORD_CLIENT_SECRET is present")
            if not self.ford_client_secret:
                warnings.append("FORD_CLIENT_SECRET not set but FORD_CLIENT_ID is present")

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
    settings.ensure_directories()
    settings.ensure_seed_data()
    return settings
