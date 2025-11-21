# Cover Letter Generator (lego-style)

Generate a plug-and-play cover letter that adapts to any job posting. Each paragraph is treated as a "lego" section that you can enable, disable, or edit individually.

## Features
- Pulls company, position, and location details from a job-posting URL via JSON-LD metadata.
- Uses your reusable lists for degrees, certifications, skills, stakeholders, presentations, and teams.
- Lets you pass job-specific company features and highlighted skills at runtime.
- Sections are separate Jinja templates so you can edit body text or add/delete pieces without touching Python code.

## Project layout
```
config/
  profile.sample.json   # copy to profile.json and customize
  sections.json         # order + toggle of lego sections
cover_letter_generator/ # Python package + CLI entry point
templates/sections/     # each paragraph lives here (lego piece)
output/                 # generated cover letters land here
```

## Setup
1. (Optional but recommended) create a virtual environment.
2. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
3. Copy and edit the profile template:
   ```bash
   cp config/profile.sample.json config/profile.json
   ```
   Update `applicant` info plus each list (degrees, certifications, skills, stakeholders, presented_to, teams). These lists feed the placeholders `degree1…`, `certi1…`, `skill1…`, etc.

## Configure lego sections
- `config/sections.json` controls which sections render and their order. Set `"enabled": false` to hide a block or duplicate an entry to reuse a template.
- Edit or add templates under `templates/sections/`. Each file is standard Markdown with Jinja placeholders such as `{{ company }}` or `{{ skill1 }}`. Create a new file, add it to `sections.json`, and it becomes another lego piece.

## Usage
```
python3 -m cover_letter_generator \
  --job-url "https://jobs.example.com/awesome-role" \
  --profile config/profile.json \
  --sections config/sections.json \
  --templates templates \
  --output output/awesome-role.md \
  --company-feature "AI-driven roadmap" \
  --company-feature "Customer trust" \
  --skill "Go-to-market orchestration"
```
Arguments of note:
- `--company-feature` and `--skill` can be repeated per job. If omitted, defaults from `profile.json` are used.
- `--*-count` flags control how many items to pull from your lists (e.g., `--cert-count 3`).
- `--format text` switches the joiner from blank-line Markdown to single newline.
- `--overrides overrides.json` lets you supply manual fields when a posting omits them:
  ```json
  {
    "company": "Acme Robotics",
    "hiring_manager": "Jordan Blake",
    "city": "Austin",
    "region": "TX",
    "country": "USA"
  }
  ```

## Adding or editing lego pieces
1. Duplicate any file in `templates/sections/` (e.g., `07_metrics.j2`).
2. Edit the text and placeholders as needed.
3. Reference it in `config/sections.json` (position in the array controls order).
4. Run the CLI again—no Python edits required.

## Notes
- Job postings vary: if the script cannot auto-detect hiring manager or location it falls back to defaults or anything you pass in an overrides file.
- All generated letters land in the `output/` folder so they never overwrite templates or configs.
