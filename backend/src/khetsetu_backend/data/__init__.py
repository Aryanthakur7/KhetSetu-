"""Dataset acquisition: a pinned manifest, an idempotent downloader and the command guard.

``summary`` is intentionally not imported here: it needs ``pyarrow`` and ``yaml`` (extra
``data``), which the deployed Space does not install.
"""

from khetsetu_backend.data.ensure import (
    DatasetDownloadError,
    DatasetError,
    DatasetHandle,
    DatasetIntegrityError,
    DownloadOutcome,
    ensure_dataset,
)
from khetsetu_backend.data.guard import active_dataset, requires_dataset
from khetsetu_backend.data.manifest import DatasetManifest

__all__ = [
    "DatasetDownloadError",
    "DatasetError",
    "DatasetHandle",
    "DatasetIntegrityError",
    "DatasetManifest",
    "DownloadOutcome",
    "active_dataset",
    "ensure_dataset",
    "requires_dataset",
]
