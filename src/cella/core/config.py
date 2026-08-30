"""Central settings, read from environment / .env (see .env.example).

Shared by the offline pipeline and the online API so paths and the atlas
release stamp stay consistent across both halves of the system.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The 12 human organ atlases in scope for v1 (docs/CONCEPT.md §2).
ORGANS: tuple[str, ...] = (
    "Blood",
    "Bone marrow",
    "Heart",
    "Hippocampus",
    "Intestine",
    "Kidney",
    "Liver",
    "Lung",
    "Lymph node",
    "Pancreas",
    "Skeletal muscle",
    "Spleen",
)


class Settings(BaseSettings):
    """Runtime configuration. Prefix env vars with ``CELLA_``."""

    model_config = SettingsConfigDict(
        env_prefix="CELLA_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Field(default=Path("./data"))
    raw_dir: Path = Field(default=Path("./data/raw"))
    processed_dir: Path = Field(default=Path("./data/processed"))
    # Full .h5ad atlases (expression matrices) for the Organ Browser derivation.
    atlas_dir: Path = Field(default=Path("./data/counts_data"))

    atlas_release: str = Field(default="unset")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/cella",
    )


settings = Settings()
