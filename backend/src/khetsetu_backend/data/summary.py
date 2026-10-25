"""Read the real shape of the dataset (row, class and shard counts) without loading images.

This is the only module in the data package that imports ``pyarrow`` and ``yaml``; both come
from the optional ``data`` extra, which the deployed Space does not install.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pyarrow.parquet as pq
import yaml

from khetsetu_backend.data.ensure import DatasetIntegrityError

if TYPE_CHECKING:
    from pathlib import Path

    from khetsetu_backend.data.ensure import DatasetHandle

_FRONT_MATTER_FENCE = "---"


@dataclass(frozen=True)
class DatasetSummary:
    """Counts describing the dataset on disk."""

    num_rows: int
    num_classes: int
    class_names: tuple[str, ...]
    num_shards: int


def _front_matter(readme: Path) -> dict[str, Any]:
    """Return the YAML block between the first two ``---`` lines of the dataset card."""
    lines = readme.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != _FRONT_MATTER_FENCE:
        msg = f"{readme.name} has no YAML front matter"
        raise DatasetIntegrityError(msg)
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        msg = f"{readme.name} front matter is not closed"
        raise DatasetIntegrityError(msg) from None
    loaded = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(loaded, dict):
        msg = f"{readme.name} front matter is not a mapping"
        raise DatasetIntegrityError(msg)
    return loaded


def read_class_names(readme: Path) -> tuple[str, ...]:
    """Return the class names in id order, read from the dataset card.

    Raises:
        DatasetIntegrityError: The card has no ``label`` class list, or the ids are not
            exactly ``0..n-1``.
    """
    meta = _front_matter(readme)
    try:
        label = next(f for f in meta["dataset_info"]["features"] if f["name"] == "label")
        raw = label["dtype"]["class_label"]["names"]
        by_id = {int(key): str(name) for key, name in raw.items()}
    except (KeyError, StopIteration, TypeError, ValueError, AttributeError):
        msg = f"{readme.name} does not list class names for the 'label' feature"
        raise DatasetIntegrityError(msg) from None
    if sorted(by_id) != list(range(len(by_id))):
        msg = f"{readme.name} class ids are not contiguous from 0"
        raise DatasetIntegrityError(msg)
    return tuple(by_id[i] for i in range(len(by_id)))


def summarize_dataset(handle: DatasetHandle) -> DatasetSummary:
    """Count rows and classes; only parquet metadata is read, never the images."""
    rows = 0
    for shard in handle.parquet_files:
        parquet = pq.ParquetFile(shard)
        if "label" not in parquet.schema_arrow.names:
            msg = f"{shard.name} has no 'label' column"
            raise DatasetIntegrityError(msg)
        rows += parquet.metadata.num_rows
    names = read_class_names(handle.readme)
    return DatasetSummary(
        num_rows=rows,
        num_classes=len(names),
        class_names=names,
        num_shards=len(handle.parquet_files),
    )
