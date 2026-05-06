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
    "matrix":       ("Matrix", "Likert", "SingleAnswer"),
    "matrix-multi": ("Matrix", "Likert", "MultipleAnswer"),
    "description":  ("DB",     "TB",    None),
}

# ## Question text [type] or ## Question text [type]*
_QUESTION_RE = re.compile(r"^##\s+(.+?)\s+\[([^\]]+)\]\s*(\*)?\s*$")

# branch-if: QID2/1 Selected  — wraps block in a Branch flow element
# show-if:   QID2/1 Selected  — on block: DisplayLogic on all questions; on question: DisplayLogic on that question
_LOGIC_COND_RE = re.compile(r"(QID\d+)/(\d+)\s+(\w+)", re.IGNORECASE)

# skip-if: 1 Selected → ENDOFBLOCK  (→ or > accepted)
_SKIP_IF_RE = re.compile(r"(\d+)\s+(\w+)\s+[→>]\s+(\S+)", re.IGNORECASE)

# loop-from: QID13  — Loop & Merge block driven by selected choices of source question
_LOOP_FROM_RE = re.compile(r"(QID\d+)", re.IGNORECASE)

# [VARNAME] or [VARNAME=N] on a choice/row bullet — variable naming and recode values
_CHOICE_ANNOTATION_RE = re.compile(r'^(.*?)\s*\[([A-Z_][A-Z0-9_]*)(?:=(\d+))?\]\s*$')

# lang-XX: or lang-XX-scale: for translations
_LANG_LINE_RE = re.compile(r'^lang-([a-z]{2})(?:-(scale))?:\s*(.+)$', re.IGNORECASE)


def _parse_logic_condition(line: str) -> dict | None:
    m = _LOGIC_COND_RE.search(line)
    if m:
        return {"qid": m.group(1), "choice": int(m.group(2)), "operator": m.group(3)}
    return None


def _parse_skip_rule(line: str) -> dict | None:
    m = _SKIP_IF_RE.search(line)
    if m:
        return {"choice": int(m.group(1)), "condition": m.group(2), "destination": m.group(3)}
    return None


