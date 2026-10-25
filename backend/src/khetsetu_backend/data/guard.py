"""``@requires_dataset``: make a command download the dataset before it runs.

Put this decorator on any command that reads the dataset (training, evaluation, dev tools).
The command body then calls :func:`active_dataset` to get the verified files.
"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from functools import wraps
from typing import TYPE_CHECKING

from khetsetu_backend.config import SettingsError, load_settings
from khetsetu_backend.data.ensure import DatasetError, DatasetHandle, ensure_dataset

if TYPE_CHECKING:
    from collections.abc import Callable

EXIT_INVALID_CONFIG = 2
EXIT_DATASET_PROBLEM = 3

_active: ContextVar[DatasetHandle | None] = ContextVar("khetsetu_active_dataset", default=None)


def active_dataset() -> DatasetHandle:
    """Return the dataset prepared by the surrounding ``@requires_dataset`` call.

    Raises:
        RuntimeError: Called outside a function decorated with ``requires_dataset``.
    """
    handle = _active.get()
    if handle is None:
        msg = "active_dataset() only works inside a function decorated with @requires_dataset"
        raise RuntimeError(msg)
    return handle


def requires_dataset[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Run ``ensure_dataset`` before ``func``; exit 2 on bad settings, 3 on a dataset problem."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            handle = ensure_dataset(load_settings())
        except SettingsError as error:
            sys.stderr.write(f"{error}\n")
            raise SystemExit(EXIT_INVALID_CONFIG) from None
        except DatasetError as error:
            sys.stderr.write(f"{error}\n")
            raise SystemExit(EXIT_DATASET_PROBLEM) from None
        token = _active.set(handle)
        try:
            return func(*args, **kwargs)
        finally:
            _active.reset(token)

    return wrapper
