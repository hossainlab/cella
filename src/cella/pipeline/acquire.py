"""P0 - Acquisition (minimal local footprint).

Two inputs, both tiny on disk, both persisted under ``settings.raw_dir``:

    data/raw/
      models/Adult_Human_<Organ>.pkl   (~2 MB each) - the classifier weights
      obs/<Organ>.parquet              (~few MB each) - cached cell metadata
      manifest.json                    (url, bytes, sha256 per file + release)

Why no bulk atlas download: no v1 tool touches the expression matrix. The
Marker Atlas and Fingerprint Explorer run entirely on the ``.pkl`` classifier
weights; the only thing needed from each 1-3 GB ``.h5ad`` atlas is its ``.obs``
table (cell-type labels, counts, dataset provenance). Because ``.h5ad`` is HDF5
and the Sanger bucket honors HTTP Range requests, we read *only* the ``.obs``
group remotely (~125 MB of range reads vs a 1.6 GB file) and cache it as a small
local parquet. After the first run everything is local (~50 MB total) and the
pipeline never needs the network again. See docs/CONCEPT.md §5.1-5.3.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import fsspec
import h5py
import httpx
import pandas as pd
from tqdm import tqdm

try:  # anndata >=0.11 moved read_elem out of .experimental
    from anndata.io import read_elem
except ImportError:  # pragma: no cover - older anndata
    from anndata.experimental import read_elem

from cella.core.config import ORGANS, settings

BASE_URL = "https://celltypist.cog.sanger.ac.uk/Resources/Organ_atlas"

# celltypist.org uses underscored directory names for multi-word organs.
_DIR = {organ: organ.replace(" ", "_") for organ in ORGANS}


def model_url(organ: str) -> str:
    d = _DIR[organ]
    return f"{BASE_URL}/{d}/models/Adult_Human_{d}.pkl"


def atlas_url(organ: str) -> str:
    """URL of the full .h5ad atlas (read remotely for .obs; never downloaded whole)."""
    d = _DIR[organ]
    return f"{BASE_URL}/{d}/{d}.h5ad"


def model_path(organ: str) -> Path:
    return settings.raw_dir / "models" / f"Adult_Human_{_DIR[organ]}.pkl"


def obs_path(organ: str) -> Path:
    return settings.raw_dir / "obs" / f"{_DIR[organ]}.parquet"


def atlas_path(organ: str) -> Path:
    """Local path for a full .h5ad atlas (expression matrix) used for derivation."""
    return settings.atlas_dir / f"{_DIR[organ]}.h5ad"


# --------------------------------------------------------------------------- #
# Model download (small .pkl files)
# --------------------------------------------------------------------------- #

def _remote_size(client: httpx.Client, url: str) -> int | None:
    resp = client.head(url, follow_redirects=True)
    resp.raise_for_status()
    length = resp.headers.get("content-length")
    return int(length) if length is not None else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(client: httpx.Client, url: str, dest: Path, *, force: bool) -> Path:
    """Stream ``url`` to ``dest``. Resumes a partial ``.part`` file; idempotent."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = _remote_size(client, url)

    if dest.exists() and not force:
        if expected is None or dest.stat().st_size == expected:
            tqdm.write(f"skip (present): {dest.name}")
            return dest

    part = dest.with_suffix(dest.suffix + ".part")
    resume_from = part.stat().st_size if part.exists() and not force else 0
    if force and part.exists():
        part.unlink()
        resume_from = 0

    headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
    mode = "ab" if resume_from else "wb"

    with client.stream("GET", url, headers=headers, follow_redirects=True) as resp:
        # 200 = full body, 206 = partial (resume honored). Anything else: restart.
        if resume_from and resp.status_code != 206:
            resume_from = 0
            mode = "wb"
        resp.raise_for_status()
        with (
            part.open(mode) as fh,
            tqdm(
                total=expected,
                initial=resume_from,
                unit="B",
                unit_scale=True,
                desc=dest.name,
            ) as bar,
        ):
            for chunk in resp.iter_bytes(chunk_size=1 << 20):
                fh.write(chunk)
                bar.update(len(chunk))

    if expected is not None and part.stat().st_size != expected:
        raise OSError(
            f"size mismatch for {dest.name}: got {part.stat().st_size}, expected {expected}"
        )
    part.replace(dest)
    return dest


# --------------------------------------------------------------------------- #
# Remote .obs caching (read metadata only, never the whole atlas)
# --------------------------------------------------------------------------- #

