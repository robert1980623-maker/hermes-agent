"""
Configuration management for AgentFactory Swarm roles.

Loads role definitions from YAML files and provides typed access
to runtime, model, and system prompt configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional

import yaml


@dataclass
class RoleConfig:
    """Configuration for a single Swarm role."""

    runtime: str = "cline"
    model: Optional[str] = None
    system_prompt: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoleConfig":
        """Create a RoleConfig from a raw dictionary."""
        return cls(
            runtime=data.get("runtime", "cline"),
            model=data.get("model") or None,
            system_prompt=data.get("system_prompt", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize back to a dictionary."""
        result: Dict[str, Any] = {"runtime": self.runtime}
        if self.model:
            result["model"] = self.model
        result["system_prompt"] = self.system_prompt
        return result


def load_role_file(file_path: str | Path) -> RoleConfig:
    """Load a single role definition from a YAML file.

    Args:
        file_path: Path to the role YAML file.

    Returns:
        A populated RoleConfig instance.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Role config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Role config must be a YAML mapping, got: {type(data).__name__}")

    return RoleConfig.from_dict(data)


def load_roles(config_path: str | Path) -> Dict[str, RoleConfig]:
    """Load all role definitions from the main config.yaml.

    Reads the `roles` section of the config and resolves each role's
    YAML file to a RoleConfig.

    Supports two role definition styles in config.yaml:

    1. File reference:
       roles:
         architect:
           config_file: "config/roles/architect.yaml"

    2. Inline definition:
       roles:
         architect:
           runtime: cline
           system_prompt: "You are the architect..."

    Args:
        config_path: Path to the main config.yaml file.

    Returns:
        Dict mapping role name (str) to its RoleConfig.

    Raises:
        FileNotFoundError: If config_path or any referenced role file does not exist.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping, got: {type(config).__name__}")

    roles_section = config.get("roles", {})
    if not isinstance(roles_section, dict):
        raise ValueError("'roles' section must be a YAML mapping")

    result: Dict[str, RoleConfig] = {}
    config_dir = config_path.parent

    for role_name, role_def in roles_section.items():
        if not isinstance(role_def, dict):
            raise ValueError(f"Role '{role_name}' must be a YAML mapping")

        # Style 1: file reference
        if "config_file" in role_def:
            file_ref = role_def["config_file"]
            # Resolve relative to the config file's directory
            resolved = config_dir / file_ref
            result[role_name] = load_role_file(resolved)
            continue

        # Style 2: inline definition
        result[role_name] = RoleConfig.from_dict(role_def)

    return result
