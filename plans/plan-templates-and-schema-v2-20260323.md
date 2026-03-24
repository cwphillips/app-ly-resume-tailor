# Plan: Template System + Schema v2
Created: 2026-03-23
Status: Draft

---

## Table of Contents
1. [Overview](#overview)
2. [Goals](#goals)
3. [What Changes and Why](#what-changes-and-why)
4. [Detailed File-by-File Changes](#detailed-file-by-file-changes)
5. [New Data Structures](#new-data-structures)
6. [User-Facing Behaviour](#user-facing-behaviour)
7. [Invariants and Constraints](#invariants-and-constraints)
8. [Test Plan](#test-plan)
9. [What Is Explicitly Out of Scope](#what-is-explicitly-out-of-scope)

---

## Overview

This plan covers a set of related schema improvements and the introduction of a
render-time template system. All changes are backwards-compatible with the existing
generation pipeline — the LLM call signature and the Streamlit session state keys
are preserved. The template system is render-time only (Option B): users generate
once and can switch templates and re-download without any additional API calls.

---

## Goals

1. **Skill grouping** — replace the flat `list[str]` with grouped categories, capped
   by a configurable maximum number of groups.
2. **Date normalisation** — enforce `"MMM YYYY"` format (e.g. `"Jan 2022"`) across all
   date fields via Field descriptions baked into the tool schema the LLM receives.
3. **Optional experience location** — `ExperienceEntry.location` becomes
   `Optional[str] = None`.
4. **New sections** — add `CertificationEntry` and `ProjectEntry` models; add optional
   `certifications` and `projects` fields to `ResumeBodyJSON`.
5. **Skipped-section feedback** — add `skipped_sections: list[str]` to `ResumeBodyJSON`
   so the LLM can signal which optional sections it omitted and why; surface this in
   the UI as an `st.info` callout.
6. **Template system** — introduce a `templates/` module with a `Section` enum, a
   `Template` dataclass, and three built-in templates. The DOCX exporter iterates
   `template.sections` in order; any section whose data is `None` is silently skipped.
   A template selector appears in the results area after generation (no re-generation
   needed to switch templates).

---

## What Changes and Why

### `models/schemas.py`

**Why:** The schema is the single source of truth for both Python validation and the
Anthropic tool definition. All structural changes to what the LLM produces must start
here.

| Change | Reason |
|--------|--------|
| Add `SkillGroup` model | Enables grouped/categorised skill display |
| `ResumeBodyJSON.skills` → `list[SkillGroup]` | Replaces flat list |
| `ExperienceEntry.location` → `Optional[str] = None` | Not all roles have a listed location |
| Add `"MMM YYYY"` to all date Field descriptions | Normalises LLM output format |
| Add `CertificationEntry` model | New optional section |
| Add `ProjectEntry` model | New optional section |
| Add `ResumeBodyJSON.certifications: Optional[list[CertificationEntry]] = None` | Optional — omitted if source material absent |
| Add `ResumeBodyJSON.projects: Optional[list[ProjectEntry]] = None` | Optional — omitted if source material absent |
| Add `ResumeBodyJSON.skipped_sections: list[str] = []` | LLM signals which optional sections it omitted and why |
| Regenerate `TAILORING_TOOL` (auto — derived from schema) | Picks up all of the above automatically |

---

### `templates/` (new module)

**Why:** Templates are the mechanism by which section order and inclusion are
controlled at render time, without touching the LLM output or the schema.

New files:
- `templates/__init__.py` — empty package marker
- `templates/library.py` — contains `Section` enum, `Template` dataclass, and the
  built-in template registry

**`Section` enum** — one value per renderable section:
```
SUMMARY | EXPERIENCE | SKILLS | EDUCATION | CERTIFICATIONS | PROJECTS
```

**`Template` dataclass:**
```python
@dataclass
class Template:
    id: str
    name: str
    description: str
    sections: list[Section]       # ordered; controls render order and inclusion
    max_skill_groups: int | None  # None = no cap
```

**Built-in templates:**

| ID | Name | Section order | Skill group cap |
|----|------|---------------|-----------------|
| `standard` | Standard | Summary → Experience → Skills → Education | 5 |
| `technical` | Technical | Summary → Skills → Experience → Projects → Education | 6 |
| `recent_grad` | Recent Graduate | Summary → Education → Experience → Skills → Projects | 4 |

`standard` is the default (pre-selected in the UI).

**Template registry:**
```python
TEMPLATES: dict[str, Template] = { "standard": ..., "technical": ..., "recent_grad": ... }
DEFAULT_TEMPLATE = TEMPLATES["standard"]
```

---

### `exporters/docx.py`

**Why:** The exporter is the only place rendering decisions are made. It must become
template-aware and gain renderers for the two new sections.

| Change | Detail |
|--------|--------|
| `render(resume, contact)` → `render(resume, contact, template)` | Accepts a `Template`; iterates `template.sections` in order |
| Section dispatch | A `dict[Section, Callable]` maps each `Section` to its render function; unknown/None sections are skipped silently |
| Updated skills renderer | Renders `list[SkillGroup]` as `"Category: skill1, skill2, ..."` per line, capped at `template.max_skill_groups` groups |
| New certifications renderer | `Name — Issuer \| Date` (date omitted if None) |
| New projects renderer | Name (bold) + description + technologies line + bullets |

The existing section renderers (summary, experience, education) are otherwise unchanged.

---

### `agents/tailoring.py`

**Why:** The system prompt must be updated to reflect the new schema fields and
instruct the model correctly on optional sections and date formatting.

| Change | Detail |
|--------|--------|
| Update `SYSTEM_PROMPT` | Add date format rule: *"All dates must use 'MMM YYYY' format (e.g. 'Jan 2022'). For current roles use 'Present'."* |
| Update `SYSTEM_PROMPT` | Add optional section rule: *"Only populate `certifications` if the source material explicitly lists certifications or credentials. Only populate `projects` if the source material explicitly describes projects. If there is insufficient content for an optional section, set it to null and add its name to `skipped_sections`."* |
| Update `SYSTEM_PROMPT` | Update ATS section names list to include Certifications and Projects |
| No changes to `run()` signature | Template is render-time only; agents are template-unaware |

---

### `app.py`

**Why:** The UI needs a template selector and must surface the `skipped_sections`
callout. The export section must pass the selected template to the exporter.

| Change | Detail |
|--------|--------|
| Add `"selected_template_id"` to session state defaults | Persists the user's template choice across reruns; reset to `"standard"` on new generation |
| Template tabs | `st.tabs` rendered in the results area after generation — one tab per built-in template, labelled with the template name. The active tab drives both the in-app preview (section order) and the download target. No API call on switch. |
| `_render_resume_preview()` | Accepts `template` parameter; renders sections in `template.sections` order, skipping `None` fields; update skills rendering for `list[SkillGroup]`; add rendering for certifications and projects |
| `_render_skipped_sections()` | New helper — if `resume.skipped_sections` is non-empty, renders an `st.info` callout above the tabs: *"These sections were omitted because your source material didn't contain enough information: [list]. Add that content and regenerate to include them."* |
| `_render_export_buttons()` | Accepts `template` parameter; passes it through to `docx_exporter.render()`; rendered inside each tab so the download always reflects the active tab's template |

---

### `tests/`

**Why:** Schema changes break existing tests; new functionality needs coverage.

| File | Changes |
|------|---------|
| `tests/test_schemas.py` | Update fixtures to use `SkillGroup`; add tests for new models (`CertificationEntry`, `ProjectEntry`); add tests for `skipped_sections` default and population |
| `tests/test_docx_exporter.py` | Update fixtures to use `SkillGroup`; add tests for grouped skills rendering (cap enforced, category labels present); add tests for certifications and projects renderers; add test that `None` sections are skipped silently; add test that template section order is respected |
| `tests/test_input_validation.py` | Update prompt-building helpers to match new schema; no new PII surface area introduced |

---

## New Data Structures

```python
# models/schemas.py additions

class SkillGroup(BaseModel):
    category: str = Field(
        description="Category label, e.g. 'Languages', 'Tools', 'Frameworks', 'Platforms'."
    )
    skills: list[str] = Field(min_length=1)


class CertificationEntry(BaseModel):
    name: str
    issuer: str
    date: Optional[str] = Field(
        default=None,
        description="'MMM YYYY' format (e.g. 'Jun 2023'), or null if unknown."
    )


class ProjectEntry(BaseModel):
    name: str
    description: str = Field(description="One sentence describing the project and its purpose.")
    technologies: list[str] = Field(description="Technologies, languages, and tools used.")
    bullets: list[str] = Field(
        min_length=1,
        description="Achievement-focused bullets. Use action verbs, past tense."
    )
    url: Optional[str] = Field(default=None, description="Project URL or repo link, if public.")


# Updated ResumeBodyJSON fields (additions only):
#   skills: list[SkillGroup]              (replaces list[str])
#   certifications: Optional[list[CertificationEntry]] = None
#   projects: Optional[list[ProjectEntry]] = None
#   skipped_sections: list[str] = []


# templates/library.py

class Section(str, Enum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    SKILLS = "skills"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"
    PROJECTS = "projects"


@dataclass
class Template:
    id: str
    name: str
    description: str
    sections: list[Section]
    max_skill_groups: int | None = None
```

---

## User-Facing Behaviour

### Generation (unchanged)
User fills inputs → clicks Generate → pipeline runs as today → `ResumeBodyJSON` stored
in session state. If optional sections lack source content, the LLM returns `null` for
those fields and lists them in `skipped_sections`.

### Post-generation (new)
After generation, the results area shows:

1. **Skipped sections callout** (if `skipped_sections` non-empty), above the tabs:
   > ℹ️ These sections were not included because your source material didn't contain
   > enough information: **Projects**, **Certifications**. Add that content to your
   > resume text and regenerate to include them.

2. **Template tabs** — one tab per built-in template:
   ```
   [ Standard ] [ Technical ] [ Recent Graduate ]

     Summary                   ← preview renders in this template's section order
     Experience
     Skills
     Education

     [ Download DOCX ]
   ```
   Clicking a tab instantly switches both the preview and the download — no API call,
   no spinner. The active tab is the selected template.

3. **Download button** — lives inside each tab; always reflects that tab's template.
   PDF/ODT buttons (if LibreOffice available) also inside the tab.

### Template switching
- Switching tabs does not trigger regeneration.
- The `skipped_sections` callout is shown once above all tabs and remains visible
  regardless of which tab is active.
- If a template includes a section (e.g. PROJECTS) but that field is `None` in the
  resume body, it is silently omitted from both the preview and the DOCX — the
  template defines *preferred* order and inclusion, not a guarantee.
- The review panel (score, strengths, concerns, suggestions) sits alongside the tabs
  and is template-independent — it always reflects the most recently generated resume.

---

## Invariants and Constraints

These must hold after all changes:

- **PII boundary is unchanged.** `ContactFields` is still never passed to any agent.
- **Template is render-time only.** No agent function signature changes; no template
  data appears in any LLM prompt.
- **Skill group cap is enforced in the exporter, not the schema.** The schema accepts
  any number of groups; the cap is applied at render time per template.
- **`skipped_sections` is informational only.** The exporter does not read it — it
  reads the actual field values (`None` check). The callout is purely UI.
- **All 34 existing tests must continue to pass** after fixture updates.

---

## Test Plan

### New unit tests

| Test | File | What it verifies |
|------|------|-----------------|
| `SkillGroup` rejects empty skills list | `test_schemas.py` | min_length=1 enforced |
| `CertificationEntry` optional date | `test_schemas.py` | date=None accepted |
| `ProjectEntry` rejects empty bullets | `test_schemas.py` | min_length=1 enforced |
| `skipped_sections` defaults to `[]` | `test_schemas.py` | default_factory correct |
| Grouped skills render as `"Category: s1, s2"` | `test_docx_exporter.py` | category labels present in DOCX |
| `max_skill_groups` cap respected | `test_docx_exporter.py` | excess groups absent from DOCX |
| Certifications section renders when present | `test_docx_exporter.py` | cert name + issuer in DOCX |
| Projects section renders when present | `test_docx_exporter.py` | project name + bullets in DOCX |
| `None` section silently skipped | `test_docx_exporter.py` | no error; section header absent |
| Template section order respected | `test_docx_exporter.py` | paragraph order matches template |
| Standard template omits Projects | `test_docx_exporter.py` | Projects header absent from Standard DOCX |
| Technical template includes Projects | `test_docx_exporter.py` | Projects header present in Technical DOCX |

### Updated existing tests
- `test_resume_body_empty_skills_rejected` — update fixture to use `SkillGroup`
- `test_skills_in_docx` — update fixture; assert category label present
- `test_rationale_absent_from_docx` — no change needed
- `test_tailoring_prompt_*` — update prompt-builder helpers to match new schema shape

---

## What Is Explicitly Out of Scope

- Custom user-defined templates (future work)
- Per-template DOCX styling differences (font, colours, margins — all templates use
  the same visual style for now; only content order/inclusion differs)
- File upload for source material (deferred from original PRD)
- Streaming LLM output
