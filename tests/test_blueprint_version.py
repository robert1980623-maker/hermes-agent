"""Tests for the BlueprintVersionController."""

import json
import os
import time

import pytest

from src.blueprint_version_controller import BlueprintVersionController


@pytest.fixture
def controller(tmp_path):
    """Provide a fresh controller backed by a temp JSON file."""
    persistence_file = tmp_path / "versions.json"
    return BlueprintVersionController(str(persistence_file))


# ── Test 1: Add and activate a new version ──────────────────────────────────

def test_add_and_activate_version(controller):
    bp = {"name": "test_blueprint", "steps": ["a", "b"]}
    controller.add_version("v1", bp)
    controller.activate_version("v1")
    assert controller.get_active() == bp


# ── Test 2: Rollback to previous version ────────────────────────────────────

def test_rollback_to_previous(controller):
    controller.add_version("v1", {"version": 1})
    controller.activate_version("v1")

    controller.add_version("v2", {"version": 2})
    controller.activate_version("v2")
    assert controller.get_active() == {"version": 2}

    controller.rollback()
    assert controller.get_active() == {"version": 1}


# ── Test 3: Cannot delete active version ────────────────────────────────────

def test_cannot_delete_active_version(controller):
    controller.add_version("v1", {"version": 1})
    controller.activate_version("v1")

    with pytest.raises(ValueError, match="Cannot delete active version"):
        controller.delete_version("v1")


# ── Test 4: List versions shows correct metadata ────────────────────────────

def test_list_versions_shows_metadata(controller):
    bp1 = {"name": "bp1"}
    bp2 = {"name": "bp2"}
    controller.add_version("v1", bp1)
    controller.add_version("v2", bp2)

    versions = controller.list_versions()
    assert len(versions) == 2

    v1_info = versions["v1"]
    v2_info = versions["v2"]
    assert v1_info["blueprint"] == bp1
    assert v2_info["blueprint"] == bp2
    assert "created_at" in v1_info
    assert "created_at" in v2_info
    assert v2_info["created_at"] >= v1_info["created_at"]


# ── Test 5: Gray mode — two versions active simultaneously ──────────────────

def test_gray_mode_two_versions_active(controller):
    controller.add_version("vA", {"name": "version_A"})
    controller.add_version("vB", {"name": "version_B"})

    controller.enable_gray("vA", "vB")
    gray = controller.get_gray_versions()
    assert gray["version_a"] == {"name": "version_A"}
    assert gray["version_b"] == {"name": "version_B"}

    controller.disable_gray()
    assert controller.get_gray_versions() is None


# ── Test 6: Persistence — versions survive restart ──────────────────────────

def test_persistence_survives_restart(tmp_path):
    persistence_file = tmp_path / "versions.json"

    # First controller: add versions and activate
    c1 = BlueprintVersionController(str(persistence_file))
    c1.add_version("v1", {"name": "persisted_v1"})
    c1.add_version("v2", {"name": "persisted_v2"})
    c1.activate_version("v2")

    # Second controller: load from same file
    c2 = BlueprintVersionController(str(persistence_file))
    assert c2.get_active() == {"name": "persisted_v2"}
    versions = c2.list_versions()
    assert len(versions) == 2
    assert versions["v1"]["blueprint"] == {"name": "persisted_v1"}


# ── Test 7: Invalid version_id raises error ─────────────────────────────────

def test_invalid_version_id_raises_error(controller):
    with pytest.raises(KeyError, match="v99"):
        controller.activate_version("v99")

    with pytest.raises(KeyError, match="v99"):
        controller.delete_version("v99")

    controller.add_version("v1", {"x": 1})
    controller.activate_version("v1")

    with pytest.raises(ValueError, match="at least 2"):
        controller.rollback()


# ── Additional safety: rollback with only 1 version ─────────────────────────

def test_rollback_requires_at_least_two_versions(controller):
    controller.add_version("v1", {"x": 1})
    controller.activate_version("v1")

    with pytest.raises(ValueError, match="at least 2"):
        controller.rollback()
