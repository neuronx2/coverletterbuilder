import html
from pathlib import Path

import streamlit as st
import yaml
from jinja2 import Template
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

PROFILE_FILE = Path("profile.yaml")
DEGREES_FILE = Path("degrees.yaml")
CERTIFICATIONS_FILE = Path("certifications.yaml")
SKILL_BLOCKS = [
    {"id": "intro", "label": "Intro & skills", "context_key": "skills_intro", "path": Path("skills_intro.yaml")},
    {"id": "market_dev", "label": "Job block A", "context_key": "skills_job_block_a", "path": Path("skills_job_block_a.yaml")},
    {"id": "senior_bi", "label": "Job block B", "context_key": "skills_job_block_b", "path": Path("skills_job_block_b.yaml")},
    {"id": "project_manager", "label": "Job block C", "context_key": "skills_job_block_c", "path": Path("skills_job_block_c.yaml")},
    {"id": "business_analytics", "label": "Job block D", "context_key": "skills_job_block_d", "path": Path("skills_job_block_d.yaml")},
    {"id": "fpna", "label": "Job block E", "context_key": "skills_job_block_e", "path": Path("skills_job_block_e.yaml")},
]
SKILL_BLOCK_MAP = {block["id"]: block for block in SKILL_BLOCKS}


# ----------------- Helpers ----------------- #

def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _load_list_from_file(path: Path, key: str) -> list[str] | None:
    if not path.exists():
        return None
    data = _load_yaml(path)
    values = data.get(key, [])
    if isinstance(values, list):
        return values
    return None


def _load_skill_sources() -> dict[str, list[str]]:
    sources: dict[str, list[str]] = {}
    for block in SKILL_BLOCKS:
        sources[block["id"]] = _load_list_from_file(block["path"], "skills") or []
    return sources


def load_profile():
    profile = _load_yaml(PROFILE_FILE)

    degrees = _load_list_from_file(DEGREES_FILE, "degrees")
    certifications = _load_list_from_file(CERTIFICATIONS_FILE, "certifications")

    profile["degrees"] = degrees if degrees is not None else profile.get("degrees", []) or []
    profile["certifications"] = (
        certifications if certifications is not None else profile.get("certifications", []) or []
    )
    return profile


def load_template():
    with open("template.txt", "r", encoding="utf-8") as f:
        return Template(f.read(), trim_blocks=True, lstrip_blocks=True)


def build_candidate_lines(context: dict[str, str], sections_state: dict[str, bool]) -> list[str]:
    lines: list[str] = []
    if not sections_state.get("candidate_block"):
        return lines
    for key in ("name", "address_line1", "address_line2"):
        value = context.get(key)
        if value:
            lines.append(value.strip())
    home_location = context.get("home_location")
    if home_location:
        lines.append(home_location)
    return lines


def extract_candidate_lines_from_text(text: str, default_lines: list[str]) -> tuple[list[str], int]:
    if not default_lines:
        return [], 0
    lines = text.split("\n")
    collected: list[str] = []
    consumed = 0
    started = False
    for line in lines:
        if not started and not line.strip():
            consumed += 1
            continue
        if not started:
            started = True
        if line.startswith(" "):
            collected.append(line.strip())
            consumed += 1
            continue
        if not line.strip() and collected:
            consumed += 1
            continue
        break
    if collected:
        return collected, consumed
    return default_lines, len(default_lines)



def _split_blocks(text: str, skip_lines: int = 0) -> list[list[str]]:
    blocks: list[list[str]] = []
    lines = text.split("\n")
    remaining = lines[skip_lines:]
    while remaining and not remaining[0].strip():
        remaining.pop(0)
    current: list[str] = []
    for line in remaining:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line.rstrip())
    if current:
        blocks.append(current)
    return blocks


def assemble_text_value(
    candidate_lines: list[str], blocks: list[list[str]], include_company_block: bool
) -> str:
    """Rebuild editable text with consistent spacing."""

    text_blocks: list[str] = []
    block_index = 0
    if candidate_lines:
        if include_company_block and blocks:
            combined = candidate_lines + blocks[0]
            text_blocks.append("\n".join(combined))
            block_index = 1
        else:
            text_blocks.append("\n".join(candidate_lines))

    for block in blocks[block_index:]:
        block_text = "\n".join(block).strip("\n")
        if block_text:
            text_blocks.append(block_text)

    return "\n\n".join(text_blocks).strip()


