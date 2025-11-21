"""Core orchestration logic for building cover letters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config_loader import load_overrides, load_profile, load_sections
from .job_parser import JobDetails, fetch_job_details
from .template_engine import TemplateEngine


@dataclass
class ListLimits:
    company_features: int = 3
    degrees: int = 4
    certifications: int = 5
    skills: int = 3
    stakeholders: int = 2
    presented_to: int = 1
    teams: int = 4


def generate_cover_letter(
    job_url: str,
    profile_path: Path,
    sections_path: Path,
    template_dir: Path,
    output_path: Path,
    *,
    overrides_path: Optional[Path] = None,
    company_features: Optional[List[str]] = None,
    skills_override: Optional[List[str]] = None,
    list_limits: Optional[ListLimits] = None,
    format_: str = "markdown",
) -> Path:
    profile = load_profile(profile_path)
    sections = load_sections(sections_path)
    overrides = load_overrides(overrides_path)
    job_details = fetch_job_details(job_url)
    limits = list_limits or ListLimits()

    context = build_context(
        job_details,
        profile,
        overrides,
        company_features=company_features,
        skills_override=skills_override,
        limits=limits,
    )
    engine = TemplateEngine(template_dir)
    rendered_sections = engine.render_sections(sections, context)
    separator = "\n\n" if format_ == "markdown" else "\n"
    output_content = separator.join(rendered_sections).strip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_content, encoding="utf-8")
    return output_path


def build_context(
    job_details: JobDetails,
    profile: Dict[str, Any],
    overrides: Dict[str, Any],
    *,
    company_features: Optional[List[str]] = None,
    skills_override: Optional[List[str]] = None,
    limits: ListLimits,
) -> Dict[str, Any]:
    applicant = profile["applicant"]
    defaults = profile["defaults"]
    job_context = job_details.as_context()

    def _value(key: str) -> Optional[str]:
        return overrides.get(key) or job_context.get(key)

    company = _value("company")
    position = _value("position") or _value("positionA")
    city = _value("city") or defaults.get("city_fallback")
    region = _value("region") or defaults.get("region_fallback")
    country = _value("country") or defaults.get("country_fallback")
    hiring_manager = (
        overrides.get("hiring_manager")
        or job_context.get("hiring_manager")
        or defaults.get("hiring_manager_fallback")
    )

    company_feature_values = _preferred_sequence(
        company_features,
        overrides.get("company_features"),
        defaults.get("company_features", []),
    )
    skill_values = _preferred_sequence(
        skills_override,
        overrides.get("skills"),
        profile["lists"].get("skills", []),
    )

    context = {
        "today": date.today().strftime("%B %d, %Y"),
        "applicant": applicant,
        "company": company,
        "company_upper": company.upper() if company else None,
        "position": position,
        "positionA": position,
        "hiring_manager": hiring_manager,
        "city": city,
        "region": region,
        "country": country,
        "job": job_context,
        "company_features": _limit_list(company_feature_values, limits.company_features),
        "skills": _limit_list(skill_values, limits.skills),
        "job_url": job_context.get("job_url"),
    }

    lists = profile["lists"]
    context["degrees"] = _limit_list(lists.get("degrees", []), limits.degrees)
    context["certifications"] = _limit_list(lists.get("certifications", []), limits.certifications)
    context["stakeholders"] = _limit_list(lists.get("stakeholders", []), limits.stakeholders)
    context["presented_to"] = _limit_list(lists.get("presented_to", []), limits.presented_to)
    context["teams"] = _limit_list(lists.get("teams", []), limits.teams)

    context.update(_fan_out("company_feature", context["company_features"], limits.company_features))
    context.update(_fan_out("degree", context["degrees"], limits.degrees))
    context.update(_fan_out("certi", context["certifications"], limits.certifications))
    context.update(_fan_out("skill", context["skills"], limits.skills))
    context.update(_fan_out("stakeholder", context["stakeholders"], limits.stakeholders))
    context.update(_fan_out("presented", context["presented_to"], limits.presented_to))
    context.update(_fan_out("team", context["teams"], limits.teams))

    context["location_block"] = ", ".join(filter(None, [city, region, country])) or job_context.get(
        "raw_location"
    )

    return context


def _preferred_sequence(
    cli_values: Optional[List[str]],
    override_values: Optional[List[str]],
    fallback: Optional[List[str]],
) -> List[str]:
    for candidate in (cli_values, override_values, fallback):
        if candidate:
            return [item for item in candidate if item]
    return []


def _limit_list(values: List[str], limit: int) -> List[str]:
    if limit <= 0:
        return []
    return values[:limit]


def _fan_out(prefix: str, values: List[str], limit: int) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}
    for idx in range(limit):
        key = f"{prefix}{idx + 1}"
        result[key] = values[idx] if idx < len(values) else None
    return result
