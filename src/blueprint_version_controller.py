"""Blueprint Version Controller — manages multiple blueprint versions with
gray switching, rollback, and JSON persistence."""

import json
import os
from datetime import datetime, timezone


class BlueprintVersionController:
    """Manages versioned blueprints with activation, rollback, and A/B gray mode."""

    def __init__(self, persistence_file: str):
        self._persistence_file = persistence_file
        self._versions: dict = {}       # version_id -> {blueprint, created_at}
        self._active_id: str | None = None
        self._activation_order: list[str] = []  # tracks activation sequence for rollback
        self._gray_mode: dict | None = None  # {version_a, version_b} or None
        self._load()

    # ── Persistence ─────────────────────────────────────────────────────────

    def _save(self) -> None:
        data = {
            "versions": self._versions,
            "active_id": self._active_id,
            "activation_order": self._activation_order,
            "gray_mode": self._gray_mode,
        }
        os.makedirs(os.path.dirname(self._persistence_file) or ".", exist_ok=True)
        with open(self._persistence_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self._persistence_file):
            return
        with open(self._persistence_file) as f:
            data = json.load(f)
        self._versions = data.get("versions", {})
        self._active_id = data.get("active_id")
        self._activation_order = data.get("activation_order", [])
        self._gray_mode = data.get("gray_mode")

    # ── Version operations ──────────────────────────────────────────────────

    def add_version(self, version_id: str, blueprint: dict) -> None:
        """Store a new blueprint version."""
        self._versions[version_id] = {
            "blueprint": blueprint,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def activate_version(self, version_id: str) -> None:
        """Switch the active version to *version_id*."""
        if version_id not in self._versions:
            raise KeyError(f"Version '{version_id}' does not exist")
        self._active_id = version_id
        self._activation_order.append(version_id)
        self._save()

    def rollback(self) -> None:
        """Revert to the previously active version. Requires at least 2 versions."""
        if len(self._activation_order) < 2:
            raise ValueError("Rollback requires at least 2 activated versions")
        # Pop the current activation, the previous entry is the rollback target
        self._activation_order.pop()
        self._active_id = self._activation_order[-1]
        self._save()

    def list_versions(self) -> dict:
        """Return all versions with their metadata."""
        return dict(self._versions)

    def get_active(self) -> dict | None:
        """Return the currently active blueprint, or None."""
        if self._active_id is None or self._active_id not in self._versions:
            return None
        return self._versions[self._active_id]["blueprint"]

    # ── Delete (safety: cannot delete active) ───────────────────────────────

    def delete_version(self, version_id: str) -> None:
        """Delete a version. Raises if the version is currently active."""
        if version_id not in self._versions:
            raise KeyError(f"Version '{version_id}' does not exist")
        if version_id == self._active_id:
            raise ValueError("Cannot delete active version")
        del self._versions[version_id]
        self._save()

    # ── Gray switching (A/B testing) ────────────────────────────────────────

    def enable_gray(self, version_a_id: str, version_b_id: str) -> None:
        """Enable gray mode with two versions running simultaneously."""
        for vid in (version_a_id, version_b_id):
            if vid not in self._versions:
                raise KeyError(f"Version '{vid}' does not exist")
        self._gray_mode = {
            "version_a": version_a_id,
            "version_b": version_b_id,
        }
        self._save()

    def disable_gray(self) -> None:
        """Disable gray mode."""
        self._gray_mode = None
        self._save()

    def get_gray_versions(self) -> dict | None:
        """Return the blueprints for both gray versions, or None if gray is off."""
        if self._gray_mode is None:
            return None
        a = self._gray_mode["version_a"]
        b = self._gray_mode["version_b"]
        return {
            "version_a": self._versions[a]["blueprint"],
            "version_b": self._versions[b]["blueprint"],
        }
