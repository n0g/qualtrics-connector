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
| `[description]` | Descriptive text block (no input) |

Add `*` after the type to make a question required: `[mc]*`

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

## Documentation

- [SURVEY_SPEC.md](SURVEY_SPEC.md) — full markdown syntax reference
- [QSF_FORMAT.md](QSF_FORMAT.md) — notes on the QSF file format (reverse-engineered)

## Status

The QSF format is undocumented by Qualtrics. The converter has been validated against a real Qualtrics export and successfully imports. The `text-essay` selector (`ESTB`) is the one remaining best-guess field. Contributions of real `.qsf` exports are welcome.

## License

MIT
