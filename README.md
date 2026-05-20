# qualtrics-connector

Convert a Markdown survey specification into a Qualtrics Survey Format (`.qsf`) file, ready to import directly into Qualtrics — no API access required.

## How it works

1. Write your survey in Markdown (see [SURVEY_SPEC.md](SURVEY_SPEC.md))
2. Run `convert.py` to produce a `.qsf` file
3. In Qualtrics: **Create Project → Import a QSF File**

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python convert.py your_survey.md
# → produces your_survey.qsf
```

```bash
python convert.py your_survey.md -o output.qsf
```

## Supported features

| Feature | Syntax |
|---------|--------|
| Required question | `[mc]*` |
| Skip logic | `skip-if: N Condition → Destination` |
| Branch flow | `branch-if: QIDn/choice Operator` |
| Display logic | `show-if: QIDn/choice Operator` |
| Question labels | `## Question [type] @label` |
| Loop & Merge | `loop-from: QIDn` or `loop-from: @label` |
| Carry forward choices | `carry-from: QIDn` |
| Choice recode value | `- Choice text [VARNAME=N]` |
| Choice variable name | `- Choice text [VARNAME]` |
| Choice text entry | `- Choice text [+text]` |
| Translations | `lang-XX:` lines + `languages: [XX]` frontmatter |

## Supported question types

| Markdown syntax | Qualtrics type |
|-----------------|----------------|
| `[mc]` | Multiple choice, single answer (radio) |
| `[mc-multi]` | Multiple choice, multiple answers (checkboxes) |
| `[mc-dropdown]` | Multiple choice, dropdown |
| `[text]` | Single-line text entry |
| `[text-essay]` | Multi-line / essay text entry |
| `[matrix]` | Matrix / Likert scale (single answer per row) |
| `[matrix-multi]` | Matrix (multiple answers per row) |
| `[rank]` | Rank order (drag and drop) |
| `[description]` | Descriptive text block with body text (no input) |

Add `*` after the type to make a question required: `[mc]*`

## Branching and logic

### Conditional blocks (branch flow)

Add `branch-if:` on the line after a `# Block Name` heading to wrap the block in a Qualtrics Branch flow element. The block is only shown to respondents who match the condition.

```markdown
# Premium Features
branch-if: QID3/1 Selected
```

`QID3/1` means question 3, choice 1. Questions are numbered sequentially across the entire survey starting at 1.

### Skip logic

Add `skip-if:` after a question's choices to jump to another question, end the block, or end the survey when a specific answer is selected.

```markdown
## Are you currently subscribed? [mc]*
- Yes
- No
skip-if: 1 Selected → ENDOFBLOCK
```

Destinations: `ENDOFBLOCK`, `ENDOFSURVEY`, or `QID<n>`.

### Recode values and variable naming

Add `[VARNAME=N]` (or just `[VARNAME]` or `[=N]`) at the end of a choice to assign an export variable name and/or numeric recode value:

```markdown
## What kind of harm concerns you? [mc-multi]
- Financial loss [FINANCE=9]
- Risk to physical safety [PHYSICAL=2]
- Emotional distress [EMOTIONAL=3]
```

### Translations

Add `languages:` to the frontmatter and `lang-XX:` lines after question text and choices:

```markdown
---
title: My Survey
language: EN
languages: [DE]
---

## What is your age? [mc]*
lang-de: Wie alt sind Sie?
- Under 18
  lang-de: Unter 18 Jahren
- 18–24
  lang-de: 18–24
```

For matrix scale labels: `lang-de-scale: val1, val2, val3`

### Loop & Merge

Add `loop-from:` on the line after a `# Block Name` heading to configure a Loop & Merge block. The block repeats once per choice the respondent selected in the source question. Use `${lm://Field/1}` in question text to pipe in the current choice label.

```markdown
# Threat Actors
## Who concerns you? [mc-multi]
- Scammers
- Stalkers
- Identity thieves

# Threat Details
loop-from: QID1

## How would ${lm://Field/1} misuse your data? [mc-multi]
- Phishing
- Physical location
- Financial fraud
```

### Display logic on individual questions

Add `show-if:` immediately after a `## Question [type]` heading to conditionally show that question.

```markdown
## Which service did you use? [mc]
show-if: QID2/1 Selected
- Service A
- Service B
```

## Example

```markdown
---
title: Product Feedback Survey
language: EN
---

# About You

## How old are you? [mc]
- Under 18
- 18–24
- 25–34
- 35 or older

# Feedback

## Rate our product [matrix]
scale: Poor, Fair, Good, Excellent
- Ease of use
- Performance

## Any additional comments? [text-essay]
```

See [example.md](example.md) for a full example.

## Using with Claude Code

This project includes a Claude Code skill that lets you describe a survey in plain language and have Claude write or edit the markdown spec for you.

**Requirements:** [Claude Code](https://claude.ai/code) CLI installed and authenticated.

```bash
# Open Claude Code in the project directory
claude
```

Then type `/survey` to activate the skill. Claude will load the full syntax reference and help you:

- Draft new survey questions and blocks
- Add skip logic, branch flow, and loop & merge
- Choose appropriate question types and scale labels
- Run the converter and fix any warnings

**Example prompts after `/survey`:**

> Add a matrix question measuring response efficacy with a 7-point agree/disagree scale

> Add a screener block that skips to the end of the survey if the respondent selects "None of the above"

> Convert the threat actors question into a loop block and ask about misuse methods for each

Claude reads your `.md` file directly, makes edits, and runs `convert.py` to verify the output before reporting back.

## Documentation

- [SURVEY_SPEC.md](SURVEY_SPEC.md) — full markdown syntax reference
- [QSF_FORMAT.md](QSF_FORMAT.md) — notes on the QSF file format (reverse-engineered)

## Status

The QSF format is undocumented by Qualtrics. The converter has been validated against real Qualtrics exports and successfully imports. Skip logic, display logic, and branch flow elements have all been confirmed against exported `.qsf` files. The `text-essay` selector (`ESTB`) is the one remaining best-guess field. Contributions of real `.qsf` exports are welcome.

## License

MIT
