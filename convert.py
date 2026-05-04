#!/usr/bin/env python3
"""Convert a Markdown survey specification to a Qualtrics Survey Format (QSF) file.

Usage:
    python convert.py survey.md
    python convert.py survey.md -o output.qsf

See SURVEY_SPEC.md for the markdown format.
"""

import argparse
import json
import random
import re
import string
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _rand_id(length: int = 15) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def new_survey_id() -> str:
    return f"SV_{_rand_id()}"


def new_user_id() -> str:
    return f"UR_{_rand_id()}"


def new_rs_id() -> str:
    return f"RS_{_rand_id()}"


def new_block_id() -> str:
    return f"BL_{_rand_id()}"


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

# Map of type string → (QuestionType, Selector, SubSelector or None)
QUESTION_TYPES: dict[str, tuple[str, str, str | None]] = {
    "mc":           ("MC",     "SAVR",  "TX"),
    "mc-multi":     ("MC",     "MAVR",  "TX"),
    "mc-dropdown":  ("MC",     "DL",    "TX"),
    "text":         ("TE",     "SL",    None),
    "text-essay":   ("TE",     "ESTB",  None),
    "matrix":       ("Matrix", "Likert","SingleAnswer"),
    "matrix-multi": ("Matrix", "Likert","MultipleAnswer"),
    "description":  ("DB",     "TB",    None),
}

# Matches: ## Question text [type] or ## Question text [type]*
_QUESTION_RE = re.compile(r"^##\s+(.+?)\s+\[([^\]]+)\]\s*(\*)?\s*$")


def _empty_question(text: str, qtype: str, required: bool) -> dict:
    return {
        "text": text,
        "type": qtype.lower(),
        "required": required,
        "choices": [],
        "rows": [],
        "scale": [],
    }


def parse_survey(text: str) -> dict:
    """Parse a markdown survey spec into a plain Python dict."""
    lines = text.splitlines()
    idx = 0

    # ---- frontmatter ----
    meta: dict = {}
    if lines and lines[0].strip() == "---":
        idx = 1
        fm: list[str] = []
        while idx < len(lines) and lines[idx].strip() != "---":
            fm.append(lines[idx])
            idx += 1
        idx += 1  # skip closing ---
        meta = yaml.safe_load("\n".join(fm)) or {}

    title = str(meta.get("title", "Untitled Survey"))
    language = str(meta.get("language", "EN")).upper()
    description = str(meta.get("description", ""))

    blocks: list[dict] = []
    current_block: dict | None = None
    current_question: dict | None = None

    def flush_question() -> None:
        nonlocal current_question
        if current_question is not None:
            assert current_block is not None
            _validate_question(current_question)
            current_block["questions"].append(current_question)
            current_question = None

    def flush_block() -> None:
        nonlocal current_block
        flush_question()
        if current_block is not None:
            blocks.append(current_block)
            current_block = None

    def ensure_block() -> None:
        nonlocal current_block
        if current_block is None:
            current_block = {"name": "Default Question Block", "questions": []}

    while idx < len(lines):
        line = lines[idx]
        idx += 1

        # H1 → new block
        if re.match(r"^#\s+", line) and not line.startswith("##"):
            flush_block()
            current_block = {"name": line.lstrip("# ").strip(), "questions": []}
            continue

        # H2 → new question
        m = _QUESTION_RE.match(line)
        if m:
            flush_question()
            ensure_block()
            current_question = _empty_question(
                text=m.group(1).strip(),
                qtype=m.group(2).strip(),
                required=m.group(3) == "*",
            )
            continue

        # Page break (--- after frontmatter)
        if line.strip() == "---":
            flush_question()
            ensure_block()
            current_block["questions"].append({"type": "page_break"})  # type: ignore[index]
            continue

        if current_question is None:
            continue

        # scale: line (matrix)
        if line.strip().lower().startswith("scale:"):
            raw = line.strip()[6:].strip()
            current_question["scale"] = [s.strip() for s in raw.split(",") if s.strip()]
            continue

        # bullet → choice or matrix row
        if line.strip().startswith("- "):
            value = line.strip()[2:].strip()
            if current_question["type"].startswith("matrix"):
                current_question["rows"].append(value)
            else:
                current_question["choices"].append(value)
            continue

    flush_block()

    return {
        "title": title,
        "language": language,
        "description": description,
        "blocks": blocks,
    }


def _validate_question(q: dict) -> None:
    qtype = q["type"]
    if qtype.startswith("mc") and not q["choices"]:
        print(f"  Warning: MC question has no choices: \"{q['text'][:60]}\"", file=sys.stderr)
    if qtype.startswith("matrix"):
        if not q["rows"]:
            print(f"  Warning: Matrix question has no rows: \"{q['text'][:60]}\"", file=sys.stderr)
        if not q["scale"]:
            print(f"  Warning: Matrix question has no scale: \"{q['text'][:60]}\"", file=sys.stderr)


