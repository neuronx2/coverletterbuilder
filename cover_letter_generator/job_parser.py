"""Helpers for extracting structured data from job posting pages."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import json
import re

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
}


@dataclass
class JobDetails:
    url: str
    position: Optional[str]
    company: Optional[str]
    hiring_manager: Optional[str]
    city: Optional[str]
    region: Optional[str]
    country: Optional[str]
    raw_location: Optional[str] = None
    description: Optional[str] = None

    def as_context(self) -> Dict[str, Optional[str]]:
        return {
            "position": self.position,
            "company": self.company,
            "hiring_manager": self.hiring_manager,
            "city": self.city,
            "region": self.region,
            "country": self.country,
            "job_url": self.url,
            "raw_location": self.raw_location,
            "description": self.description,
        }


class JobDataError(RuntimeError):
    """Raised when the job posting cannot be fetched."""


def fetch_job_details(url: str, timeout: int = 20) -> JobDetails:
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise JobDataError(f"Unable to fetch {url}: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    json_ld_data = _extract_json_ld(soup)
    job = _extract_job_from_json_ld(json_ld_data)

    position = job.get("title") if job else None
    company = _extract_company(job, soup)
    hiring_manager = _extract_hiring_manager(job, soup)
    city, region, country, raw_location = _extract_location(job)

    if not position:
        position = _meta_content(soup, ["og:title", "twitter:title"]) or soup.title.string if soup.title else None
    description = _meta_content(soup, ["og:description", "twitter:description"])

    return JobDetails(
        url=url,
        position=_clean_text(position),
        company=_clean_text(company),
        hiring_manager=_clean_text(hiring_manager),
        city=_clean_text(city),
        region=_clean_text(region),
        country=_clean_text(country),
        raw_location=_clean_text(raw_location),
        description=_clean_text(description),
    )


def _extract_json_ld(soup: BeautifulSoup) -> list[Any]:
    nodes: list[Any] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.text or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            nodes.extend(data)
        else:
            nodes.append(data)
    return nodes


def _extract_job_from_json_ld(nodes: list[Any]) -> Dict[str, Any]:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("@type")
        if isinstance(node_type, list):
            types = [t.lower() for t in node_type]
            if "jobposting" in types:
                return node
        elif isinstance(node_type, str) and node_type.lower() == "jobposting":
            return node
        if "@graph" in node:
            graph = node["@graph"]
            if isinstance(graph, list):
                job = _extract_job_from_json_ld(graph)
                if job:
                    return job
    return {}


def _extract_company(job: Dict[str, Any], soup: BeautifulSoup) -> Optional[str]:
    org = job.get("hiringOrganization") if job else None
    if isinstance(org, dict):
        name = org.get("name")
        if name:
            return name
    meta_site_name = _meta_content(soup, ["og:site_name"]) or _meta_content(soup, ["application-name"])
    if meta_site_name:
        return meta_site_name
    return None


def _extract_hiring_manager(job: Dict[str, Any], soup: BeautifulSoup) -> Optional[str]:
    contact = job.get("contactPoint") if job else None
    if isinstance(contact, dict):
        return contact.get("name")
    # Look for "hiring manager" text in the page as a naive fallback
    text = soup.get_text(" ", strip=True)
    match = re.search(r"Hiring Manager[:\-\s]+([A-Z][A-Za-z\s]+)", text)
    if match:
        return match.group(1).strip()
    return None


def _extract_location(job: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    location_data = None
    if job:
        job_location = job.get("jobLocation")
        if isinstance(job_location, list) and job_location:
            location_data = job_location[0]
        elif isinstance(job_location, dict):
            location_data = job_location
    if isinstance(location_data, dict):
        address = location_data.get("address")
        if isinstance(address, dict):
            city = address.get("addressLocality")
            region = address.get("addressRegion")
            country = address.get("addressCountry")
            return city, region, country, None
        if isinstance(location_data.get("address"), str):
            raw = str(location_data.get("address"))
            city, region, country = _split_location_text(raw)
            return city, region, country, raw

    return None, None, None, None


def _split_location_text(value: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], None
    if len(parts) == 1:
        return parts[0], None, None
    return None, None, None


def _meta_content(soup: BeautifulSoup, names: list[str]) -> Optional[str]:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None
