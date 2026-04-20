"""Application settings and path configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _parse_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse a comma-separated environment variable into a tuple."""
    raw_value = os.getenv(name, "")
    if not raw_value.strip():
        return default
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration for the backend application."""

    root_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    app_name: str = "Safety Helmet Detection API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
    )
    image_size: int = field(default_factory=lambda: int(os.getenv("IMAGE_SIZE", "640")))
    update_required_count: int = field(
        default_factory=lambda: int(os.getenv("UPDATE_REQUIRED_COUNT", "100"))
    )
    stream_window_size: int = field(
        default_factory=lambda: int(os.getenv("STREAM_WINDOW_SIZE", "30"))
    )
    stream_event_threshold: int = field(
        default_factory=lambda: int(os.getenv("STREAM_EVENT_THRESHOLD", "20"))
    )
    target_stream_fps: float = field(
        default_factory=lambda: float(os.getenv("TARGET_STREAM_FPS", "10"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: _parse_csv_env(
            "CORS_ORIGINS",
            (
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ),
        )
    )
    allowed_image_content_types: tuple[str, ...] = ("image/jpeg", "image/png")
    allowed_model_suffixes: tuple[str, ...] = (".pt", ".onnx", ".engine")

    # ── Person-first pipeline ─────────────────────────────────────────────────
    person_first_enabled: bool = field(
        default_factory=lambda: os.getenv("PERSON_FIRST_ENABLED", "false").lower() == "true"
    )
    person_confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("PERSON_CONFIDENCE_THRESHOLD", "0.40"))
    )
    person_detection_interval: int = field(
        default_factory=lambda: int(os.getenv("PERSON_DETECTION_INTERVAL", "1"))
    )
    helmet_recheck_interval: int = field(
        default_factory=lambda: int(os.getenv("HELMET_RECHECK_INTERVAL", "5"))
    )
    person_crop_margin: float = field(
        default_factory=lambda: float(os.getenv("PERSON_CROP_MARGIN", "0.05"))
    )
    upper_body_crop_ratio: float = field(
        default_factory=lambda: float(os.getenv("UPPER_BODY_CROP_RATIO", "0.60"))
    )

    @property
    def data_dir(self) -> Path:
        """Return the top-level data directory."""
        return self.root_dir / "data"

    @property
    def models_dir(self) -> Path:
        """Return the model weights directory."""
        return self.root_dir / "models"

    @property
    def history_dir(self) -> Path:
        """Return the persisted history directory."""
        return self.data_dir / "history"

    @property
    def history_global_dir(self) -> Path:
        """Return the directory for full-frame history images."""
        return self.history_dir / "global"

    @property
    def history_crops_dir(self) -> Path:
        """Return the directory for cropped violation images."""
        return self.history_dir / "crops"

    @property
    def history_jsonl(self) -> Path:
        """Return the JSONL file that stores history events."""
        return self.history_dir / "history.jsonl"

    @property
    def videos_dir(self) -> Path:
        """Return the directory for uploaded videos."""
        return self.data_dir / "videos"

    @property
    def temp_videos_dir(self) -> Path:
        """Return the directory for temporary uploaded videos."""
        return self.data_dir / "temp_videos"

    @property
    def update_pool_dir(self) -> Path:
        """Return the update-pool root directory."""
        return self.data_dir / "update_pool"

    @property
    def update_pool_images_dir(self) -> Path:
        """Return the directory for accepted update images."""
        return self.update_pool_dir / "images"

    @property
    def update_pool_labels_dir(self) -> Path:
        """Return the directory for accepted update labels."""
        return self.update_pool_dir / "labels"

    @property
    def update_pool_meta_path(self) -> Path:
        """Return the JSONL file storing update-pool review metadata."""
        return self.update_pool_dir / "accepted.jsonl"

    @property
    def gemini_api_key(self) -> str:
        """Return the Gemini API key from environment."""
        return os.getenv("GEMINI_API_KEY", "")

    @property
    def report_interval_hours(self) -> int:
        """Return the scheduled report generation interval in hours."""
        return int(os.getenv("REPORT_INTERVAL_HOURS", "4"))

    @property
    def reports_dir(self) -> Path:
        """Return the directory for generated PDF reports."""
        return self.data_dir / "reports"

    @property
    def model_path(self) -> Path:
        """Resolve the configured model path."""
        configured = os.getenv("MODEL_PATH")
        if configured:
            return Path(configured).expanduser().resolve()

        return self.models_dir / "yolov8s_ap.onnx"

    @property
    def person_model_path(self) -> Path:
        """Resolve the person-detector model path (auto-downloads yolov8n.pt if absent)."""
        configured = os.getenv("PERSON_MODEL_PATH")
        if configured:
            return Path(configured).expanduser().resolve()
        explicit = self.models_dir / "yolov8n.pt"
        if explicit.exists():
            return explicit
        # Fall back to letting Ultralytics auto-download from its cache
        return Path("yolov8n.pt")

    def ensure_directories(self) -> None:
        """Create the directories the application expects at runtime."""
        for path in (
            self.data_dir,
            self.models_dir,
            self.history_dir,
            self.history_global_dir,
            self.history_crops_dir,
            self.videos_dir,
            self.temp_videos_dir,
            self.update_pool_dir,
            self.update_pool_images_dir,
            self.update_pool_labels_dir,
            self.reports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings
