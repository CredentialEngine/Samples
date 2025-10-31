# CASE → CTDL/CTDLASN Exporter

This CLI script ingests a **CASE CFPackage** (JSON) and produces:

- **Individual Course JSON** files (one per course) using the **CTDL** context  
  `https://credreg.net/ctdl/schema/context/json`
- **Individual Competency Framework JSON** files (one per course) using the **CTDLASN** context  
  `https://credreg.net/ctdlasn/schema/context/json`

It also generates a compact **validation report** (`validations.json`) that only lists items which have validation errors.

---

## Features

- Builds `ceterms:Course` nodes from CASE `CFItems` typed as **Course**
- Derives a **per-course Competency Framework** containing the competencies linked to that course
- Populates `ceterms:teaches` on each course with alignments to competencies and backfills:
  - `ceterms:framework` → the created framework `@id`
  - `ceterms:frameworkName` → framework name (language-mapped if available)
- Writes **two sets** of files:
  - `courses_out/course_<CTID>.json` (CTDL context)
  - `frameworks_out/framework_<course CTID>.json` (CTDLASN context)
- **Validation** (errors only) for:
  - Courses: required fields and CE Registry URI checks
  - Frameworks & Competencies: basic CTDLASN sanity checks

---

## Requirements

- Python 3.8+
- Internet access to fetch the CASE package (unless you proxy it locally)
- A URL to a **CASE CFPackage** (JSON)

> The script uses a simple `User-Agent` to retrieve the package and a 60s timeout.

---

## Installation

No package install needed. Clone or copy the script to your project:

```bash
chmod +x case_to_ctdl.py
```

---

## Running the Script

```bash
./case_to_ctdl.py
```

You’ll be prompted for:

1. **CASE CFPackage URL**  
   e.g., `https://example.org/path/to/cfpackage.json`
2. **Output folder for COURSE files** (default: `courses_out`)
3. **Output folder for FRAMEWORK files** (default: `frameworks_out`)
4. **Validation report path** (default: `validations.json`)
5. **Registry base URL** (default: `https://credentialengineregistry.org/resources/`)

---

## Inputs

- **CFPackage JSON** structure (CASE):  
  The script expects keys:
  - `CFPackage.CFDocument` (language, document URI, etc.)
  - `CFPackage.CFItems` (items including Courses and Competencies)
  - `CFPackage.CFAssociations` (relations to build hierarchy, `isChildOf`/`isPartOf`)

> Item type comparison is case-insensitive for `"Course"`.

---

## Outputs

### 1) Courses (CTDL)
- **Path**: `<courses_out>/course_<CTID>.json`
- **Context**: `https://credreg.net/ctdl/schema/context/json`
- **Shape**:
  ```json
  {
    "@context": "https://credreg.net/ctdl/schema/context/json",
    "@graph": [
      {
        "@id": "https://credentialengineregistry.org/resources/ce-xxxxxxxx-....",
        "@type": "ceterms:Course",
        "ceterms:ctid": "ce-xxxxxxxx-....",
        "ceterms:name": { "en": "Intro to ..." },
        "ceterms:description": { "en": "..." },
        "ceterms:inLanguage": "en",
        "ceterms:codedNotation": "COURSE-101",
        "ceterms:subjectWebpage": "https://...",
        "ceterms:teaches": [
          {
            "@type": "ceterms:CredentialAlignmentObject",
            "ceterms:framework": "https://credentialengineregistry.org/resources/ce-...",
            "ceterms:frameworkName": { "en": "Intro to ..." },
            "ceterms:targetNode": "https://credentialengineregistry.org/resources/ce-...",
            "ceterms:targetNodeName": { "en": "Competency text ..." }
          }
        ],
        "ceterms:lifeCycleStatusType": "https://credentialengineregistry.org/resources/ce-...", 
        "ceterms:ownedBy": "https://credentialengineregistry.org/resources/ce-..." 
      }
    ]
  }
  ```

### 2) Competency Frameworks (CTDLASN)
- **Path**: `<frameworks_out>/framework_<course CTID>.json`
- **Context**: `https://credreg.net/ctdlasn/schema/context/json`
- **Shape**:
  - Top node: `ceasn:CompetencyFramework` with deterministic CTID derived from the course CTID
  - Graph includes all descendant competencies under the course roots, with local `ceasn:isPartOf`, `ceasn:hasChild`, and reciprocal `ceasn:isChildOf`

### 3) Validation Report
- **Path**: `validations.json`
- **Contains only items with errors** (frameworks, competencies, and courses).

---

## Validation Rules

### Courses (`ceterms:Course`)
- Required fields:
  - `ceterms:ctid`
  - `ceterms:name`
  - `ceterms:description`
  - `ceterms:inLanguage`
  - `ceterms:lifeCycleStatusType`
  - At least one of `ceterms:ownedBy` or `ceterms:offeredBy`
- URI checks: `ownedBy` / `offeredBy` must be valid CE Registry URIs.

### Frameworks (`ceasn:CompetencyFramework`)
- Required fields:
  - `ceterms:ctid`
  - `ceasn:name`
  - `ceasn:description`
  - `ceasn:inLanguage`
  - `ceasn:publisher` must be CE Registry URI(s)

### Competencies (`ceasn:Competency`)
- Required fields:
  - `ceterms:ctid`
  - `ceasn:competencyText`
  - `ceasn:isPartOf`

---

## Example Session

```
$ ./case_to_ctdl.py
Enter CASE CFPackage URL: https://example.org/my_cfpackage.json
Output folder for COURSE files [courses_out]:
Output folder for FRAMEWORK files [frameworks_out]:
Validation report [validations.json]:
Registry base URL [https://credentialengineregistry.org/resources/]:
Fetching CASE package...
Creating individual course and framework JSON files...
Created 12 course JSON files in 'courses_out' (CTDL)
Created 12 framework JSON files in 'frameworks_out' (CTDLASN)
— Validation summary —
Framework errors:  3
Competency errors: 5
Course errors:     7
Validation details saved to validations.json
```

---

## License

MIT (or your preferred license).
