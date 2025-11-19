# CASE → CTDL/CTDLASN Mapping

This script ingests a **CASE CFPackage** (JSON) and produces, for **each course**:

- A **Course JSON** (CTDL context) 
- A **Competency Framework JSON** (CTDLASN context) 

It also outputs **validation report** (`validations.json`) listing **items with errors**.

## Requirements

- Python **3.8+**
- Internet access to fetch the CASE package (unless served locally)
- A URL to a **CASE CFPackage** (JSON)

> The script uses a simple `User-Agent` and a 60s timeout to retrieve the package.

## Installation

No package installation is required.
Simply save the script (e.g., case_to_ctdl.py), open your terminal, and navigate to its folder:

If you want to publish the courses and frameworks use the CASE-CTDL.py, please use the https://case.georgiastandards.org/ims/case/v1p1/CFPackages/caseidentifier
```bash
cd /path/to/your/script
python3 CASE-CTDL.py
```

If you want to publish the learning programs use the CASEPathways-CTDLLearningPrograms.py, please use the https://case.georgiastandards.org/ims/case/vext/CFPackages/caseidentifier

```bash
cd /path/to/your/script
python3 CASEPathways-CTDLLearningPrograms.py
```
## Inputs
You’ll be prompted for:

1. **CASE CFPackage URL**
2. **Publisher CTID(s)** (comma-separated)
3. **OwnedBy CTID(s)** (comma-separated)
4. **Add OfferedBy?** (y/N)

> Output folders are fixed defaults: `courses_out/`, `frameworks_out/`.  
> Registry base: `https://credentialengineregistry.org/resources/`.  
> Validation report path: `validations.json`.


## Example Session

```
$ ./case_to_ctdl.py
Enter CASE CFPackage URL: https://example.org/my_cfpackage.json
Enter publisher CTID(s): ce-0eb8a99d-2683-4b4b-a876-0c71a04f3e4f
Enter ownedBy CTID(s): ce-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
Do you want to add offeredBy? [y/N]: y
Enter offeredBy CTID(s): ce-ffffffff-1111-2222-3333-444444444444
Fetching CASE package...
Creating individual course and framework JSON files...
Created 12 course JSON files in 'courses_out'
Created 12 framework JSON files in 'frameworks_out'
— Validation summary —
Framework errors:  3
Competency errors: 5
Course errors:     1
Validation details saved to validations.json
```

## Output Files

### CASE-CTDL.py
- `courses_out/course_<COURSE_CTID>.json`
- `frameworks_out/framework_<COURSE_CTID>.json`
- `validations.json`- validation summary (frameworks, competencies, courses)
### CASEPathways-CTDLLearningPrograms.py
- `learningprograms_out/learningprogram_<LearningProgram_CTID>.json`
- `validations_pathways.json`- validation summary (learning programs)

## Validation Rules

### Courses (`ceterms:Course`)
- Required:
  - `ceterms:ctid`
  - `ceterms:name`
  - `ceterms:description`
  - `ceterms:inLanguage`
  - `ceterms:lifeCycleStatusType`
  - **At least one of** `ceterms:ownedBy` **or** `ceterms:offeredBy`
- URI checks: `ownedBy` / `offeredBy` must be **CE Registry URIs**.

### Frameworks (`ceasn:CompetencyFramework`)
- Required:
  - `ceterms:ctid`
  - `ceasn:name`
  - `ceasn:description`
  - `ceasn:inLanguage`
  - `ceasn:publisher` → **non-empty list** of CE Registry URIs

### Competencies (`ceasn:Competency`)
- Required:
  - `ceterms:ctid`
  - `ceasn:competencyText`
  - `ceasn:isPartOf`

### LearningPrograms (`ceterms:LearningProgram`)
- Required:
  - `ceterms:ctid`
  - `ceterms:name`
  - `ceterms:description`
  - `ceterms:inLanguage`
  - `ceterms:lifeCycleStatusType`
  - **At least one of** `ceterms:ownedBy` **or** `ceterms:offeredBy`
  -- `ceterms:isPreparationFor`
- URI checks: `ownedBy` / `offeredBy` must be **CE Registry URIs**.


The script writes `validations.json` with **only items that have errors**.





## CASE-CTDL Mapping

### Frameworks (`ceasn:CompetencyFramework`)

- **Competency Frameworks** are generated per course from the competencies connected to that course’s CASE items.

  - The framework’s ceasn:publisher is added from your comma-separated publisher input.
  - The framework @graph includes all child competencies under the framework.
  - Each included competency is added to the framework by setting ceasn:isPartOf to the framework @id.
  - The framework’s ceasn:description (if available) is taken from the course’s notes-derived “Course Description” section.
  - ceasn:inLanguage is set from the CASE document language.
  - ceterms:subjectWebpage is set from the CASE document’s CFDocumentURI/officialSourceURL when present.
  - Hierarchy of the competencies is added:
    - ceasn:hasTopChild lists the framework’s competencies (direct children of the competency framework).
    - ceasn:hasChild is added on parent competencies for their in-framework children.
    - Reciprocal ceasn:isChildOf is added on child competencies.

