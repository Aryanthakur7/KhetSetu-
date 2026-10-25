"""Start-up steps that run before the app is built."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from khetsetu_backend.config import DatasetMode
from khetsetu_backend.data.ensure import DatasetHandle, ensure_dataset

if TYPE_CHECKING:
    from collections.abc import Callable

    from khetsetu_backend.config import Settings

logger = logging.getLogger(__name__)


def prepare_runtime(
    settings: Settings,
    *,
    ensure: Callable[[Settings], DatasetHandle] = ensure_dataset,
) -> DatasetHandle | None:
    """Fetch the dataset when running locally; do nothing on a Space or in CI.

    The deployed Space only needs the model, never the 823 MB of training images, so
    ``settings.effective_dataset_mode`` is ``off`` there and this returns ``None``.
    """
    if settings.effective_dataset_mode is DatasetMode.BLOCKING:
        return ensure(settings)
    logger.info("dataset prefetch skipped (mode=off)")
    return None
