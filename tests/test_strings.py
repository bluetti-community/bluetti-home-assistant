"""Tests for strings.json / translations/*.json content."""

import json
from pathlib import Path

BASE = Path(__file__).parents[1] / "custom_components" / "bluetti"


def _flatten_keys(value, prefix: str = "") -> set[str]:
    """Return the set of dotted leaf-key paths in a nested dict."""
    if not isinstance(value, dict):
        return {prefix}
    keys: set[str] = set()
    for key, sub_value in value.items():
        keys |= _flatten_keys(sub_value, f"{prefix}.{key}" if prefix else key)
    return keys


def test_every_translation_file_has_every_strings_json_key():
    # strings.json is the source of truth for which keys exist; every
    # shipped translation must define all of them, or Home Assistant falls
    # back to showing the raw key/English text for whatever is missing.
    strings_keys = _flatten_keys(json.loads((BASE / "strings.json").read_text()))

    translations_dir = BASE / "translations"
    translation_files = sorted(translations_dir.glob("*.json"))
    assert translation_files, "no translation files found"

    for path in translation_files:
        translated_keys = _flatten_keys(json.loads(path.read_text()))
        missing = strings_keys - translated_keys
        assert not missing, f"{path.name} is missing keys: {sorted(missing)}"


def test_every_translated_fn_code_has_a_name_in_strings_json():
    # A code listed without a name would lose the cloud's name and fall back
    # to the device name alone.
    from custom_components.bluetti.const import (
        TRANSLATED_ENERGY_FN_CODES,
        TRANSLATED_FN_CODES,
    )

    entity = json.loads((BASE / "strings.json").read_text())["entity"]
    for platform, fn_codes in TRANSLATED_FN_CODES.items():
        for fn_code in fn_codes:
            assert entity[platform][fn_code]["name"], (platform, fn_code)
    for fn_code in TRANSLATED_ENERGY_FN_CODES:
        assert fn_code in TRANSLATED_FN_CODES["sensor"]
        assert entity["sensor"][f"{fn_code}_energy"]["name"]
