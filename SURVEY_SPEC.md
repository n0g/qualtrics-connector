# Markdown Survey Specification

This document defines the markdown format accepted by `convert.py`.

---

## File Structure

```
---
title: My Survey Title
language: EN
description: Optional description
---

# Block Name

## Question text [type]
- Choice 1
- Choice 2

---

# Another Block

## Another question [type]
```

---

## Frontmatter

YAML block at the top of the file (required for title, optional otherwise).

| Key | Default | Description |
|-----|---------|-------------|
| `title` | `Untitled Survey` | Survey name shown in Qualtrics |
| `language` | `EN` | Language code |
| `description` | `""` | Survey description (metadata only) |

---

## Blocks

Level-1 headings (`#`) define blocks (pages in Qualtrics). If no `#` headings are used, all questions go into a single default block.

```markdown
# Demographics

## Question 1 [mc]
...

# Feedback

## Question 2 [text]
```

---

## Questions

Level-2 headings (`##`) define questions. The type is specified in `[brackets]` at the end.

```markdown
## Question text here [type]
```

Add `*` after the type to make the question required:

```markdown
## What is your name? [text]*
```

---

## Question Types

### `[mc]` — Multiple Choice, Single Answer

Choices are listed as bullet points.

```markdown
## What is your age? [mc]
- Under 18
- 18–24
- 25–34
- 35–44
- 45 or older
```

### `[mc-multi]` — Multiple Choice, Multiple Answers

```markdown
## Which platforms do you use? [mc-multi]
- iOS
- Android
- Web
- Desktop
```

### `[mc-dropdown]` — Multiple Choice, Dropdown

```markdown
## Select your country [mc-dropdown]
- United States
- Germany
- Japan
- Other
```

### `[text]` — Single-Line Text Entry

No bullet points needed.

```markdown
## What is your email address? [text]
```

### `[text-essay]` — Multi-Line / Essay Text Entry

```markdown
## Please describe your experience [text-essay]
```

### `[matrix]` — Matrix / Likert Scale (single answer per row)

Specify the scale (columns) with a `scale:` line (comma-separated), then list rows as bullet points.

```markdown
## Rate the following features [matrix]
scale: Poor, Fair, Good, Excellent
- Ease of use
- Visual design
- Performance
- Documentation
```

### `[matrix-multi]` — Matrix, Multiple Answers per Row

Same syntax as `[matrix]`.

```markdown
## Which of the following apply? [matrix-multi]
scale: Never, Sometimes, Often, Always
- I use the mobile app
- I use the desktop app
- I use the API
```

### `[description]` — Descriptive Text (no input)

The heading is the internal label. Any paragraph text after the heading becomes the displayed body content.

```markdown
## Instructions [description]
Please read the following carefully before proceeding.

All responses are anonymous and will only be used for research purposes.
```

---

## Page Breaks

A `---` line inside a block inserts a page break between questions.

```markdown
# Block 1

## Question 1 [mc]
- Yes
- No

---

## Question 2 [text]
```

---

## Skip Logic

`skip-if:` conditionally skips to another question or ends the block/survey based on an answer. Place it after the choices of an MC question.

```
skip-if: <choice_number> <condition> → <destination>
```

| Field | Values |
|-------|--------|
| `choice_number` | 1-based index of the choice |
| `condition` | `Selected`, `NotSelected`, `Empty`, `NotEmpty` |
| `destination` | `ENDOFBLOCK`, `ENDOFSURVEY`, or `QID<n>` |

Multiple `skip-if:` rules on one question are all applied.

```markdown
## Are you currently subscribed? [mc]*
- Yes
- No
skip-if: 1 Selected → ENDOFBLOCK
```

```markdown
## Have you ever considered using one? [mc]*
- Yes
- No
skip-if: 2 Selected → ENDOFSURVEY
```

---

## Conditional Blocks (Branch Flow)

`branch-if:` on a block (line immediately after `# Block Name`) wraps the entire block in a Branch element in the Qualtrics survey flow. The block is only presented to respondents who match the condition.

```
# Block Name
branch-if: QID<n>/<choice_number> <operator>
```

| Field | Values |
|-------|--------|
| `QID<n>` | Question number in the survey (assigned sequentially, 1-based) |
| `choice_number` | 1-based index of the choice in that question |
| `operator` | `Selected`, `NotSelected` |

```markdown
# Premium Features
branch-if: QID3/1 Selected

## Which premium features do you use? [mc-multi]
- Advanced analytics
- API access
- Priority support
```

**Question numbering:** QIDs are assigned in order of appearance across all blocks (counting description blocks as questions). QID1 is the first question in the first block, QID2 is the second, and so on.

---

## Display Logic on Individual Questions

`show-if:` on a question (line immediately after `## Question text [type]`) conditionally shows that question based on a previous answer.

```
## Question text [type]
show-if: QID<n>/<choice_number> <operator>
```

```markdown
## Which premium service did you use? [mc]
show-if: QID2/1 Selected
- Service A
- Service B
```

---

## Full Example

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
- 35–44
- 45 or older

## What is your job role? [mc]
- Engineer
- Designer
- Manager
- Other
skip-if: 1 Selected → ENDOFSURVEY

---

## How long have you used our product? [mc]
- Less than 1 month
- 1–6 months
- 6–12 months
- More than 1 year

# Product Experience

## Please rate the following aspects of our product [matrix]
scale: Very Poor, Poor, Neutral, Good, Excellent
- Ease of use
- Visual design
- Performance
- Documentation
- Customer support

## Which features do you use regularly? [mc-multi]
- Dashboard
- Reports
- Integrations
- API
- Mobile app

## What is the most important improvement we could make? [text-essay]

## Overall, how satisfied are you with our product? [mc]*
- Very dissatisfied
- Dissatisfied
- Neutral
- Satisfied
- Very satisfied

# Advanced Users
branch-if: QID3/4 Selected

## How do you primarily use the API? [mc]
- Internal automation
- Third-party integrations
- Data export
- Other
```

---

## Limitations

- Branch logic conditions support only a single `QID/choice operator` expression (AND/OR not yet supported)
- Scoring is not supported
- Choice randomization is not supported
- Multi-language questions are not supported
- Rich text / HTML in question text is not supported
