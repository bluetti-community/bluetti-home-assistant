"""Sanity checks for hacs.json, required for HACS to recognize this repo."""

import json
from pathlib import Path

HACS_JSON_PATH = Path(__file__).parents[1] / "hacs.json"


MANIFEST_PATH = Path(__file__).parents[1] / "custom_components" / "bluetti" / "manifest.json"


def test_hacs_json_is_valid_and_has_a_name():
    hacs_json = json.loads(HACS_JSON_PATH.read_text())
    assert hacs_json["name"] == "BLUETTI (community)"


def test_the_fork_is_told_apart_from_the_official_integration():
    """
    Same domain and brand icon as the official integration by design, so
    the display name is the only thing HACS and HA show that can differ.
    """
    hacs_json = json.loads(HACS_JSON_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["domain"] == "bluetti"
    assert manifest["name"] == hacs_json["name"] != "BLUETTI"
    assert manifest["codeowners"] == ["@chpego"]


def test_hacs_json_renders_the_readme_in_the_hacs_ui():
    hacs_json = json.loads(HACS_JSON_PATH.read_text())
    assert hacs_json["render_readme"] is True


def test_hacs_installs_the_release_asset_the_workflow_attaches():
    """
    HACS only counts downloads of a release asset it was told to use;
    without zip_release it installs from the repository archive and the
    counter never moves. release.yml attaches exactly this file.
    """
    hacs_json = json.loads(HACS_JSON_PATH.read_text())
    assert hacs_json["zip_release"] is True
    assert hacs_json["filename"] == "bluetti.zip"
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "release.yml").read_text()
    assert "bluetti.zip" in workflow
