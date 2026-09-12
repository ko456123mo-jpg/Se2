"""Exception hierarchy.

Every module raises one of these so the GUI can translate failures into clear,
non-technical messages (project rule 65).
"""
from __future__ import annotations


class StegoNexusError(Exception):
    """Base class for all application errors."""

    #: short user-facing guidance shown in the GUI
    hint: str = ""

    def __init__(self, message: str, *, hint: str | None = None, details: dict | None = None):
        super().__init__(message)
        if hint:
            self.hint = hint
        self.details = details or {}

    def user_message(self) -> str:
        return f"{self} (hint: {self.hint})" if self.hint else str(self)


class ValidationError(StegoNexusError):
    hint = "Check the value you entered."


class PathError(StegoNexusError):
    hint = "Verify the path exists and is readable."


class FileNotFound(StegoNexusError):
    hint = "The file does not exist at that path."


class UnsupportedFormat(StegoNexusError):
    hint = "This file type is not supported by the selected technique."


class CapacityError(StegoNexusError):
    hint = "Use a smaller secret or a larger carrier."


class KeyOrPasswordError(StegoNexusError):
    hint = "The key/password does not match the one used to hide the data."


class IntegrityError(StegoNexusError):
    hint = "Integrity check failed - the payload or carrier may be corrupted."


class CorruptedCarrier(StegoNexusError):
    hint = "The carrier does not contain a valid StegoNexus payload."


class ToolUnavailable(StegoNexusError):
    hint = "Install the missing tool - see Tool Health and KALI_INSTALLATION.md."


class ToolExecutionError(StegoNexusError):
    hint = "The external tool failed. Inspect stderr output for details."


class ToolTimeout(StegoNexusError):
    hint = "The tool exceeded its timeout. Try a smaller input or raise the timeout."


class DatabaseError(StegoNexusError):
    hint = "Database operation failed. Check disk space and permissions."


class NetworkLabError(StegoNexusError):
    hint = "Network lab operation failed. Confirm loopback/authorized environment."


class AuthorizationError(StegoNexusError):
    hint = "This operation is restricted to authorized laboratory environments."
