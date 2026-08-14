from __future__ import annotations

from argus_skill.core.portable_filename import portable_filename_component


def test_windows_reserved_and_unsafe_names_are_encoded() -> None:
    assert portable_filename_component("CON", windows=True).startswith("argus-id-")
    assert portable_filename_component("team::task", windows=True).startswith("argus-id-")


def test_encoded_looking_logical_id_cannot_alias_an_unsafe_id() -> None:
    unsafe = portable_filename_component("team::task", windows=True)

    assert portable_filename_component(unsafe, windows=True) != unsafe
