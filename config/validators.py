import re
import sys
from utils.ip_utils import normalize_ip_list


_WINDOWS_INVALID_CHARS = set('<>:"|?*')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

def validate_email(value: str):
    """
    Validates that the value is a valid email address.
    Raises ValueError if invalid.
    """
    if not value:
        return

    # Simple regex for email validation
    pattern = r"^[\w\.+-]+@[\w\.-]+\.\w+$"
    if not re.match(pattern, value):
        raise ValueError("Invalid email address format.")


def validate_email_list(value) -> None:
    """
    Validate a list of email addresses.

    Empty lists are allowed because some settings use an empty list to mean
    "all accounts".
    """
    if value is None:
        return

    if not isinstance(value, (list, tuple)):
        raise ValueError("Expected a list of email addresses.")

    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        email = str(item or "").strip()
        if not email:
            continue
        normalized = email.lower()
        if normalized in seen:
            raise ValueError(f"Duplicate email address on row {index}.")
        validate_email(email)
        seen.add(normalized)


def validate_port(value: int):
    """
    Validates that the value is a valid TCP/UDP port number.
    Raises ValueError if invalid.
    """
    if value is None:
        return

    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ValueError("Port must be a number.")

    if port < 1 or port > 65535:
        raise ValueError("Port must be between 1 and 65535.")


def validate_directory_path(value: str | None) -> None:
    """
    Validate a directory path string for the current platform.

    Notes:
      - Accepts None/empty (use required=True to force a value).
      - Does not require the path to exist.
    """
    if value is None:
        return

    path = str(value).strip()
    if not path:
        return

    if "\x00" in path:
        raise ValueError("Path contains a NUL byte.")

    if not sys.platform.startswith("win"):
        return

    # Windows-specific checks (invalid characters, trailing spaces/dots, reserved names).
    from pathlib import PureWindowsPath

    windows_path = PureWindowsPath(path)
    for part in windows_path.parts:
        # Skip drive/root parts (e.g. "C:\\", "\\\\server\\share\\").
        if part.endswith("\\") or part == "\\":
            continue

        # Allow relative navigation segments.
        if part in (".", ".."):
            continue

        if any(ord(ch) < 32 for ch in part):
            raise ValueError("Windows paths cannot contain control characters.")

        if any(ch in _WINDOWS_INVALID_CHARS for ch in part):
            raise ValueError('Windows paths cannot contain any of: <>:"|?*')

        if part.endswith(" ") or part.endswith("."):
            raise ValueError("Windows path components cannot end with a space or period.")

        trimmed = part.rstrip(" .")
        base = trimmed.split(".", 1)[0].upper()
        if base in _WINDOWS_RESERVED_NAMES:
            raise ValueError(f"Windows path component uses a reserved name: {base}.")


def validate_ip_address_list(value) -> None:
    if value is None:
        return

    if not isinstance(value, (list, tuple)):
        raise ValueError("IP whitelist must be a list of IP addresses.")

    try:
        normalize_ip_list(value)
    except ValueError as exc:
        raise ValueError(f"Invalid IP address in whitelist: {exc}")


def validate_float_range(
    min_value: float | None = None,
    max_value: float | None = None,
    *,
    label: str = "Value",
):
    def _validator(value) -> None:
        if value is None:
            return

        text = str(value).strip()
        if not text:
            return

        try:
            parsed = float(text)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a number.")

        if (min_value is not None) and (parsed < float(min_value)):
            raise ValueError(f"{label} must be at least {min_value}.")
        if (max_value is not None) and (parsed > float(max_value)):
            raise ValueError(f"{label} must be at most {max_value}.")

    return _validator


def validate_integer_range(
    min_value: int | None = None,
    max_value: int | None = None,
    *,
    label: str = "Value",
):
    def _validator(value) -> None:
        if value is None:
            return

        text = str(value).strip()
        if not text:
            return

        try:
            parsed = int(text)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a whole number.")

        if (min_value is not None) and (parsed < int(min_value)):
            raise ValueError(f"{label} must be at least {min_value}.")
        if (max_value is not None) and (parsed > int(max_value)):
            raise ValueError(f"{label} must be at most {max_value}.")

    return _validator
