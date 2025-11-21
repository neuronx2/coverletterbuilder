"""Command line interface for the cover letter generator."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config_loader import ConfigError
from .generator import ListLimits, generate_cover_letter
from .job_parser import JobDataError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a tailored cover letter from a job post.")
    parser.add_argument("--job-url", required=True, help="Link to the job posting.")
    parser.add_argument("--output", default="output/cover_letter.md", help="Where to save the generated letter.")
    parser.add_argument("--profile", default="config/profile.json", help="Path to your profile configuration file.")
    parser.add_argument(
        "--sections",
        default="config/sections.json",
        help="JSON file that defines which template sections (lego pieces) are used.",
    )
    parser.add_argument(
        "--templates",
        default="templates",
        help="Directory that stores section templates.",
    )
    parser.add_argument("--overrides", help="Optional JSON file with manual overrides for job metadata.")
    parser.add_argument(
        "--format",
        choices=["markdown", "text"],
        default="markdown",
        help="Choose markdown or plaintext output.",
    )
    parser.add_argument(
        "--company-feature",
        action="append",
        dest="company_features",
        help="Company-specific talking point to highlight (repeatable).",
    )
    parser.add_argument(
        "--skill",
        action="append",
        dest="skills",
        help="Skill to emphasize for this job (repeatable).",
    )
    parser.add_argument("--company-feature-count", type=int, default=3, help="How many company features to keep.")
    parser.add_argument("--degrees-count", type=int, default=4, help="How many degrees/qualifications to include.")
    parser.add_argument("--cert-count", type=int, default=4, help="Number of certifications to include.")
    parser.add_argument("--skills-count", type=int, default=3, help="Number of skills to include.")
    parser.add_argument("--stakeholder-count", type=int, default=2, help="Number of stakeholder audiences to include.")
    parser.add_argument("--presented-count", type=int, default=1, help="Number of presentation audiences to include.")
    parser.add_argument("--team-count", type=int, default=4, help="Number of teams to include.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    list_limits = ListLimits(
        company_features=args.company_feature_count,
        degrees=args.degrees_count,
        certifications=args.cert_count,
        skills=args.skills_count,
        stakeholders=args.stakeholder_count,
        presented_to=args.presented_count,
        teams=args.team_count,
    )

    try:
        output = generate_cover_letter(
            args.job_url,
            profile_path=Path(args.profile),
            sections_path=Path(args.sections),
            template_dir=Path(args.templates),
            output_path=Path(args.output),
            overrides_path=Path(args.overrides) if args.overrides else None,
            company_features=args.company_features,
            skills_override=args.skills,
            list_limits=list_limits,
            format_=args.format,
        )
    except (ConfigError, JobDataError) as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")

    sys.stdout.write(f"Cover letter created at {output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
