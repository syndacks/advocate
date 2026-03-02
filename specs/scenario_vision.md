# Scenario Vision

## 1. Purpose

Scenarios are the primary mechanism for validating whether the case engine behaves like a trustworthy decision-support system.

They are not demo scripts and they are not prompt examples.

They exist to answer one question:

Given a realistic stream of evidence, does the system produce the right case state, flags, actions, and packet outputs?

## 2. Core Principles

- Scenarios are external to the application repo.
- Scenarios are black-box evaluations, not training data.
- Scenarios replay evidence over time, not static snapshots.
- Scenario assertions target state, actions, and packet outputs.
- Scenario fixtures must be realistic enough to expose operational pain.

## 3. What A Scenario Represents

A scenario represents one full opportunity narrative such as:

- promising role with strong fit but incomplete prep
- application submitted with no follow-up and stale outreach
- interview progression with contradictory recruiter signals
- rejection with enough evidence to explain what happened
- offer with compensation ambiguity
- dead pipeline that should close automatically

## 4. Scenario Categories

The first scenario suite should include:

### 4.1 Intake And Readiness

- missing resume alignment
- missing requirement coverage
- missing quantified impact examples

### 4.2 External Engagement

- recruiter outreach received
- application submitted but no response
- stale follow-up window

### 4.3 Interview Lifecycle

- recruiter screen to panel progression
- interview feedback updates stage
- timeline evidence arrives out of order

### 4.4 Contradictions

- conflicting compensation numbers
- conflicting recruiter identity
- conflicting outcome signals
- role mismatch between posting and candidate materials

### 4.5 Terminal Outcomes

- rejected
- withdrawn
- accepted elsewhere
- offer under negotiation

## 5. What Each Scenario Must Assert

At minimum:

- final `stage_label`
- final `completion_ratio` band
- required `missing_components`
- required `stale_components`
- required `contradicted_components`
- top ranked actions
- packet artifact existence
- key packet citations when applicable

## 6. Scenario Repo Shape

Recommended structure:

```text
scenario-repo/
  scenarios/
    intake_missing_quantified_impact/
      scenario.yaml
      evidence/
    stale_follow_up_after_application/
      scenario.yaml
      evidence/
    conflicting_compensation_offer/
      scenario.yaml
      evidence/
```

Each `scenario.yaml` should define:

- candidate profile seed
- case metadata
- ordered evidence arrivals
- waits or flow completion conditions
- expected final assertions

## 7. Minimal Scenario Example

```yaml
scenario_id: stale_follow_up_after_application
case:
  company_name: ExampleCo
  role_title: Senior Product Manager
evidence_sequence:
  - at: 2026-02-01T09:00:00Z
    file: evidence/job_posting.txt
    evidence_type: web_job_posting
  - at: 2026-02-02T11:00:00Z
    file: evidence/tailored_resume.pdf
    evidence_type: document_pdf
  - at: 2026-02-03T15:00:00Z
    file: evidence/application_confirmation.eml
    evidence_type: message_email
assertions:
  final_stage_label: submitted
  stale_components_contains:
    - engagement.follow_up_contact
  top_actions_contains:
    - send_follow_up
```

## 8. Evaluation Boundary

Scenarios must never be readable by:

- prompt templates
- retrieval corpora
- merge rules
- application heuristics

They are test fixtures only.

## 9. Repository Policy

Implementation work is not complete unless it strengthens or preserves the scenario vision.

If a feature cannot be evaluated through a realistic scenario, the feature is underspecified.
