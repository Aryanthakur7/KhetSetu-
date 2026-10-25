"""Errors a service may raise across the seam.

Each error carries the :class:`~khetsetu_contracts.models.MessageKey` the frontend should
show, so the UI never needs to read exception text (which could leak internals).
"""

from __future__ import annotations

from typing import ClassVar

from khetsetu_contracts.models import MessageKey


class ContractError(Exception):
    """Base class: a failure the user can be told about in plain words."""

    message_key: ClassVar[MessageKey] = MessageKey.UNAVAILABLE


class InvalidImageError(ContractError):
    """The bytes are not a readable image."""

    message_key: ClassVar[MessageKey] = MessageKey.INVALID_IMAGE


class ImageTooLargeError(ContractError):
    """The upload is too big in bytes or in pixels."""

    message_key: ClassVar[MessageKey] = MessageKey.IMAGE_TOO_LARGE


class NotReadyError(ContractError):
    """The service is still starting up."""

    message_key: ClassVar[MessageKey] = MessageKey.NOT_READY