All outputs are **ready to POST** to the Registry’s **Graph Publish** endpoint, given that the validation is succesful and there are no errors.

```json
{
  {
  "PublishForOrganizationIdentifier": "ce-0eb8a99d-2683-4b4b-a876-0c71a04f3e4f",
  "GraphInput": {
    "@context": "https://credreg.net/ctdlasn/schema/context/json",
    "@id": "https://credentialengineregistry.org/resources/ce-2f7a1f5a-1234-5678-9abc-def012345678",
    "@graph": [
      {
        "@id": "https://credentialengineregistry.org/resources/ce-2f7a1f5a-1234-5678-9abc-def012345678",
        "@type": "ceasn:CompetencyFramework",
        "ceterms:ctid": "ce-2f7a1f5a-1234-5678-9abc-def012345678",
        "ceasn:name": { "en-US": "Personal Growth Mastery - Framework" },
        "ceasn:description": { "en-US": "Competencies aligned to the course ‘Personal Growth Mastery’." },
        "ceasn:inLanguage": [ "en-US" ],
        "ceasn:publisher": [
          "https://credentialengineregistry.org/resources/ce-0eb8a99d-2683-4b4b-a876-0c71a04f3e4f"
        ],
        "ceasn:hasTopChild": [
          "https://credentialengineregistry.org/resources/ce-11111111-2222-3333-4444-555555555555",
          "https://credentialengineregistry.org/resources/ce-66666666-7777-8888-9999-000000000000"
        ],
        "ceterms:subjectWebpage": "https://example.org/course/framework"
      },

      {
        "@id": "https://credentialengineregistry.org/resources/ce-11111111-2222-3333-4444-555555555555",
        "@type": "ceasn:Competency",
        "ceterms:ctid": "ce-11111111-2222-3333-4444-555555555555",
        "ceasn:competencyLabel": { "en-US": "Self-Awareness" },
        "ceasn:competencyText":  { "en-US": "Demonstrate the ability to reflect on personal strengths and areas for growth." },
        "ceasn:inLanguage": "en-US",
        "ceasn:isPartOf": "https://credentialengineregistry.org/resources/ce-2f7a1f5a-1234-5678-9abc-def012345678",
        "ceasn:hasChild": [
          "https://credentialengineregistry.org/resources/ce-aaaaaaa1-bbbb-cccc-dddd-eeeeeeeeeee1"
        ]
      },
      {
        "@id": "https://credentialengineregistry.org/resources/ce-aaaaaaa1-bbbb-cccc-dddd-eeeeeeeeeee1",
        "@type": "ceasn:Competency",
        "ceterms:ctid": "ce-aaaaaaa1-bbbb-cccc-dddd-eeeeeeeeeee1",
        "ceasn:competencyLabel": { "en-US": "Goal Setting" },
        "ceasn:competencyText":  { "en-US": "Set measurable, time-bound personal development goals and track progress." },
        "ceasn:inLanguage": "en-US",
        "ceasn:isPartOf": "https://credentialengineregistry.org/resources/ce-2f7a1f5a-1234-5678-9abc-def012345678",
        "ceasn:isChildOf": [
          "https://credentialengineregistry.org/resources/ce-11111111-2222-3333-4444-555555555555"
        ]
      },

      {
        "@id": "https://credentialengineregistry.org/resources/ce-66666666-7777-8888-9999-000000000000",
        "@type": "ceasn:Competency",
        "ceterms:ctid": "ce-66666666-7777-8888-9999-000000000000",
        "ceasn:competencyLabel": { "en-US": "Resilience" },
        "ceasn:competencyText":  { "en-US": "Apply coping strategies to adapt to challenges and setbacks." },
        "ceasn:inLanguage": "en-US",
        "ceasn:isPartOf": "https://credentialengineregistry.org/resources/ce-2f7a1f5a-1234-5678-9abc-def012345678"
      }
    ]
  }
}

}
```
### Course (`ceterms:course`)
- **Courses** are constructed from CASE `CFItems` whose type is `Course` (case-insensitive).
- For each course, a **per-course Competency Framework** is generated from competencies linked to the course:
  - The course’s `ceterms:teaches` is populated with alignments to those competencies.
  - `ceterms:framework` is backfilled with the created framework `@id`.
  - `ceterms:frameworkName` is set to the framework’s name (language-mapped when available).

All outputs are **ready to POST** to the Registry’s **Graph Publish** endpoint, given that the validation is succesful and there are no errors.