def _empty_question(text: str, qtype: str, required: bool) -> dict:
    return {
        "text": text,
        "type": qtype.lower(),
        "required": required,
        "choices": [],
        "rows": [],
        "scale": [],
        "body_lines": [],        # paragraph text for [description] questions
        "skip_logic": [],        # list of {choice, condition, destination}
        "display_logic": None,   # {qid, choice, operator}
        "recode_values": {},     # {1-based choice idx → recode value string}
        "variable_names": {},    # {1-based choice idx → variable name string}
        "text_translations": {}, # {lang_code → translated question text}
        "choice_translations": {},  # {lang_code → {1-based idx → text}}
        "row_translations": {},     # {lang_code → {1-based idx → text}}
        "scale_translations": {},   # {lang_code → [text, ...]}
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
    langs_raw = meta.get("languages", [])
    if isinstance(langs_raw, str):
        langs_raw = [l.strip() for l in langs_raw.split(",") if l.strip()]
    extra_languages: list[str] = [l.upper() for l in langs_raw]

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
            current_block = {
                "name": "Default Question Block",
                "questions": [],
                "branch_logic": None,   # wraps block in Branch flow element
                "display_logic": None,  # applies DisplayLogic to all questions in block
                "loop_from": None,      # Loop & Merge: source question QID
            }

    # Tracks what was last parsed to associate lang-XX: lines with the right field.
    # Values: "question_text" | "scale" | ("choice", 1-based-idx) | ("row", 1-based-idx)
    _last_item_type: str | tuple | None = None

    while idx < len(lines):
        line = lines[idx]
        idx += 1

        # Skip HTML comments
        stripped = line.strip()
        if stripped.startswith("<!--"):
            continue

        # H1 → new block
        if re.match(r"^#\s+", line) and not line.startswith("##"):
            flush_block()
            current_block = {
                "name": line.lstrip("# ").strip(),
                "questions": [],
                "branch_logic": None,
                "display_logic": None,
                "loop_from": None,
            }
            continue

        # branch-if: block in Branch flow element (before first question in block)
        if stripped.lower().startswith("branch-if:"):
            cond = _parse_logic_condition(stripped)
            if cond is not None and current_block is not None and current_question is None:
                current_block["branch_logic"] = cond
            continue

        # loop-from: Loop & Merge block driven by selected choices of source question
        if stripped.lower().startswith("loop-from:"):
            m = _LOOP_FROM_RE.search(stripped)
            if m is not None and current_block is not None and current_question is None:
                current_block["loop_from"] = m.group(1).upper()
            continue

        # show-if: DisplayLogic on block (all questions) or on single question
        if stripped.lower().startswith("show-if:"):
            cond = _parse_logic_condition(stripped)
            if cond is not None:
                if current_question is not None:
                    current_question["display_logic"] = cond
                elif current_block is not None:
                    current_block["display_logic"] = cond
            continue

        # skip-if: skip logic on the current question
        if stripped.lower().startswith("skip-if:"):
            rule = _parse_skip_rule(stripped)
            if rule is not None and current_question is not None:
                current_question["skip_logic"].append(rule)
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
            _last_item_type = "question_text"
            continue

        # Page break (--- after frontmatter)
        if stripped == "---":
            flush_question()
            ensure_block()
            current_block["questions"].append({"type": "page_break"})  # type: ignore[index]
            continue

        if current_question is None:
            continue

        # scale: line (matrix)
        if stripped.lower().startswith("scale:"):
            raw = stripped[6:].strip()
            current_question["scale"] = [s.strip() for s in raw.split(",") if s.strip()]
            _last_item_type = "scale"
            continue

        # lang-XX: or lang-XX-scale: translation annotation
        m_lang = _LANG_LINE_RE.match(stripped)
        if m_lang:
            lang = m_lang.group(1).upper()
            is_scale = m_lang.group(2) is not None
            text = m_lang.group(3).strip()
            if is_scale:
                current_question["scale_translations"][lang] = [s.strip() for s in text.split(",") if s.strip()]
            elif _last_item_type == "question_text":
                current_question["text_translations"][lang] = text
            elif _last_item_type == "scale":
                current_question["scale_translations"][lang] = [s.strip() for s in text.split(",") if s.strip()]
            elif isinstance(_last_item_type, tuple):
                kind, item_idx = _last_item_type
                if kind == "choice":
                    current_question["choice_translations"].setdefault(lang, {})[item_idx] = text
                elif kind == "row":
                    current_question["row_translations"].setdefault(lang, {})[item_idx] = text
            continue

        # bullet → choice or matrix row (with optional [VARNAME=N] annotation)
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            ann = _CHOICE_ANNOTATION_RE.match(value)
            if ann:
                value = ann.group(1).strip()
                varname = ann.group(2)
                recode = ann.group(3)
            else:
                varname = recode = None
            if current_question["type"].startswith("matrix"):
                current_question["rows"].append(value)
                item_idx = len(current_question["rows"])
                _last_item_type = ("row", item_idx)
            else:
                current_question["choices"].append(value)
                item_idx = len(current_question["choices"])
                _last_item_type = ("choice", item_idx)
            if varname:
                current_question["variable_names"][item_idx] = varname
            if recode is not None:
                current_question["recode_values"][item_idx] = recode
            continue

        # Body text for [description] questions (all remaining content)
        if current_question["type"] == "description":
            current_question["body_lines"].append(line)
            continue

    flush_block()

    return {
        "title": title,
        "language": language,
        "description": description,
        "extra_languages": extra_languages,
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
# QSF builder helpers
# ---------------------------------------------------------------------------

def _join_body(lines: list[str]) -> str:
    """Join description body lines into HTML, preserving paragraph breaks."""
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []
    if current:
        paragraphs.append(" ".join(current))
    return "<br><br>".join(paragraphs)


def _build_display_logic(dl: dict) -> dict:
    """Build DisplayLogic payload for a question (has inPage: false)."""
    return {**_logic_condition_block(dl), "inPage": False}


def _build_branch_logic(dl: dict) -> dict:
    """Build BranchLogic payload for a flow Branch element (no inPage field)."""
    return _logic_condition_block(dl)


def _logic_condition_block(dl: dict) -> dict:
    src_qid = dl["qid"]
    choice = dl["choice"]
    operator = dl["operator"]
    locator = f"q://{src_qid}/SelectableChoice/{choice}"
    op_text = "Is Selected" if operator == "Selected" else f"Is {operator}"
    return {
        "0": {
            "0": {
                "LogicType": "Question",
                "QuestionID": src_qid,
                "QuestionIsInLoop": "no",
                "ChoiceLocator": locator,
                "Operator": operator,
                "QuestionIDFromLocator": src_qid,
                "LeftOperand": locator,
                "Type": "Expression",
                "Description": (
                    f"<span class=\"ConjDesc\">If</span> "
                    f"<span class=\"QuestionDesc\">{src_qid}</span> "
                    f"<span class=\"LeftOpDesc\">Choice {choice}</span> "
                    f"<span class=\"OpDesc\">{op_text}</span> "
                ),
            },
            "Type": "If",
        },
        "Type": "BooleanExpression",
    }


def _build_skip_logic_entry(sl: dict, qid: str, q: dict, skip_id: int) -> dict:
    choice = sl["choice"]
    condition = sl["condition"]
    destination = sl["destination"]

    if q["type"] in ("text", "text-essay"):
        locator = f"q://{qid}/ChoiceTextEntryValue"
        choice_display = q["text"][:40]
    else:
        locator = f"q://{qid}/SelectableChoice/{choice}"
        choices = q.get("choices", [])
        choice_display = choices[choice - 1] if 0 < choice <= len(choices) else f"Choice {choice}"

    dest_labels = {"ENDOFSURVEY": "End of Survey", "ENDOFBLOCK": "End of Block"}
    dest_desc = dest_labels.get(destination, destination)

    cond_labels = {
        "Selected": "Is Selected", "NotSelected": "Is Not Selected",
        "Empty": "Is Empty", "NotEmpty": "Is Not Empty",
    }
    cond_desc = cond_labels.get(condition, condition)

    return {
        "SkipLogicID": skip_id,
        "ChoiceLocator": locator,
        "Condition": condition,
        "SkipToDestination": destination,
        "Locator": locator,
        "SkipToDescription": (
            f"{q['text'][:40]} <strong>{choice_display}</strong>  "
            f"<strong>{cond_desc}</strong>"
        ),
        "Description": (
            f"Condition: <strong title=\"{choice_display}\">{choice_display}</strong> "
            f"<strong>{cond_desc}</strong>. Skip To: <strong>{dest_desc}</strong>."
        ),
        "QuestionID": qid,
    }


# ---------------------------------------------------------------------------
# QSF payload builder
# ---------------------------------------------------------------------------

def _build_language_dict(q: dict) -> dict:
    """Build the Language dict for a question's SQ payload from translation data."""
    all_langs: set[str] = set()
    all_langs |= set(q.get("text_translations", {}).keys())
    all_langs |= set(q.get("scale_translations", {}).keys())
    all_langs |= set(q.get("choice_translations", {}).keys())
    all_langs |= set(q.get("row_translations", {}).keys())

    result: dict = {}
    for lang in sorted(all_langs):
        entry: dict = {}
        if lang in q.get("text_translations", {}):
            entry["QuestionText"] = q["text_translations"][lang]
        is_matrix = q["type"].startswith("matrix")
        if is_matrix:
            row_trans = q.get("row_translations", {}).get(lang, {})
            if row_trans:
                entry["Choices"] = {
                    str(i + 1): {"Display": row_trans[i + 1]}
                    for i in range(len(q["rows"]))
                    if (i + 1) in row_trans
                }
            scale_trans = q.get("scale_translations", {}).get(lang, [])
            if scale_trans:
                entry["Answers"] = {str(i + 1): {"Display": s} for i, s in enumerate(scale_trans)}
        else:
            choice_trans = q.get("choice_translations", {}).get(lang, {})
            if choice_trans:
                entry["Choices"] = {
                    str(i + 1): {"Display": choice_trans[i + 1]}
                    for i in range(len(q["choices"]))
                    if (i + 1) in choice_trans
                }
        if entry:
            result[lang] = entry
    return result


def _build_question_payload(
    q: dict,
    qid_num: int,
    display_logic: dict | None = None,
) -> dict:
    qid = f"QID{qid_num}"
    tag = f"Q{qid_num}"
    qtype = q["type"]
    required: bool = q.get("required", False)

    type_info = QUESTION_TYPES.get(qtype, ("TE", "SL", None))
    qt, sel, sub = type_info

    force = "ON" if required else "OFF"

    # Description questions use body text as QuestionText when available
    if qt == "DB" and q.get("body_lines"):
        question_text = _join_body(q["body_lines"])
    else:
        question_text = q["text"]

    payload: dict = {
        "QuestionText": question_text,
        "DataExportTag": tag,
        "QuestionType": qt,
        "Selector": sel,
        "DataVisibility": {"Private": False, "Hidden": False},
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": q["text"][:99],
        "Validation": {
            "Settings": {
                "ForceResponse": force,
                "Type": "None",
            }
        },
        "Language": _build_language_dict(q) or [],
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
        payload["DynamicChoicesData"] = []

    if qt == "TE":
        payload["SearchSource"] = {"AllowFreeResponse": "false"}

    if qt == "Matrix":
        rows = q.get("rows", [])
        scale = q.get("scale", [])
        payload["DefaultChoices"] = False
        payload["Choices"] = {str(i + 1): {"Display": r} for i, r in enumerate(rows)}
        payload["ChoiceOrder"] = [str(i + 1) for i in range(len(rows))]
        payload["Answers"] = {str(i + 1): {"Display": s} for i, s in enumerate(scale)}
        payload["AnswerOrder"] = [str(i + 1) for i in range(len(scale))]
        payload["NextChoiceId"] = len(rows) + 1
        payload["NextAnswerId"] = len(scale) + 1
        payload["GradingData"] = []
        payload["ChoiceDataExportTags"] = False
        # Override Configuration with matrix-specific layout settings.
        # ChoiceColumnWidth=40 gives the statement column 40% of the row width;
        # the Qualtrics default of 25 is too narrow for long statements.
        payload["Configuration"] = {
            "QuestionDescriptionOption": "UseText",
            "TextPosition": "inline",
            "ChoiceColumnWidth": 40,
            "RepeatHeaders": "none",
            "WhiteSpace": "OFF",
            "MobileFirst": True,
        }

    # Display logic: question-level overrides block-level show-if
    effective_dl = q.get("display_logic") or display_logic
    if effective_dl:
        payload["DisplayLogic"] = _build_display_logic(effective_dl)

    # QuestionID goes last (before optional recode/varname fields), matching real QSF export order
    payload["QuestionID"] = qid

    if q.get("recode_values"):
        payload["RecodeValues"] = {str(k): str(v) for k, v in q["recode_values"].items()}
    if q.get("variable_names"):
        payload["VariableNaming"] = {str(k): v for k, v in q["variable_names"].items()}

    return payload


# ---------------------------------------------------------------------------
# QSF builder
# ---------------------------------------------------------------------------

def build_qsf(survey: dict) -> dict:
    survey_id = new_survey_id()
    user_id = new_user_id()
    rs_id = new_rs_id()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    title: str = survey["title"]
    lang: str = survey["language"]
    extra_languages: list[str] = survey.get("extra_languages", [])

    # Assign QIDs and collect per-block data
    qid_counter = 1
    skip_id_counter = 1
    blocks_data: list[dict] = []
    # Each entry: (qid_num, question_dict, block_display_logic_or_None)
    all_question_triples: list[tuple[int, dict, dict | None]] = []

    for i, block in enumerate(survey["blocks"]):
        block_id = new_block_id()
        block_elements: list[dict] = []
        block_triples: list[tuple[int, dict, dict | None]] = []
        # block-level show-if applies DisplayLogic to all questions (not via Branch)
        block_dl = block.get("display_logic")

        for q in block["questions"]:
            if q["type"] == "page_break":
                block_elements.append({"Type": "Page Break"})
            else:
                qid = f"QID{qid_counter}"
                elem: dict = {"Type": "Question", "QuestionID": qid}
                if q.get("skip_logic"):
                    elem["SkipLogic"] = [
                        _build_skip_logic_entry(sl, qid, q, skip_id_counter + k)
                        for k, sl in enumerate(q["skip_logic"])
                    ]
                    skip_id_counter += len(q["skip_logic"])
                block_elements.append(elem)
                block_triples.append((qid_counter, q, block_dl))
                qid_counter += 1

        blocks_data.append({
            "id": block_id,
            "name": block["name"],
            # First block uses "Default"; subsequent blocks use "Standard"
            "block_type": "Default" if i == 0 else "Standard",
            "elements": block_elements,
            "triples": block_triples,
            "branch_logic": block.get("branch_logic"),  # None → regular block in flow
            "loop_from": block.get("loop_from"),        # None → not a loop block
        })
        all_question_triples.extend(block_triples)

    # Lookup from QID string to question dict, used when building loop block Options
    qid_to_question = {f"QID{n}": q for n, q, _ in all_question_triples}

    total_questions = len(all_question_triples)

    # BL element: real blocks first, trash block last
    bl_payload: list[dict] = []
    for bd in blocks_data:
        bl_entry: dict = {
            "Type": bd["block_type"],
            "Description": bd["name"],
            "ID": bd["id"],
            "BlockElements": bd["elements"],
        }
        if bd.get("loop_from"):
            src_qid = bd["loop_from"]
            src_q = qid_to_question.get(src_qid, {})
            n_choices = len(src_q.get("choices", []))
            locator = f"q://{src_qid}/ChoiceGroup/SelectedChoices"
            bl_entry["SubType"] = ""
            bl_entry["Options"] = {
                "BlockLocking": "false",
                "RandomizeQuestions": "false",
                "Looping": "Question",
                "LoopingOptions": {
                    "Locator": locator,
                    "QID": src_qid,
                    "ChoiceGroupLocator": locator,
                    "Static": {str(j + 1): {"2": ""} for j in range(n_choices)},
                    "Randomization": "None",
                },
            }
        bl_payload.append(bl_entry)
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

    # FL element
    # Each block (or branch+nested block) consumes sequential FlowIDs starting at FL_2.
    # Properties.Count = max FlowID used.
    flow_counter = 2
    flow_items: list[dict] = []

    for bd in blocks_data:
        if bd.get("loop_from"):
            flow_items.append({
                "ID": bd["id"],
                "Type": "Standard",
                "FlowID": f"FL_{flow_counter}",
            })
            flow_counter += 1
        elif bd["branch_logic"]:
            branch_flow_id = f"FL_{flow_counter}"
            flow_counter += 1
            nested_flow_id = f"FL_{flow_counter}"
            flow_counter += 1
            flow_items.append({
                "Type": "Branch",
                "FlowID": branch_flow_id,
                "Description": "New Branch",
                "BranchLogic": _build_branch_logic(bd["branch_logic"]),
                "Flow": [{"Type": "Block", "ID": bd["id"], "FlowID": nested_flow_id, "Autofill": []}],
            })
        else:
            flow_items.append({
                "ID": bd["id"],
                "Type": "Block",
                "FlowID": f"FL_{flow_counter}",
                "Autofill": [],
            })
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

    # PROJ element
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

    # SCO element
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
    if extra_languages:
        available = {lang: []}
        available.update({l: [] for l in extra_languages})
        so_element["Payload"]["AvailableLanguages"] = available
        so_element["Payload"]["HiddenLanguages"] = []
        so_element["Payload"]["CustomLanguages"] = []
        so_element["Payload"]["MetaDataTranslations"] = {}

    # SQ elements
    sq_elements = []
    for qid_num, q, block_dl in all_question_triples:
        sq_elements.append({
            "SurveyID": survey_id,
            "Element": "SQ",
            "PrimaryAttribute": f"QID{qid_num}",
            "SecondaryAttribute": q["text"][:99],
            "TertiaryAttribute": None,
            "Payload": _build_question_payload(q, qid_num, display_logic=block_dl),
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
        1 for b in survey["blocks"] for q in b["questions"] if q.get("type") != "page_break"
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