# ---------------------------------------------------------------------------
# QSF builder
# ---------------------------------------------------------------------------

def _build_question_payload(q: dict, qid_num: int) -> dict:
    qid = f"QID{qid_num}"
    tag = f"Q{qid_num}"
    text: str = q["text"]
    qtype = q["type"]
    required: bool = q.get("required", False)

    type_info = QUESTION_TYPES.get(qtype, ("TE", "SL", None))
    qt, sel, sub = type_info

    force = "ON" if required else "OFF"

    payload: dict = {
        "QuestionText": text,
        "DataExportTag": tag,
        "QuestionType": qt,
        "Selector": sel,
        "DataVisibility": {"Private": False, "Hidden": False},
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": text[:99],
        "Validation": {
            "Settings": {
                "ForceResponse": force,
                "Type": "None",
            }
        },
        "Language": [],
        "NextChoiceId": 1,
        "NextAnswerId": 1,
    }

    if sub is not None:
        payload["SubSelector"] = sub

    if qt == "MC":
        choices = q.get("choices", [])
        payload["Choices"] = {str(i + 1): {"Display": c} for i, c in enumerate(choices)}
        payload["ChoiceOrder"] = [str(i + 1) for i in range(len(choices))]
        payload["NextChoiceId"] = len(choices) + 1

    if qt == "Matrix":
        rows = q.get("rows", [])
        scale = q.get("scale", [])
        payload["Choices"] = {str(i + 1): {"Display": r} for i, r in enumerate(rows)}
        payload["ChoiceOrder"] = [str(i + 1) for i in range(len(rows))]
        payload["Answers"] = {str(i + 1): {"Display": s} for i, s in enumerate(scale)}
        payload["AnswerOrder"] = [str(i + 1) for i in range(len(scale))]
        payload["NextChoiceId"] = len(rows) + 1
        payload["NextAnswerId"] = len(scale) + 1

    # QuestionID goes last, matching real QSF export order
    payload["QuestionID"] = qid
    return payload


