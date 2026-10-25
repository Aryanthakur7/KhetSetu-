"""Tests for reading the dataset card and parquet shards."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from khetsetu_backend.data import DatasetIntegrityError, DownloadOutcome
from khetsetu_backend.data.ensure import DatasetHandle
from khetsetu_backend.data.summary import read_class_names, summarize_dataset

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DATASET = REPO_ROOT / "data" / "plant_village_classification"

CARD = """---
dataset_info:
  features:
  - name: image
    dtype: image
  - name: label
    dtype:
      class_label:
        names:
          '0': {zero}
          '1': {one}
          '{last}': {two}
---
# A card
"""


def _card(tmp_path: Path, *, last: int = 2) -> Path:
    path = tmp_path / "README.md"
    path.write_text(CARD.format(zero="Apple", one="Bean", two="Corn", last=last), encoding="utf-8")
    return path


def _shard(path: Path, rows: int) -> Path:
    table = pa.table({"label": list(range(rows)), "image": [b"x"] * rows})
    pq.write_table(table, path)
    return path


def test_class_names_come_back_in_id_order(tmp_path: Path) -> None:
    assert read_class_names(_card(tmp_path)) == ("Apple", "Bean", "Corn")


def test_non_contiguous_class_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(DatasetIntegrityError, match="contiguous"):
        read_class_names(_card(tmp_path, last=5))


def test_a_card_without_front_matter_is_rejected(tmp_path: Path) -> None:
    card = tmp_path / "README.md"
    card.write_text("# no front matter\n", encoding="utf-8")
    with pytest.raises(DatasetIntegrityError, match="front matter"):
        read_class_names(card)


def test_a_card_without_class_names_is_rejected(tmp_path: Path) -> None:
    card = tmp_path / "README.md"
    card.write_text("---\ndataset_info:\n  features: []\n---\n", encoding="utf-8")
    with pytest.raises(DatasetIntegrityError, match="class names"):
        read_class_names(card)


def test_summary_adds_up_rows_over_all_shards(tmp_path: Path) -> None:
    handle = DatasetHandle(
        root=tmp_path,
        readme=_card(tmp_path),
        parquet_files=(_shard(tmp_path / "a.parquet", 3), _shard(tmp_path / "b.parquet", 4)),
        revision="r",
        outcome=DownloadOutcome.CACHE_HIT,
    )
    summary = summarize_dataset(handle)
    assert summary.num_rows == 7
    assert summary.num_classes == 3
    assert summary.num_shards == 2
    assert summary.class_names == ("Apple", "Bean", "Corn")


def test_a_shard_without_a_label_column_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.parquet"
    pq.write_table(pa.table({"image": [b"x"]}), bad)
    handle = DatasetHandle(
        root=tmp_path,
        readme=_card(tmp_path),
        parquet_files=(bad,),
        revision="r",
        outcome=DownloadOutcome.CACHE_HIT,
    )
    with pytest.raises(DatasetIntegrityError, match="label"):
        summarize_dataset(handle)


@pytest.mark.dataset
@pytest.mark.skipif(not REAL_DATASET.is_dir(), reason="local dataset not downloaded")
def test_real_dataset_has_the_documented_shape() -> None:
    shards = tuple(sorted((REAL_DATASET / "data").glob("train-*.parquet")))
    handle = DatasetHandle(
        root=REAL_DATASET,
        readme=REAL_DATASET / "README.md",
        parquet_files=shards,
        revision="local",
        outcome=DownloadOutcome.CACHE_HIT,
    )
    summary = summarize_dataset(handle)
    assert summary.num_rows == 55448
    assert summary.num_classes == 39
    assert summary.class_names[0] == "Apple___Apple_scab"
    assert summary.class_names[4] == "Background_without_leaves"
    assert summary.num_shards == 2
