# State Machine Semantics

## 1. Purpose

This document defines the executable semantics for the case state machine.

It governs:

- component presence
- confidence thresholds
- staleness
- contradictions
- completion ratios
- stage derivation
- next best action generation

## 2. Inputs

Each evaluation run consumes:

- the latest prior `CaseStateVersion`, if any
- all relevant `component_observations`
- the rules in [case_requirements.yaml](/Users/dacks/repos/advocate/case_requirements.yaml)
- the canonical observation schemas in [specs/observations.md](/Users/dacks/repos/advocate/specs/observations.md)
- the canonical evidence taxonomy in [specs/evidence_taxonomy.md](/Users/dacks/repos/advocate/specs/evidence_taxonomy.md)
- a deterministic evaluation timestamp `now`

## 3. Component Evaluation

For each component key:

1. Filter observations to the matching `component_key`.
2. Discard observations whose underlying evidence type is not listed in `accepted_evidence_types`.
3. Discard observations below the component `minimum_confidence`, or the global default if unspecified.
4. Order remaining observations by:
   - higher normalized reliability
   - higher confidence
   - newer evidence timestamp
5. Materialize the best-supported value as the current component value.

## 4. Presence, Missing, Invalid, And Stale

Definitions:

- `present`: at least one valid observation survived evaluation
- `missing`: component is required and not present
- `invalid`: observations exist but all were rejected by evidence type or confidence rules
- `stale`: component is present, has `stale_after_days`, and `last_updated + stale_after_days < now`

`completed` and `present` are equivalent in the first implementation.

## 5. Contradictions

Contradictions are evaluated after component materialization.

For each contradiction rule:

1. Collect valid observations for the referenced normalized field paths.
2. Normalize values to a comparable representation.
3. If materially different values remain from distinct evidence records, mark the contradiction as present.

Material difference means:

- strings differ after normalization for identity-style fields
- money values differ by more than the configured tolerance
- enums differ exactly

Contradictions do not erase the component. They add a contradiction flag to the state.

## 6. Completion Ratio

The completion ratio is:

`sum(weights for present components) / sum(weights for all weighted components)`

Rules:

- components without explicit weights count as `1.0`
- optional components may still contribute if given a weight
- stale components remain present but also appear in `stale_components`
- contradicted components remain present but also appear in `contradicted_components`

## 7. Stage Resolution

Stage rules are evaluated in the order they appear in [case_requirements.yaml](/Users/dacks/repos/advocate/case_requirements.yaml).

The first matching stage wins.

If no stage matches, use `intake`.

## 8. Stage Operator Semantics

All keys under a single `when` clause are ANDed together.

Supported operators:

- `completion_ratio_lt`
- `completion_ratio_lte`
- `completion_ratio_gt`
- `completion_ratio_gte`
- `completed_components_all`
- `completed_components_any`
- `completed_components_not`
- `stale_components_any`
- `stale_components_all`
- `contradictions_any`
- `field_equals_any`

Operator meanings:

- `completed_components_all`: every listed component is present
- `completed_components_any`: at least one listed component is present
- `completed_components_not`: every listed component is not present
- `stale_components_any`: at least one listed component is stale
- `stale_components_all`: every listed component is stale
- `contradictions_any`: at least one listed contradiction key is present
- `field_equals_any`: the normalized field path equals one of the allowed values

## 9. Action Rule Semantics

Action rules are evaluated after stage resolution.

All conditions on an action rule are ANDed together.

Supported action operators:

- `when_missing_any`
- `when_missing_all`
- `when_stale_any`
- `when_completed_any`
- `when_completed_all`
- `when_contradictions_any`
- `when_field_equals_any`
- `when_stage_in`

Action rules may all match. This is not first-match-wins.

Matched actions are sorted by ascending `priority`.

## 10. Normalized Field Resolution

Field references must use fully qualified normalized paths from [specs/observations.md](/Users/dacks/repos/advocate/specs/observations.md).

Examples:

- `decision.outcome_signal.status`
- `decision.compensation_signal.amount`
- `opportunity.recruiter_or_decision_maker.contact_email`

Paths that do not exist in the observation spec are invalid.

## 11. Reliability

Base reliability is determined by `evidence_type_reliability` in [case_requirements.yaml](/Users/dacks/repos/advocate/case_requirements.yaml).

The first implementation computes:

`normalized_reliability = evidence_type_reliability * observation_confidence`

This is only for ranking candidate observations, not for replacing explicit component confidence thresholds.

## 12. Output Contract

Every state evaluation must output:

- `derived_components`
- `missing_components`
- `invalid_components`
- `stale_components`
- `contradicted_components`
- `completion_ratio`
- `stage_label`
- `recommended_actions`

These outputs populate `CaseStateVersion`.
