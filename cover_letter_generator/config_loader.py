"""Utilities for loading configuration files for the cover letter generator."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json


class ConfigError(RuntimeError):
    """Raised when a configuration file is invalid."""


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc


def load_profile(path: Path) -> Dict[str, Any]:
    """Load applicant profile configuration."""
    raw = _read_json(path)
    applicant = raw.get("applicant", {})
    lists = raw.get("lists", {})
    defaults = raw.get("defaults", {})

    for field in ("name", "email"):
        if field not in applicant:
            raise ConfigError(f"Missing applicant.{field} in {path}")

    def _list(key: str) -> List[str]:
        value = lists.get(key, [])
        if not isinstance(value, list):
            raise ConfigError(f"Expected 'lists.{key}' to be a list in {path}")
        return value

    normalized = {
        "applicant": applicant,
        "lists": {
            "degrees": _list("degrees"),
            "certifications": _list("certifications"),
            "skills": _list("skills"),
            "stakeholders": _list("stakeholders"),
            "presented_to": _list("presented_to"),
            "teams": _list("teams"),
        },
        "defaults": {
            "company_features": defaults.get("company_features", []),
            "hiring_manager_fallback": defaults.get("hiring_manager_fallback", "Hiring Manager"),
            "city_fallback": defaults.get("city_fallback"),
            "region_fallback": defaults.get("region_fallback"),
            "country_fallback": defaults.get("country_fallback"),
        },
    }
    return normalized


def load_sections(path: Path) -> List[Dict[str, Any]]:
    """Load section configuration (lego blocks)."""
    raw = _read_json(path)
    sections = raw.get("sections", [])
    if not isinstance(sections, list):
        raise ConfigError(f"Expected 'sections' to be a list in {path}")

    for section in sections:
        if "template" not in section:
            raise ConfigError("Each section needs a template file reference")
        section.setdefault("enabled", True)
    return sections


def load_overrides(path: Path | None) -> Dict[str, Any]:
    """Load manual overrides (optional)."""
    if path is None:
        return {}
    return _read_json(path)
