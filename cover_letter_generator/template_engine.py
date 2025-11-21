"""Jinja2 wrapper for rendering cover-letter lego sections."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from jinja2 import Environment, FileSystemLoader, StrictUndefined


class TemplateEngine:
    """Render sections using Jinja2 templates."""

    def __init__(self, template_dir: Path) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

    def render_sections(self, sections: Iterable[Dict[str, Any]], context: Dict[str, Any]) -> List[str]:
        rendered: List[str] = []
        for section in sections:
            if not section.get("enabled", True):
                continue
            template_name = section["template"]
            template = self.env.get_template(template_name)
            section_context = {**context, **section.get("context", {})}
            rendered.append(template.render(**section_context).strip())
        return [block for block in rendered if block]
