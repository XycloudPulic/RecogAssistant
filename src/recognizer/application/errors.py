# SPDX-License-Identifier: MIT

"""Application-layer exceptions independent from web framework."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base exception for application/services layer."""


class ValidationError(ApplicationError):
    """Raised when input/payload validation fails in use-cases."""


class NotFoundError(ApplicationError):
    """Raised when requested resource cannot be found."""


class ConflictError(ApplicationError):
    """Raised when a unique/consistency conflict occurs."""