```json
{
  "PublishForOrganizationIdentifier": "ce-0eb8a99d-2683-4b4b-a876-0c71a04f3e4f",
  "GraphInput": {
    "@context": "https://credreg.net/ctdl/schema/context/json",
    "@id": "https://credentialengineregistry.org/resources/ce-9eb5105c-c5a5-4cf5-b6e8-e228400b9f34",
    "@graph": [
      {
        "@id": "https://credentialengineregistry.org/resources/ce-9eb5105c-c5a5-4cf5-b6e8-e228400b9f34",
        "@type": "ceterms:Course",
        "ceterms:ctid": "ce-9eb5105c-c5a5-4cf5-b6e8-e228400b9f34",
        "ceterms:name": { "en-US": "Personal Growth Mastery - Via Graph publish" },
        "ceterms:description": { "en-US": "..." },
        "ceterms:inLanguage": "en-US",
        "ceterms:codedNotation": "COURSE-101",
        "ceterms:subjectWebpage": "https://...",
        "ceterms:lifeCycleStatusType": {
          "@type": "ceterms:CredentialAlignmentObject",
          "ceterms:framework": "https://credreg.net/ctdl/terms/LifeCycleStatus",
          "ceterms:targetNode": "lifeCycle:Active",
          "ceterms:frameworkName": { "en-US": "Life Cycle Status" },
          "ceterms:targetNodeName": { "en-US": "Active" },
          "ceterms:targetNodeDescription": {
            "en-US": "Resource is active, current, ongoing, offered, operational, or available."
          }
        },
        "ceterms:ownedBy": [
          "https://credentialengineregistry.org/resources/ce-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        ],
        "ceterms:teaches": [
          {
            "@type": "ceterms:CredentialAlignmentObject",
            "ceterms:framework": "https://credentialengineregistry.org/resources/ce-...framework-ctid...",
            "ceterms:frameworkName": { "en-US": "Personal Growth Mastery - Via Graph publish" },
            "ceterms:targetNode": "https://credentialengineregistry.org/resources/ce-...competency-ctid...",
            "ceterms:targetNodeName": { "en-US": "Competency text ..." }
          }
        ]
        // Note: "ceterms:offeredBy" appears only if you choose to add it at runtime.
      }
    ]
  }
}
```

### Learning Programs(`ceterms:LearningProgram`)
 **Learning Programs** are constructed from CASE `CFItems` whose type is `Pathway` (case-insensitive).
- For each learning program, a **ceterms:conditionprofile** is added and linked to the related course:
  - `ceterms:isPreparationFor`  is set as the condition profile name.
  - `ceterms:targetLearningOpportunity` is backfilled with the course `@id`..

All outputs are **ready to POST** to the Registry’s **Graph Publish** endpoint, given that the validation is succesful and there are no errors.

```json
{
  "PublishForOrganizationIdentifier": "ce-14712aad-c6d4-4a3a-b271-d831cb865516",
  "GraphInput": {
    "@context": "https://credreg.net/ctdl/schema/context/json",
    "@id": "https://credentialengineregistry.org/resources/ce-7c497f4c-951f-4665-8c1a-da4f34ec4930",
    "@graph": [
      {
        "@id": "https://credentialengineregistry.org/resources/ce-7c497f4c-951f-4665-8c1a-da4f34ec4930",
        "@type": "ceterms:LearningProgram",
        "ceterms:ctid": "ce-7c497f4c-951f-4665-8c1a-da4f34ec4930",
        "ceterms:lifeCycleStatusType": {
          "@type": "ceterms:CredentialAlignmentObject",
          "ceterms:framework": "https://credreg.net/ctdl/terms/LifeCycleStatus",
          "ceterms:targetNode": "lifeCycle:Active",
          "ceterms:frameworkName": {
            "en-US": "Life Cycle Status"
          },
          "ceterms:targetNodeName": {
            "en-US": "Active"
          },
          "ceterms:targetNodeDescription": {
            "en-US": "Resource is active, current, ongoing, offered, operational, or available."
          }
        },
        "ceterms:ownedBy": [
          "https://credentialengineregistry.org/resources/ce-14712aad-c6d4-4a3a-b271-d831cb865516"
        ],
        "ceterms:inLanguage": [
          "en"
        ],
        "ceterms:name": {
          "en": "Business and Technology"
        },
        "ceterms:description": {
          "en": "Business and Technology"
        },
        "ceterms:subjectWebpage": "https://case.georgiastandards.org/ims/case/v1p1/CFItems/7c497f4c-951f-4665-8c1a-da4f34ec4930",
        "ceterms:isPreparationFor": [
          {
            "@type": "ceterms:ConditionProfile",
            "ceterms:name": {
              "en-US": "Is Preparation For"
            },
            "ceterms:description": {
              "en-US": "Students who complete this CTAE pathway will be prepared to earn the following courses of value."
            },
            "ceterms:targetLearningOpportunity": [
              "https://credentialengineregistry.org/resources/ce-099fee90-294c-42be-bcd1-dbb05bb0e023",
              "https://credentialengineregistry.org/resources/ce-1ed12fe7-ad46-448e-b843-83d554c0a471",
              "https://credentialengineregistry.org/resources/ce-eb9a1c5a-d61c-4580-a914-dbcfe4f0713d"
            ]
          }
        ]
      }
    ]
  }
}
```