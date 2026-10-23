"""Standard-library logging setup driven by :class:`~khetsetu_backend.config.Settings`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from khetsetu_backend.config import Settings

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class _KhetSetuHandler(logging.StreamHandler[TextIO]):
    """Marker subclass so repeated :func:`configure_logging` calls find their own handler."""


def configure_logging(settings: Settings) -> None:
    """Set the root logger level and install exactly one KhetSetu stream handler.

    Idempotent: a previously installed handler is replaced, never duplicated. Settings
    objects must not be logged wholesale; log individual non-secret values instead.

    Args:
        settings: Validated settings; only ``log_level`` is read.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, _KhetSetuHandler):
            root.removeHandler(handler)
            handler.close()
    handler = _KhetSetuHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.setLevel(settings.log_level.value)
