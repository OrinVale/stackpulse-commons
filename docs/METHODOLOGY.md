# Methodology

## Purpose

StackPulse produces **review prompts**, not conclusions. A reported event means
that a public source changed between two successful observations according to a
small, explicit ruleset. It does not establish an organization's intent,
budget, adoption decision, or future activity.

## Eligible sources

A source is eligible only when it is:

- publicly accessible without a login;
- directly linkable;
- collected in a way that respects the source's terms, rate limits, and access
  controls;
- useful to compare over time.

The initial connector uses the public Lever postings endpoint. It does not
collect private job-board data, scrape authenticated areas, bypass access
controls, or enrich people.

## Observation model

For every successful crawl, StackPulse reads the public job identifier, title,
location, source URL, and configured technology terms in the current posting.
It then writes a compact state file containing only the source, site, job ID,
and observed terms needed for the next comparison. The original description
text is not retained in that state file.

The event rules are:

| Condition | Result |
| --- | --- |
| First successful crawl of a source | Baseline only; no event |
| New job ID with configured technology terms after a baseline | NEW JOB |
| Existing job ID gains configured technology terms | JOB CHANGED |
| Existing job without new configured terms | No event |

If a crawl returns no postings, the previous state is retained. A transient
source failure should not erase a baseline.

## Technology terms and priority score

The current terms are intentionally visible in stackpulse.py: CRM, ERP, data,
automation, revenue, AI, and cloud terms. The project uses a simple
review-priority score:

    18 + 8 × newly observed technology terms + 4 × change-language terms
    + 6 for relevant role wording

The score is capped at 100 and only scores of 30 or more are shown. It is not a
probability, confidence interval, valuation, or recommendation. A high score
only means that the record merits a human look before publication.

## Known limitations

- A public job may be stale, duplicated, mislabeled, or removed after a crawl.
- A term match can be ambiguous or reflect a skill preference rather than an
  active project.
- A source may change its API behavior, rate limits, or availability.
- Coverage is not representative of an entire sector or geography.
- The current generic taxonomy is not a Web3 taxonomy.

Reports must preserve the source link and observation time, describe these
limits, and avoid claims that go beyond the evidence.

## Reproducibility

The repository includes a deterministic fixture and state-comparison tests.
The scheduled workflow commits the compact state, source list, and generated
event outputs. Anyone reviewing a public release should be able to inspect the
rule set and trace a published event to its source URL.
