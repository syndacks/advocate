# Observation Schemas

## 1. Purpose

This document defines the canonical normalized shapes stored in `component_observations.value_json`.

Without these schemas, the state machine cannot evaluate contradictions, stages, or actions deterministically.

## 2. Observation Envelope

Every observation row has this envelope at the table level, as defined in [schema.md](/Users/dacks/repos/advocate/schema.md):

- `case_id`
- `evidence_id`
- `component_key`
- `value_json`
- `confidence`
- `source_type`
- `extractor_version`

Inside `value_json`, each component must follow the component-specific schema below.

## 3. General Rules

- Field names are stable and snake_case.
- Dates use ISO 8601 strings.
- Money values use integer minor units when practical or explicit `currency` plus numeric values.
- Free-form narrative is allowed only in fields explicitly named `summary`, `explanation`, or `notes`.
- Contradiction checks operate on these normalized fields, not raw text.

## 4. Component Schemas

### 4.1 `identity.resume_aligned`

```json
{
  "resume_variant_id": "string",
  "target_role_title": "string",
  "target_role_family": "string",
  "alignment_summary": "string",
  "matching_requirement_ids": ["string"],
  "missing_requirement_ids": ["string"]
}
```

### 4.2 `identity.portfolio_or_work_samples`

```json
{
  "sample_ids": ["string"],
  "sample_types": ["demo", "writing", "code", "design"],
  "summary": "string"
}
```

### 4.3 `identity.target_narrative`

```json
{
  "summary": "string",
  "motivation": "string",
  "role_fit_claim": "string"
}
```

### 4.4 `opportunity.target_role`

```json
{
  "company_name": "string",
  "role_title": "string",
  "role_family": "string",
  "role_level": "string",
  "job_posting_url": "string"
}
```

### 4.5 `opportunity.job_description`

```json
{
  "job_posting_url": "string",
  "requirements_summary": "string",
  "requirement_ids": ["string"],
  "preferred_qualifications": ["string"]
}
```

### 4.6 `opportunity.recruiter_or_decision_maker`

```json
{
  "contact_name": "string",
  "contact_email": "string",
  "contact_role": "string",
  "company_name": "string"
}
```

### 4.7 `opportunity.timeline_anchor`

```json
{
  "event_type": "applied|reply|screen|interview|follow_up|offer|rejection",
  "event_at": "2026-02-28T12:00:00Z",
  "notes": "string"
}
```

### 4.8 `relevance.top_matching_experience`

```json
{
  "experience_ids": ["string"],
  "matched_requirement_ids": ["string"],
  "summary": "string"
}
```

### 4.9 `relevance.quantified_impact_examples`

```json
{
  "examples": [
    {
      "label": "string",
      "metric_name": "string",
      "metric_value": "string",
      "context": "string"
    }
  ]
}
```

### 4.10 `relevance.requirement_coverage`

```json
{
  "covered_requirement_ids": ["string"],
  "uncovered_requirement_ids": ["string"],
  "coverage_ratio": 0.75
}
```

### 4.11 `relevance.gap_explanations`

```json
{
  "gaps": [
    {
      "requirement_id": "string",
      "explanation": "string",
      "mitigation": "string"
    }
  ]
}
```

### 4.12 `engagement.application_submitted`

```json
{
  "status": "submitted",
  "submitted_at": "2026-02-28T12:00:00Z",
  "channel": "career_site|referral|email|other"
}
```

### 4.13 `engagement.recruiter_contact`

```json
{
  "contact_name": "string",
  "contact_email": "string",
  "contact_direction": "inbound|outbound",
  "contacted_at": "2026-02-28T12:00:00Z"
}
```

### 4.14 `engagement.follow_up_contact`

```json
{
  "follow_up_type": "application|interview|offer|general",
  "contacted_at": "2026-02-28T12:00:00Z",
  "recipient_name": "string",
  "recipient_email": "string"
}
```

### 4.15 `engagement.interview_feedback`

```json
{
  "stage_name": "string",
  "interviewed_at": "2026-02-28T12:00:00Z",
  "feedback_summary": "string",
  "result_signal": "advance|hold|unclear|reject"
}
```

### 4.16 `decision.outcome_signal`

```json
{
  "status": "rejected|withdrawn|closed_no_response|advance|offer|verbal_offer|accepted|hold",
  "decided_at": "2026-02-28T12:00:00Z",
  "notes": "string"
}
```

### 4.17 `decision.compensation_signal`

```json
{
  "currency": "USD",
  "amount": 250000,
  "range_min": 220000,
  "range_max": 260000,
  "equity_summary": "string"
}
```

### 4.18 `decision.close_reason`

```json
{
  "reason": "rejected|withdrawn|accepted_elsewhere|timing|misaligned_role|other",
  "summary": "string"
}
```

## 5. Merge Rules

- Multiple observations may exist for the same component.
- The merge engine chooses the materialized component state using recency, confidence, reliability, and contradiction rules from [specs/state_machine.md](/Users/dacks/repos/advocate/specs/state_machine.md).
- The raw observations remain append-only even when superseded.

## 6. Contradiction Field Paths

The following normalized field paths are valid contradiction targets:

- `decision.compensation_signal.amount`
- `decision.compensation_signal.range_min`
- `decision.compensation_signal.range_max`
- `opportunity.recruiter_or_decision_maker.contact_name`
- `opportunity.recruiter_or_decision_maker.contact_email`
- `opportunity.target_role.role_title`
- `opportunity.target_role.role_family`
- `opportunity.target_role.role_level`
- `decision.outcome_signal.status`

Only these normalized paths should be referenced by contradiction rules unless this document is updated first.