def build_qsf(survey: dict) -> dict:
    survey_id = new_survey_id()
    user_id = new_user_id()
    rs_id = new_rs_id()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    title: str = survey["title"]
    lang: str = survey["language"]

    # Assign QIDs and collect per-block data
    qid_counter = 1
    blocks_data: list[dict] = []
    all_question_pairs: list[tuple[int, dict]] = []

    for i, block in enumerate(survey["blocks"]):
        block_id = new_block_id()
        block_elements: list[dict] = []
        block_question_pairs: list[tuple[int, dict]] = []

        for q in block["questions"]:
            if q["type"] == "page_break":
                block_elements.append({"Type": "Page Break"})
            else:
                qid = f"QID{qid_counter}"
                block_elements.append({"Type": "Question", "QuestionID": qid})
                block_question_pairs.append((qid_counter, q))
                qid_counter += 1

        blocks_data.append({
            "id": block_id,
            "name": block["name"],
            # First block uses "Default"; subsequent blocks use "Standard"
            "block_type": "Default" if i == 0 else "Standard",
            "elements": block_elements,
            "question_pairs": block_question_pairs,
        })
        all_question_pairs.extend(block_question_pairs)

    total_questions = len(all_question_pairs)

    # BL element: real blocks first, trash block last
    bl_payload: list[dict] = []
    for bd in blocks_data:
        bl_payload.append({
            "Type": bd["block_type"],
            "Description": bd["name"],
            "ID": bd["id"],
            "BlockElements": bd["elements"],
        })
    bl_payload.append({
        "Type": "Trash",
        "Description": "Trash / Unused Questions",
        "ID": new_block_id(),
    })

    bl_element = {
        "SurveyID": survey_id,
        "Element": "BL",
        "PrimaryAttribute": "Survey Blocks",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": bl_payload,
    }

    # FL element: no EndOfSurvey entry; Count = len(blocks) + 1 (root)
    flow_counter = 2
    flow_items: list[dict] = []
    for bd in blocks_data:
        flow_items.append({"ID": bd["id"], "Type": "Block", "FlowID": f"FL_{flow_counter}"})
        flow_counter += 1

    fl_element = {
        "SurveyID": survey_id,
        "Element": "FL",
        "PrimaryAttribute": "Survey Flow",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {
            "Flow": flow_items,
            "Properties": {"Count": flow_counter - 1},
            "FlowID": "FL_1",
            "Type": "Root",
        },
    }

    # PROJ element: PrimaryAttribute is "CORE", not "ProjectCategory"
    proj_element = {
        "SurveyID": survey_id,
        "Element": "PROJ",
        "PrimaryAttribute": "CORE",
        "SecondaryAttribute": None,
        "TertiaryAttribute": "1.1.0",
        "Payload": {"ProjectCategory": "CORE", "SchemaVersion": "1.1.0"},
    }

    # QC element
    qc_element = {
        "SurveyID": survey_id,
        "Element": "QC",
        "PrimaryAttribute": "Survey Question Count",
        "SecondaryAttribute": str(total_questions),
        "TertiaryAttribute": None,
        "Payload": None,
    }

    # RS element
    rs_element = {
        "SurveyID": survey_id,
        "Element": "RS",
        "PrimaryAttribute": rs_id,
        "SecondaryAttribute": "Default Response Set",
        "TertiaryAttribute": None,
        "Payload": None,
    }

    # SCO element: PrimaryAttribute is "Scoring" with full scoring fields
    sco_element = {
        "SurveyID": survey_id,
        "Element": "SCO",
        "PrimaryAttribute": "Scoring",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {
            "ScoringCategories": [],
            "ScoringCategoryGroups": [],
            "ScoringSummaryCategory": None,
            "ScoringSummaryAfterQuestions": 0,
            "ScoringSummaryAfterSurvey": 0,
            "DefaultScoringCategory": None,
            "AutoScoringCategory": None,
        },
    }

    # SO element
    so_element = {
        "SurveyID": survey_id,
        "Element": "SO",
        "PrimaryAttribute": "Survey Options",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {
            "BackButton": "false",
            "SaveAndContinue": "true",
            "SurveyProtection": "PublicSurvey",
            "BallotBoxStuffingPrevention": "false",
            "NoIndex": "Yes",
            "SecureResponseFiles": "true",
            "SurveyExpiration": "None",
            "SurveyTermination": "DefaultMessage",
            "Header": "",
            "Footer": "",
            "ProgressBarDisplay": "None",
            "PartialData": "+1 week",
            "ValidationMessage": "",
            "PreviousButton": "",
            "NextButton": "",
            "SurveyTitle": title,
            "SkinLibrary": "qualtrics",
            "SkinType": "templated",
            "Skin": {"brandingId": None, "templateId": "*base", "overrides": None},
            "NewScoring": 1,
            "SurveyMetaDescription": "",
        },
    }

    # SQ elements
    sq_elements = []
    for qid_num, q in all_question_pairs:
        sq_elements.append({
            "SurveyID": survey_id,
            "Element": "SQ",
            "PrimaryAttribute": f"QID{qid_num}",
            "SecondaryAttribute": q["text"][:99],
            "TertiaryAttribute": None,
            "Payload": _build_question_payload(q, qid_num),
        })

    # STAT element
    stat_element = {
        "SurveyID": survey_id,
        "Element": "STAT",
        "PrimaryAttribute": "Survey Statistics",
        "SecondaryAttribute": None,
        "TertiaryAttribute": None,
        "Payload": {"MobileCompatible": True, "ID": "Survey Statistics"},
    }

    return {
        "SurveyEntry": {
            "SurveyID": survey_id,
            "SurveyName": title,
            "SurveyDescription": survey.get("description", "") or None,
            "SurveyOwnerID": user_id,
            "SurveyBrandID": "qualtrics",
            "DivisionID": None,
            "SurveyLanguage": lang,
            "SurveyActiveResponseSet": rs_id,
            "SurveyStatus": "Inactive",
            "SurveyStartDate": "0000-00-00 00:00:00",
            "SurveyExpirationDate": "0000-00-00 00:00:00",
            "SurveyCreationDate": now,
            "CreatorID": user_id,
            "LastModified": now,
            "LastAccessed": "0000-00-00 00:00:00",
            "LastActivated": "0000-00-00 00:00:00",
            "Deleted": None,
        },
        # Element order matches real Qualtrics export: BL, FL, PROJ, QC, RS, SCO, SO, SQ(s), STAT
        "SurveyElements": [
            bl_element,
            fl_element,
            proj_element,
            qc_element,
            rs_element,
            sco_element,
            so_element,
            *sq_elements,
            stat_element,
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a Markdown survey spec (.md) to a Qualtrics Survey Format file (.qsf)"
    )
    parser.add_argument("input", help="Input .md file")
    parser.add_argument("-o", "--output", help="Output .qsf file (default: replaces .md extension)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".qsf")

    text = input_path.read_text(encoding="utf-8")
    survey = parse_survey(text)
    qsf = build_qsf(survey)

    output_path.write_text(json.dumps(qsf, indent=2, ensure_ascii=False), encoding="utf-8")

    q_count = sum(
        1 for b in survey["blocks"] for q in b["questions"] if q["type"] != "page_break"
    )
    block_count = len(survey["blocks"])

    print(f"✓ {output_path}")
    print(f"  Title:     {survey['title']}")
    print(f"  Language:  {survey['language']}")
    print(f"  Blocks:    {block_count}")
    print(f"  Questions: {q_count}")
    print()
    print("Import into Qualtrics:")
    print("  Create Project → Import a QSF File → select the .qsf file")


if __name__ == "__main__":
    main()
