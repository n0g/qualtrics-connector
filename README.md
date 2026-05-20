# qualtrics-survey-builder

Build Qualtrics surveys from a plain Markdown file and import the result directly — no API access required.

## Using with Claude Code

The easiest way to create a survey is with [Claude Code](https://claude.ai/code). Clone the repo, open it in Claude Code, and type `/survey` to activate the built-in skill. Claude will read and edit your `.md` file, run the converter, and fix any warnings before reporting back.

```bash
git clone https://github.com/n0g/qualtrics-survey-builder.git
cd qualtrics-survey-builder
pip install -r requirements.txt
claude
```

Then type `/survey` and describe what you want:

> Create a screener that routes current users, former users, and non-users into separate blocks

> Add a loop & merge block that asks about misuse methods for each threat actor the respondent selected

> Add a 7-point Likert matrix measuring response efficacy with one reversed item

Claude writes the markdown, runs `python convert.py`, and produces a `.qsf` ready to import.

See [SURVEY_SPEC.md](SURVEY_SPEC.md) for the full markdown syntax reference.

## Manual usage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python convert.py your_survey.md
# → produces your_survey.qsf
```

```bash
python convert.py your_survey.md -o output.qsf
```

Then in Qualtrics: **Create Project → Import a QSF File**.

See [SURVEY_SPEC.md](SURVEY_SPEC.md) for the markdown format and [example.md](example.md) for a complete example.

## Documentation

- [SURVEY_SPEC.md](SURVEY_SPEC.md) — full markdown syntax reference (question types, logic, labels, loop & merge, translations, and more)
- [QSF_FORMAT.md](QSF_FORMAT.md) — notes on the QSF file format (reverse-engineered from real Qualtrics exports)

## Status

The QSF format is undocumented by Qualtrics. The converter has been validated against real Qualtrics exports and successfully imports. Skip logic, display logic, branch flow, loop & merge, carry-forward, and rank order have all been confirmed against exported `.qsf` files. Contributions of real `.qsf` exports are welcome.

## License

MIT
