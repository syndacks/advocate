# Evidence Taxonomy

## 1. Purpose

This document defines the canonical evidence vocabulary for the repository.

Every other spec must use these terms consistently. If a file uses a different label for the same concept, this taxonomy wins.

## 2. Core Model

Each `EvidenceItem` has three separate classifications:

- `source_channel`: where it came from
- `evidence_type`: what kind of record it is
- `mime_type`: raw storage format

These are not interchangeable.

## 3. Canonical `source_channel`

Allowed values:

- `manual_ui`
- `email_forward`
- `browser_clip`
- `calendar_import`
- `api`
- `bulk_import`
- `system_generated`

Definition:

- `source_channel` describes ingress only.
- It must not be used to infer semantics like compensation, recruiter contact, or offer status.

## 4. Canonical `evidence_type`

Allowed values:

- `document_pdf`
- `document_image`
- `message_email`
- `note_text`
- `transcript_text`
- `structured_json`
- `calendar_event`
- `web_job_posting`

Definition:

- `evidence_type` is the semantic record class used by extraction, merge, and rules.
- `accepted_evidence_types` in [case_requirements.yaml](/Users/dacks/repos/advocate/case_requirements.yaml) must only use values from this list.

## 5. Mapping Examples

| Real input | `source_channel` | `evidence_type` | Notes |
| --- | --- | --- | --- |
| Uploaded resume PDF | `manual_ui` | `document_pdf` | Resume semantics are extracted later |
| Forwarded recruiter email | `email_forward` | `message_email` | The sender is metadata, not type |
| Pasted follow-up draft | `manual_ui` | `note_text` | |
| Imported interview transcript | `api` | `transcript_text` | |
| Calendar invite ICS | `calendar_import` | `calendar_event` | |
| Clipped job posting page | `browser_clip` | `web_job_posting` | |
| Structured form submission | `manual_ui` | `structured_json` | |
| Screenshot of offer details | `manual_ui` | `document_image` | |

## 6. Reliability Defaults

Reliability defaults are keyed by `evidence_type`, not by ad hoc labels.

Canonical keys:

- `document_pdf`
- `document_image`
- `message_email`
- `note_text`
- `transcript_text`
- `structured_json`
- `calendar_event`
- `web_job_posting`

If finer-grained reliability is needed later, add an extractor- or metadata-based override layer. Do not invent new taxonomy keys inside feature configs.

## 7. Normalization Rules

- A forwarded email remains `message_email` even if it contains compensation, scheduling, or rejection information.
- A calendar invite remains `calendar_event` even if it implies interview progression.
- A screenshot remains `document_image` even if it shows an offer or rejection.
- Semantic meaning must be extracted into observations, not encoded in `evidence_type`.

## 8. Repository Rule

The following files must align to this taxonomy:

- [architecture.md](/Users/dacks/repos/advocate/architecture.md)
- [schema.md](/Users/dacks/repos/advocate/schema.md)
- [case_requirements.yaml](/Users/dacks/repos/advocate/case_requirements.yaml)
- [specs/observations.md](/Users/dacks/repos/advocate/specs/observations.md)
- [specs/state_machine.md](/Users/dacks/repos/advocate/specs/state_machine.md)
