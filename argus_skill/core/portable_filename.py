from __future__ import annotations

import hashlib
import os
import re

_ENCODED_COMPONENT = re.compile(r"argus-id-[0-9a-f]{64}\Z")
_WINDOWS_RESERVED = frozenset({
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
})


def portable_filename_component(
    value: str,
    *,
    windows: bool | None = None,
    max_bytes: int = 120,
) -> str:
    """Encode a logical identifier as one bounded, portable path component."""
    text = str(value)
    on_windows = os.name == "nt" if windows is None else windows
    stem = text.split(".", 1)[0].casefold()
    unsafe = (
        not text
        or any(char in text for char in "/\\\0")
        or len(text.encode("utf-8")) > max_bytes
        or _ENCODED_COMPONENT.fullmatch(text) is not None
        or (
            on_windows
            and (
                any(ord(char) < 32 or char in '<>:"|?*' for char in text)
                or text.endswith((" ", "."))
                or stem in _WINDOWS_RESERVED
            )
        )
    )
    if not unsafe:
        return text
    return f"argus-id-{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


__all__ = ["portable_filename_component"]
