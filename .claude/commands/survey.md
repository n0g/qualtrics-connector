# Qualtrics Survey Assistant

You are helping the user create or edit a Qualtrics survey using the markdown-to-QSF converter in this repository. The converter (`convert.py`) takes a `.md` file and produces a `.qsf` file ready to import into Qualtrics via **Create Project → Import a QSF File**.

## Your workflow

1. Read `SURVEY_SPEC.md` for the full markdown syntax reference.
2. Read or create the survey `.md` file the user is working on.
3. Make edits, then run the converter to verify it produces no warnings:
   ```
   python convert.py your_survey.md
   ```
4. Report any warnings and fix them before presenting the result.

## Key syntax rules

**Question heading:**
```
## Question text [type]* @label
```
- `*` makes it required
- `@label` lets other directives reference this question by name instead of QIDn

**Block heading:**
```
# Block Name
branch-if: @label/choice_number Selected
loop-from: @label
```

**Question-level directives** (placed immediately after the heading):
```
show-if: @label/choice_number Selected
carry-from: @label
```

**Choice annotations** (inline on bullet points):
```
- Option text [VARNAME=N]   ← recode value and variable name
- Other [+text]             ← enables inline text entry field
```

**Skip logic** (after choices):
```
skip-if: choice_number Selected → ENDOFBLOCK
skip-if: choice_number Selected → ENDOFSURVEY
skip-if: choice_number Selected → @label
```

## Question types

| Syntax | Description |
|--------|-------------|
| `[mc]` | Single-answer radio |
| `[mc-multi]` | Multi-answer checkboxes |
| `[mc-dropdown]` | Dropdown |
| `[rank]` | Drag-and-drop rank order |
| `[text]` | Single-line text entry |
| `[text-essay]` | Multi-line text entry |
| `[matrix]` | Likert matrix (one answer per row) — requires `scale:` line |
| `[matrix-multi]` | Likert matrix (multiple answers per row) |
| `[description]` | Descriptive text block (no input) |

## Label system

Assign a label to any question and reference it anywhere a `QIDn` is expected:

```markdown
## Are you subscribed? [mc]* @subscribed
- Yes
- No
skip-if: 1 Selected → ENDOFBLOCK

# Current Users
branch-if: @subscribed/1 Selected
```

Labels are resolved to the correct QID at build time. The converter warns on unresolved labels.

## Loop & Merge

The loop block repeats once per selected choice in the source question. Use `${lm://Field/1}` to pipe the current choice label into question text.

```markdown
## Who concerns you? [mc-multi]* @threat_actors
- Scammers
- Identity thieves

# Threat Details
loop-from: @threat_actors

## How would <strong>${lm://Field/1}</strong> harm you? [mc-multi]
- Phishing
- Physical harm
```

## Carry forward + Rank

Show only choices the respondent selected in a prior question:

```markdown
## Which concerns you most? [mc]*
carry-from: @threat_actors

## Rank your concerns [rank]*
carry-from: @threat_actors
```

## Common patterns

**Branching screener:**
```markdown
# Screener
## Have you used X? [mc]* @used_x
- Yes
- No
skip-if: 2 Selected → ENDOFSURVEY

# Users Only
branch-if: @used_x/1 Selected

## How long have you used X? [mc]
- Less than 1 year
- More than 1 year
```

**Matrix with reversed item:**
```markdown
## Rate the following [matrix]
scale: Strongly Disagree, Neutral, Strongly Agree
- The service works well
- The service is hard to use <!-- REVERSED ITEM -->
```

**"Other — please specify":**
```markdown
- Other [+text]
```

## What the converter cannot do yet

- AND/OR compound conditions in branch/display/skip logic (single condition only)
- Choice randomization
- Loop blocks combined with `branch-if:`
- Scoring