def _read_remote_obs(url: str, *, retries: int = 4) -> pd.DataFrame:
    """Read only the .obs group of a remote .h5ad, retrying on transient network drops."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with fsspec.open(url, "rb").open() as remote, h5py.File(remote, "r") as h5:
                return read_elem(h5["obs"])
        except Exception as exc:  # noqa: BLE001 - network layer raises many types
            last_exc = exc
            wait = 2 ** (attempt - 1)
            tqdm.write(f"  read failed (attempt {attempt}/{retries}): {exc}; retrying in {wait}s")
            time.sleep(wait)
    raise OSError(f"failed to read obs after {retries} attempts: {url}") from last_exc


def cache_obs_one(organ: str, *, force: bool = False) -> Path:
    """Read only the ``.obs`` group of one organ's remote .h5ad and cache as parquet."""
    dest = obs_path(organ)
    if dest.exists() and not force:
        tqdm.write(f"skip (present): {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)

    obs = _read_remote_obs(atlas_url(organ))
    # Object dtype -> string so parquet round-trips cleanly.
    obs = obs.astype({c: "string" for c in obs.select_dtypes("object").columns})
    obs.to_parquet(dest)
    tqdm.write(f"cached obs: {organ} ({len(obs):,} cells, {obs.shape[1]} cols) -> {dest.name}")
    return dest


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #

def _manifest_entries(kind: str, paths: dict[str, Path]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for organ, path in paths.items():
        entries.append(
            {
                "organ": organ,
                "kind": kind,
                "path": str(path.relative_to(settings.raw_dir)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return entries


def _write_manifest(new_entries: list[dict[str, object]]) -> Path:
    """Merge entries into data/raw/manifest.json keyed by path."""
    manifest_path = settings.raw_dir / "manifest.json"
    existing: dict[str, dict[str, object]] = {}
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text())
        existing = {str(e["path"]): e for e in prior.get("files", [])}

    for entry in new_entries:
        existing[str(entry["path"])] = entry

    payload = {
        "atlas_release": settings.atlas_release,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": BASE_URL,
        "files": sorted(existing.values(), key=lambda e: str(e["path"])),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2))
    return manifest_path


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #

def acquire_models(organs: tuple[str, ...] = ORGANS, *, force: bool = False) -> None:
    """Download the .pkl classifier models (the core v1 asset)."""
    paths: dict[str, Path] = {}
    with httpx.Client(timeout=httpx.Timeout(60.0, read=None)) as client:
        for organ in organs:
            paths[organ] = _download(client, model_url(organ), model_path(organ), force=force)
    _write_manifest(_manifest_entries("model", paths))


def cache_obs(organs: tuple[str, ...] = ORGANS, *, force: bool = False) -> None:
    """Remote-read each organ's .obs and cache it as a small local parquet.

    Resilient: a failing organ is recorded and skipped so one network drop does
    not abort the whole batch. Raises at the end if any organ never succeeded.
    """
    paths: dict[str, Path] = {}
    failed: list[str] = []
    for organ in organs:
        try:
            paths[organ] = cache_obs_one(organ, force=force)
        except Exception as exc:  # noqa: BLE001 - keep going, report at end
            failed.append(organ)
            tqdm.write(f"FAILED: {organ}: {exc}")
    if paths:
        _write_manifest(_manifest_entries("obs", paths))
    if failed:
        raise RuntimeError(f"obs caching failed for: {', '.join(failed)} (rerun to retry)")


def acquire_atlases(organs: tuple[str, ...] = ORGANS, *, force: bool = False) -> None:
    """Download the full .h5ad atlases (~30 GB total; needed for expression derivation).

    These carry the expression matrix used to precompute pseudobulk / DGE artifacts
    for the Organ Browser. They are large and transient — the raw files can be
    removed once the small derived artifacts are built.
    """
    paths: dict[str, Path] = {}
    with httpx.Client(timeout=httpx.Timeout(60.0, read=None)) as client:
        for organ in organs:
            paths[organ] = _download(client, atlas_url(organ), atlas_path(organ), force=force)
    _write_manifest(_manifest_entries("atlas", paths))


def acquire_all(organs: tuple[str, ...] = ORGANS, *, force: bool = False) -> None:
    """Acquire everything the pipeline needs locally: models + cached .obs (~50 MB)."""
    acquire_models(organs, force=force)
    cache_obs(organs, force=force)