def build_docx(
    text: str,
    sections_state: dict[str, bool],
    candidate_lines: list[str],
    candidate_line_consumed: int,
) -> BytesIO:
    """
    Create an in-memory .docx file from the cover letter text.
    """
    doc = Document()
    candidate_count = len(candidate_lines) if sections_state.get("candidate_block") else 0
    blocks = _split_blocks(text, skip_lines=candidate_line_consumed if candidate_count else 0)

    def add_block(lines: list[str], align_right: bool = False) -> None:
        for line in lines:
            paragraph = doc.add_paragraph(line.strip() if align_right else line)
            if align_right:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.line_spacing = 1

    if candidate_count:
        add_block(candidate_lines, align_right=True)

    for idx, block in enumerate(blocks):
        add_block(block)
        if idx < len(blocks) - 1:
            spacer = doc.add_paragraph("")
            spacer.paragraph_format.space_after = Pt(0)
            spacer.paragraph_format.space_before = Pt(0)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def build_pdf(
    text: str,
    sections_state: dict[str, bool],
    candidate_lines: list[str],
    candidate_line_consumed: int,
) -> BytesIO:
    """Create an in-memory PDF using ReportLab platypus for better layout control."""

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=72,
        rightMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    candidate_count = len(candidate_lines) if sections_state.get("candidate_block") else 0
    blocks = _split_blocks(text, skip_lines=candidate_line_consumed if candidate_count else 0)

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=0,
        spaceAfter=8,
    )
    candidate_style = ParagraphStyle(
        "Candidate",
        parent=body_style,
        alignment=TA_RIGHT,
        spaceAfter=6,
    )

    story: list = []

    def para_text(lines: list[str]) -> str:
        return "<br/>".join(html.escape(line) if line.strip() else "&nbsp;" for line in lines)

    if candidate_count:
        story.append(Paragraph(para_text(candidate_lines), candidate_style))

    for idx, block in enumerate(blocks):
        story.append(Paragraph(para_text(block), body_style))

    if not story:
        story.append(Paragraph("", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


def _render_skill_selector(block_id: str, label: str, base_options: list[str]) -> list[str]:
    """Render a skills multiselect with add/remove helpers for a specific block."""
    st.markdown(f"**{label}**")
    custom_key = f"{block_id}_custom_skills"
    selection_key = f"{block_id}_skills_selection"
    input_key = f"{block_id}_skill_input"
    add_button_key = f"{block_id}_add_skill_button"
    select_all_key = f"{block_id}_select_all_skills"
    clear_key = f"{block_id}_clear_skills"

    st.session_state.setdefault(custom_key, [])

    new_skill = st.text_input(
        f"Add custom skill for {label}",
        key=input_key,
        placeholder="e.g., Commercial Strategy",
    )
    if st.button("➕ Add skill", key=add_button_key):
        value = new_skill.strip()
        if value:
            custom_entries = st.session_state[custom_key]
            if value not in base_options and value not in custom_entries:
                custom_entries.append(value)
                st.session_state[custom_key] = custom_entries
            current_selection = st.session_state.get(selection_key, [])
            if value not in current_selection:
                st.session_state[selection_key] = current_selection + [value]
        st.session_state[input_key] = ""
        st.experimental_rerun()

    options = base_options + [entry for entry in st.session_state[custom_key] if entry not in base_options]

    if selection_key not in st.session_state:
        st.session_state[selection_key] = list(options)
    else:
        st.session_state[selection_key] = [item for item in st.session_state[selection_key] if item in options]

    btn_cols = st.columns(2)
    if btn_cols[0].button("Select all", key=select_all_key):
        st.session_state[selection_key] = list(options)
    if btn_cols[1].button("Clear", key=clear_key):
        st.session_state[selection_key] = []

    st.multiselect(
        f"Skills to include ({label})",
        options=options,
        key=selection_key,
        help="Pick only the skills you want to mention in this block.",
    )
    return st.session_state.get(selection_key, [])


# ----------------- Streamlit UI ----------------- #

st.set_page_config(page_title="Cover Letter Lego Builder", layout="wide")

st.title("Cover Letter Lego Builder")

profile = load_profile()
template = load_template()

JOB_FIELDS = ("company", "position", "hiring_manager", "city", "region", "country")
for field in JOB_FIELDS:
    st.session_state.setdefault(f"{field}_input", profile.get(field, ""))

candidate_expander = st.sidebar.expander("Candidate Details", expanded=False)
with candidate_expander:
    full_name = st.text_input("Full Name", value="Full Name", placeholder="Full Name", key="candidate_full_name")
    candidate_address = st.text_input("Address", value="Address", placeholder="Address", key="candidate_address")
    candidate_city = st.text_input("City", value="City", placeholder="City", key="candidate_city")
    candidate_region = st.text_input("Region", value="Region/State", placeholder="Region/State", key="candidate_region")
    candidate_country = st.text_input("Country", value="Country", placeholder="Country", key="candidate_country")

home_city = candidate_city.strip() or profile.get("city", "")
home_region = candidate_region.strip() or profile.get("region", "")
home_country = candidate_country.strip() or profile.get("country", "")
home_location = ", ".join([part for part in (home_city, home_region, home_country) if part])

company_expander = st.sidebar.expander("Company Details", expanded=False)
with company_expander:
    company_value = st.text_input("Company Name", value="Company Name", placeholder="Company Name", key="company_name")
    position_value = st.text_input("Job Title / Position", value="Job Title", placeholder="Job Title", key="company_position")
    hiring_manager_value = st.text_input("Hiring manager", value="Hiring Manager", placeholder="Hiring Manager", key="company_hiring_manager")
    city_value = st.text_input("City", value="City", placeholder="City", key="company_city")
    region_value = st.text_input("Region", value="Region/State", placeholder="Region/State", key="company_region")
    country_value = st.text_input("Country", value="Country", placeholder="Country", key="company_country")
    awareness = st.text_input(
        "How did you hear about the role?",
        value="a LinkedIn post",
        placeholder="a LinkedIn post",
        key="company_awareness",
    )

sections_expander = st.sidebar.expander("Text Blocks", expanded=False)
with sections_expander:
    sections = {
        "candidate_block": st.checkbox("Candidate block", True),
        "company_block": st.checkbox("Company block", True),
        "subject_block": st.checkbox("Subject block", True),
        "greeting_block": st.checkbox("Greeting block", True),
        "intro": st.checkbox("Intro & skills", True),
        "market_dev": st.checkbox("Job block A", True),
        "senior_bi": st.checkbox("Job block B", True),
        "project_manager": st.checkbox("Job block C", True),
        "business_analytics": st.checkbox("Job block D", True),
        "fpna": st.checkbox("Job block E", True),
        "degrees_certs": st.checkbox("Degrees & Certifications", True),
        "languages_company": st.checkbox("Languages & why this company", True),
        "goodbye_block": st.checkbox("Goodbye block", True),
    }

degrees_source = profile.get("degrees", [])
certifications_source = profile.get("certifications", [])
skills_sources = _load_skill_sources()

qualifications_expander = st.sidebar.expander("Qualifications & Credentials", expanded=False)
with qualifications_expander:
    st.caption("Choose which degrees and certifications appear in the generated letter or add custom entries.")

    # Degrees management
    st.session_state.setdefault("custom_degree_entries", [])
    st.markdown("**Degrees**")
    new_degree = st.text_input("Add custom degree", key="degree_add_input", placeholder="e.g., MSc Big Data & Analytics")
    if st.button("➕ Add degree", key="add_degree_button"):
        value = new_degree.strip()
        if value:
            if value not in degrees_source and value not in st.session_state["custom_degree_entries"]:
                st.session_state["custom_degree_entries"].append(value)
            current_selection = st.session_state.get("degrees_selection", [])
            if value not in current_selection:
                st.session_state["degrees_selection"] = current_selection + [value]
        st.session_state.degree_add_input = ""
        st.experimental_rerun()
    degree_options = degrees_source + st.session_state["custom_degree_entries"]
    if "degrees_selection" not in st.session_state:
        st.session_state["degrees_selection"] = list(degree_options)
    else:
        st.session_state["degrees_selection"] = [
            degree for degree in st.session_state["degrees_selection"] if degree in degree_options
        ]
    degree_button_cols = st.columns(2)
    if degree_button_cols[0].button("Select all degrees", key="select_all_degrees_button"):
        st.session_state["degrees_selection"] = list(degree_options)
    if degree_button_cols[1].button("Clear degrees", key="clear_degrees_button"):
        st.session_state["degrees_selection"] = []
    st.multiselect(
        "Degrees to include",
        options=degree_options,
        key="degrees_selection",
        help="These entries feed the 'I hold ...' sentence.",
    )

    st.markdown("---")

    # Certifications management
    st.session_state.setdefault("custom_cert_entries", [])
    st.markdown("**Certifications**")
    new_cert = st.text_input("Add custom certification", key="cert_add_input", placeholder="e.g., Six Sigma Black Belt")
    if st.button("➕ Add certification", key="add_cert_button"):
        value = new_cert.strip()
        if value:
            if value not in certifications_source and value not in st.session_state["custom_cert_entries"]:
                st.session_state["custom_cert_entries"].append(value)
            current_certs = st.session_state.get("certifications_selection", [])
            if value not in current_certs:
                st.session_state["certifications_selection"] = current_certs + [value]
        st.session_state.cert_add_input = ""
        st.experimental_rerun()
    cert_options = certifications_source + st.session_state["custom_cert_entries"]
    if "certifications_selection" not in st.session_state:
        st.session_state["certifications_selection"] = list(cert_options)
    else:
        st.session_state["certifications_selection"] = [
            cert for cert in st.session_state["certifications_selection"] if cert in cert_options
        ]
    cert_button_cols = st.columns(2)
    if cert_button_cols[0].button("Select all certifications", key="select_all_cert_button"):
        st.session_state["certifications_selection"] = list(cert_options)
    if cert_button_cols[1].button("Clear certifications", key="clear_cert_button"):
        st.session_state["certifications_selection"] = []
    st.multiselect(
        "Certifications to include",
        options=cert_options,
        key="certifications_selection",
        help="Pick only the credentials you want to highlight.",
    )

skills_expander = st.sidebar.expander("Skills by Block", expanded=False)
selected_skills_map: dict[str, list[str]] = {}
with skills_expander:
    st.caption("Use the controls below to add, remove, or reorder skills for each text block.")
    for idx, block in enumerate(SKILL_BLOCKS):
        block_id = block["id"]
        base_options = skills_sources.get(block_id, [])
        selected = _render_skill_selector(block_id, block["label"], base_options)
        selected_skills_map[block["context_key"]] = selected
        if idx < len(SKILL_BLOCKS) - 1:
            st.markdown("---")

selected_degrees = st.session_state.get("degrees_selection", degrees_source) or []
selected_certifications = st.session_state.get("certifications_selection", certifications_source) or []

contact_defaults = profile.get("contact_links", [])

def _sanitize_contact(entry: dict[str, str] | str, fallback_label: str) -> dict[str, str]:
    if isinstance(entry, dict):
        return {
            "label": entry.get("label") or fallback_label,
            "value": entry.get("value", ""),
        }
    if isinstance(entry, str):
        return {"label": fallback_label, "value": entry}
    return {"label": fallback_label, "value": ""}


def _build_default_contacts(raw_defaults: list) -> list[dict[str, str]]:
    fallback_labels = ["Email", "LinkedIn", "Xing", "Website"]
    defaults: list[dict[str, str]] = []
    if not raw_defaults:
        return defaults
    for idx, item in enumerate(raw_defaults):
        fallback = fallback_labels[idx] if idx < len(fallback_labels) else f"Contact {idx + 1}"
        defaults.append(_sanitize_contact(item, fallback))
    return defaults

if "contact_entries" not in st.session_state:
    defaults = _build_default_contacts(contact_defaults)
    if defaults:
        st.session_state.contact_entries = defaults
    else:
        st.session_state.contact_entries = [
            {"label": "Email", "value": profile.get("applicant", {}).get("email", "")}
        ]

custom_expander = st.sidebar.expander("Contact Details", expanded=False)
with custom_expander:
    remove_indices: list[int] = []
    header_cols = st.columns([1.1, 2.2, 0.4])
    header_cols[0].markdown("**Label**")
    header_cols[1].markdown("**Value**")
    header_cols[2].markdown(" ")

    for idx, entry in enumerate(st.session_state.contact_entries):
        cols = st.columns([1.1, 2.2, 0.4])
        label_key = f"contact_label_{idx}"
        value_key = f"contact_value_{idx}"
        label_value = cols[0].text_input(
            "Label",
            entry["label"],
            key=label_key,
            label_visibility="collapsed",
        )
        value_value = cols[1].text_input(
            "Value",
            entry["value"],
            key=value_key,
            label_visibility="collapsed",
        )
        st.session_state.contact_entries[idx] = {
            "label": label_value.strip() or "Label",
            "value": value_value.strip(),
        }
        if cols[2].button("🗑️", key=f"contact_remove_{idx}") and len(st.session_state.contact_entries) > 1:
            remove_indices.append(idx)

    if remove_indices:
        for idx in sorted(remove_indices, reverse=True):
            st.session_state.contact_entries.pop(idx)

    add_col1, add_col2 = st.columns([1, 1])
    if add_col1.button("➕ Add contact"):
        st.session_state.contact_entries.append({"label": f"Contact {len(st.session_state.contact_entries) + 1}", "value": ""})
    if add_col2.button("↻ Reset"):
        defaults = _build_default_contacts(contact_defaults)
        st.session_state.contact_entries = defaults or [
            {"label": "Email", "value": profile.get("applicant", {}).get("email", "")}
        ]

contact_links = [
    entry
    for entry in st.session_state.contact_entries
    if entry.get("value")
]

# Use sidebar inputs for job information
job_info = {
    "company": company_value.strip(),
    "position": position_value.strip(),
    "hiring_manager": hiring_manager_value.strip(),
    "city": city_value.strip(),
    "region": region_value.strip(),
    "country": country_value.strip(),
}

profile_for_context = {**profile}
profile_for_context.update(
    {
        "name": full_name.strip() or profile.get("name", ""),
        "address_line1": candidate_address.strip() or profile.get("address_line1", ""),
        "city": home_city,
        "region": home_region,
        "country": home_country,
    }
)
profile_for_context["degrees"] = selected_degrees
profile_for_context["certifications"] = selected_certifications
for block in SKILL_BLOCKS:
    ctx_key = block["context_key"]
    profile_for_context[ctx_key] = selected_skills_map.get(ctx_key, skills_sources.get(block["id"], []))

# Merge everything into a single context for the template
context = {
    **profile_for_context,
    **job_info,
    "hiring_manager": job_info.get("hiring_manager") or None,
    "awareness_source": awareness,
    "sections": sections,
    "home_city": home_city,
    "home_region": home_region,
    "home_country": home_country,
    "home_location": home_location,
    "contact_links": contact_links or profile.get("contact_links", []),
}

candidate_lines_plain = build_candidate_lines(context, sections)

# Render the cover letter
rendered_text = template.render(**context)
if sections.get("candidate_block") and sections.get("company_block"):
    rendered_text = rendered_text.replace("\n\n", "\n", 1)

preview_candidate_lines, preview_consumed = extract_candidate_lines_from_text(
    rendered_text, candidate_lines_plain
)
preview_blocks = _split_blocks(
    rendered_text,
    skip_lines=preview_consumed if preview_candidate_lines else 0,
)

text_area_value = assemble_text_value(
    preview_candidate_lines,
    preview_blocks,
    bool(sections.get("company_block")),
)
if not text_area_value:
    text_area_value = rendered_text

preview_parts = []
if preview_candidate_lines:
    preview_parts.append(
        "<div style='text-align:right;'>" + "<br>".join(html.escape(line) for line in preview_candidate_lines) + "</div>"
    )
for block in preview_blocks:
    preview_parts.append(
        "<div style='text-align:left;'>"
        + "<br>".join(html.escape(line) for line in block)
        + "</div>"
    )
preview_html = (
    "<div style='font-family: "
    "Courier New, monospace; white-space: pre-wrap; border:1px solid #ddd; padding:1rem; background:#f8f9fb;'>"
    + "<div style='display:flex; flex-direction:column; gap:1rem;'>"
    + "".join(preview_parts)
    + "</div></div>"
)

st.subheader("Cover letter text")
edited_text = st.text_area(
    "You can edit the text before downloading:",
    value=text_area_value,
    height=450,
)

st.markdown("**Preview (A4 layout)**")
st.markdown(preview_html, unsafe_allow_html=True)

default_export_name = " - ".join(
    filter(
        None,
        [
            company_value.strip(),
            position_value.strip(),
            context.get("today"),
        ],
    )
) or "cover_letter"
export_name_input = st.text_input(
    "File name (without extension)",
    value=default_export_name,
    key="export_filename",
)
export_name = export_name_input.strip() or default_export_name

candidate_lines_for_export, consumed_candidate_lines = extract_candidate_lines_from_text(
    edited_text, candidate_lines_plain
)

col1, col2 = st.columns(2)

with col1:
    docx_file = build_docx(
        edited_text,
        sections,
        candidate_lines_for_export,
        consumed_candidate_lines,
    )
    st.download_button(
        "Download as Word (.docx)",
        data=docx_file,
        file_name=f"{export_name}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

with col2:
    pdf_file = build_pdf(
        edited_text,
        sections,
        candidate_lines_for_export,
        consumed_candidate_lines,
    )
    st.download_button(
        "Download as PDF (.pdf)",
        data=pdf_file,
        file_name=f"{export_name}.pdf",
        mime="application/pdf",
    )

st.caption(
    "Tip: Update 'profile.yaml' for reusable info like contact links, tweak 'degrees.yaml' / 'certifications.yaml' "
    "for credentials, and edit the 'skills_*.yaml' files to set default skills per block."
)
