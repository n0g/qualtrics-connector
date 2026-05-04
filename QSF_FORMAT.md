# QSF File Format Reference

Qualtrics Survey Format (QSF) is a proprietary JSON file. Qualtrics does not publish an official spec; this document is reverse-engineered from the [ctesta01 gist](https://gist.github.com/ctesta01/d4255959dace01431fb90618d1e8c241) and the [sumtxt/qsf R package](https://github.com/sumtxt/qsf).

**Confidence levels:** ✅ Confirmed from source code · ⚠️ Inferred / best-guess · ❓ Unknown

---

## Top-Level Structure

```json
{
  "SurveyEntry": { ... },
  "SurveyElements": [ ... ]
}
```

---

## SurveyEntry ✅

```json
{
  "SurveyID": "SV_xxxxxxxxxxxxxxx",
  "SurveyName": "My Survey",
  "SurveyDescription": "",
  "SurveyOwnerID": "UR_xxxxxxxxxxxxxxx",
  "SurveyBrandID": "qualtricssurvey",
  "DivisionID": null,
  "SurveyLanguage": "EN",
  "SurveyActiveResponseSet": "RS_xxxxxxxxxxxxxxx",
  "SurveyStatus": "Inactive",
  "SurveyStartDate": "0000-00-00 00:00:00",
  "SurveyExpirationDate": "0000-00-00 00:00:00",
  "SurveyCreationDate": "2026-05-01 12:00:00",
  "CreatorID": "UR_xxxxxxxxxxxxxxx",
  "LastModified": "2026-05-01 12:00:00",
  "LastAccessed": "0000-00-00 00:00:00",
  "LastActivated": "0000-00-00 00:00:00",
  "Deleted": null
}
```

**ID formats:**
- `SurveyID`: `SV_` + 15 alphanumeric chars
- `SurveyOwnerID` / `CreatorID`: `UR_` + 15 alphanumeric chars
- `SurveyActiveResponseSet`: `RS_` + 15 alphanumeric chars

---

## SurveyElements Array

Contains the following element types identified by the `Element` field. Each element follows this envelope:

```json
{
  "SurveyID": "SV_xxx",
  "Element": "<type>",
  "PrimaryAttribute": "...",
  "SecondaryAttribute": null,
  "TertiaryAttribute": null,
  "Payload": { ... }
}
```

### Known element types

| Element | Description | Payload type |
|---------|-------------|--------------|
| `BL` | Survey Blocks (pages) | Array of block objects |
| `FL` | Survey Flow | Object with `Flow` array |
| `SO` | Survey Options | Object |
| `SQ` | Survey Question | Object (one per question) |
| `RS` | Response Set | `null` |
| `PROJ` | Project metadata | Object |
| `STAT` | Survey statistics ⚠️ | Object |
| `QC` | Question count ⚠️ | `null` |
| `SCO` | Scoring ⚠️ | Object |

---

## BL — Survey Blocks ✅

```json
{
  "Element": "BL",
  "PrimaryAttribute": "Survey Blocks",
  "Payload": [
    {
      "Type": "Default",
      "Description": "Default Question Block",
      "ID": "BL_xxxxxxxxxxxxxxx",
      "BlockElements": [
        { "Type": "Question", "QuestionID": "QID1" },
        { "Type": "Page Break" },
        { "Type": "Question", "QuestionID": "QID2" }
      ]
    },
    {
      "Type": "Standard",
      "Description": "Second Block",
      "ID": "BL_xxxxxxxxxxxxxxx",
      "BlockElements": [
        { "Type": "Question", "QuestionID": "QID3" }
      ]
    },
    {
      "Type": "Trash",
      "Description": "Trash / Unused Questions",
      "ID": "BL_xxxxxxxxxxxxxxx"
    }
  ]
}
```

- **Block ID format:** `BL_` + 15 alphanumeric chars ✅
- First block uses `"Type": "Default"`; additional blocks use `"Type": "Standard"` ✅
- Trash block comes **last** in the array ✅
- Trash block has **no** `BlockElements` key ✅
- No `SubType` field in real exports ✅
- `BlockElements` accepts `"Question"` and `"Page Break"` type entries ✅

---

## FL — Survey Flow ✅

```json
{
  "Element": "FL",
  "PrimaryAttribute": "Survey Flow",
  "Payload": {
    "Flow": [
      { "ID": "BL_xxx", "Type": "Block", "FlowID": "FL_2" },
      { "ID": "BL_yyy", "Type": "Block", "FlowID": "FL_3" }
    ],
    "Properties": { "Count": 3 },
    "FlowID": "FL_1",
    "Type": "Root"
  }
}
```

- Root flow has `FlowID: "FL_1"` and `Type: "Root"` ✅
- Each block entry gets a sequential `FlowID` starting at `FL_2` ✅
- **No `EndOfSurvey` entry** — real exports end with the last block ✅
- `Properties.Count` = number of blocks + 1 (for the root) ✅

---

## SO — Survey Options ✅

```json
{
  "Element": "SO",
  "PrimaryAttribute": "Survey Options",
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
    "SurveyTitle": "My Survey",
    "SkinLibrary": "qualtrics",
    "SkinType": "templated",
    "Skin": { "brandingId": null, "templateId": "*base", "overrides": null },
    "NewScoring": 1,
    "SurveyMetaDescription": ""
  }
}
```

- Boolean-like values are strings (`"true"` / `"false"`), not JSON booleans ✅
- `NewScoring` is `1`, not `0` ✅
- `Skin` includes `"overrides": null` ✅
- `PartialData` is `"+1 week"` ✅
- `SkinLibrary` is institution-specific in real exports; `"qualtrics"` is a safe default ✅

---

## SQ — Survey Question ✅

```json
{
  "Element": "SQ",
  "PrimaryAttribute": "QID1",
  "SecondaryAttribute": "First 99 chars of question text",
  "Payload": {
    "QuestionText": "Full question text",
    "DataExportTag": "Q1",
    "QuestionType": "MC",
    "Selector": "SAVR",
    "SubSelector": "TX",
    "DataVisibility": { "Private": false, "Hidden": false },
    "Configuration": { "QuestionDescriptionOption": "UseText" },
    "QuestionDescription": "First 99 chars of question text",
    "Choices": {
      "1": { "Display": "Option A" },
      "2": { "Display": "Option B" }
    },
    "ChoiceOrder": ["1", "2"],
    "Validation": {
      "Settings": {
        "ForceResponse": "OFF",
        "Type": "None"
      }
    },
    "Language": [],
    "NextChoiceId": 3,
    "NextAnswerId": 1,
    "QuestionID": "QID1"
  }
}
```

- `QuestionID` format: `QID` + integer (e.g. `QID1`, `QID2`) ✅
- `QuestionID` goes at the **end** of the payload, not the top ✅
- `DataExportTag` defaults to `Q` + integer ✅
- `ChoiceOrder` values are **strings**, not integers (`["1","2"]` not `[1,2]`) ✅
- `DataVisibility` field is present ✅
- `NextChoiceId` = number of choices + 1 ✅
- `NextAnswerId` = number of answers + 1 (for matrix); 1 otherwise ✅
- Validation has only `ForceResponse` and `Type` — no `ForceResponseType` ✅
- `Language` is an empty array for single-language surveys ✅
- No `DefaultChoices` field ✅

### Question Types & Selectors

| Markdown type | QuestionType | Selector | SubSelector |
|---------------|-------------|----------|-------------|
| `mc` | `MC` | `SAVR` | `TX` |
| `mc-multi` | `MC` | `MAVR` | `TX` |
| `mc-dropdown` | `MC` | `DL` | `TX` |
| `text` | `TE` | `SL` | — |
| `text-essay` | `TE` | `ESTB` | — ⚠️ |
| `matrix` | `Matrix` | `Likert` | `SingleAnswer` |
| `matrix-multi` | `Matrix` | `Likert` | `MultipleAnswer` |
| `description` | `DB` | `TB` | — |

**Selector codes:**
- `SAVR` = Single Answer Vertical Radio ✅
- `SAHR` = Single Answer Horizontal Radio ⚠️
- `MAVR` = Multiple Answer Vertical (checkboxes) ✅
- `MAHR` = Multiple Answer Horizontal ⚠️
- `DL` = Dropdown List ⚠️
- `SL` = Single Line text entry ✅
- `ESTB` = Essay Text Box ⚠️ (may be `ML` or `MLT`)
- `Likert` = Matrix/Likert selector ✅
- `TB` = Text / Descriptive block ✅
- `TX` = Sub-selector for text responses ✅

### Matrix Question Payload ✅

```json
{
  "QuestionType": "Matrix",
  "Selector": "Likert",
  "SubSelector": "SingleAnswer",
  "Choices": {
    "1": { "Display": "Row 1" },
    "2": { "Display": "Row 2" }
  },
  "ChoiceOrder": [1, 2],
  "Answers": {
    "1": { "Display": "Scale point 1" },
    "2": { "Display": "Scale point 2" }
  },
  "AnswerOrder": [1, 2]
}
```

Note: For Matrix, `Choices` = rows (statements), `Answers` = columns (scale) ✅

---

## RS — Response Set ⚠️

```json
{
  "Element": "RS",
  "PrimaryAttribute": "RS_xxxxxxxxxxxxxxx",
  "SecondaryAttribute": "Default Response Set",
  "Payload": null
}
```

---

## PROJ — Project Metadata ✅

```json
{
  "Element": "PROJ",
  "PrimaryAttribute": "CORE",
  "TertiaryAttribute": "1.1.0",
  "Payload": {
    "ProjectCategory": "CORE",
    "SchemaVersion": "1.1.0"
  }
}
```

- `PrimaryAttribute` is `"CORE"`, not `"ProjectCategory"` ✅

---

## QC — Question Count ⚠️

```json
{
  "Element": "QC",
  "PrimaryAttribute": "Survey Question Count",
  "SecondaryAttribute": "5",
  "Payload": null
}
```

`SecondaryAttribute` is the total question count as a string.

---

## Element Order ✅

Real Qualtrics exports use this element order:

```
BL → FL → PROJ → QC → RS → SCO → SO → SQ (one per question) → STAT
```

## Known Unknowns

- ❓ Exact selector for essay text entry (`ESTB` vs `ML` vs `MLT`) — `ESTB` used as best-guess
- ❓ Display logic / skip logic structure
- ❓ Randomization of choices
- ❓ Multi-language survey structure
- ❓ Whether block `Type: "Default"` vs `"Standard"` matters to Qualtrics on import
