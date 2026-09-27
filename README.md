# StackPulse Commons

> Open-source, source-linked change intelligence for public-interest ecosystem research.

StackPulse Commons turns observable changes in publicly available organization
pages into reproducible, time-stamped change events. Its initial research
pilot will focus on how openly visible workforce and technology changes can
help communities understand ecosystem capacity without relying on private data,
opaque lead lists, or speculative claims.

**Status:** working prototype; pre-pilot. The current connector supports public
Lever job boards and uses a generic technology dictionary. A Web3-specific
source and taxonomy pilot is a funded roadmap item, not a claim about current
coverage.

## Why it exists

Ecosystem researchers and public-good builders often have to make decisions
with fragmented, late, or non-reproducible signals. Public hiring and
technology-change information is visible, but it is difficult to compare over
time responsibly.

StackPulse provides a small, inspectable baseline:

1. Collect only a public source with a direct link.
2. Normalize observations using an explicit terminology list.
3. Treat the first successful observation as a baseline, never as a change.
4. Report a new job or a changed technology mention only after a later crawl.
5. Preserve a compact comparison state instead of retaining job-description
   text.

See the [methodology](docs/METHODOLOGY.md) for limits, scoring, and
reproducibility details.

## What it is — and is not

StackPulse is a research and monitoring tool. It is **not**:

- a private-data collection system;
- a claim that an organization intends to buy, fund, or adopt anything;
- financial, investment, hiring, or business advice;
- a token, an investment offering, or a donor-reward program.

Every event should be reviewed against its source link before it is reused in a
report or decision.

## Run locally

    pip install -r requirements.txt
    python stackpulse.py demo --fixture fixtures/demo.json
    python -m unittest discover -s tests -v

To crawl selected public Lever boards:

    python stackpulse.py crawl-lever sambatv firemon \
      --state stackpulse-state.json \
      --html output/latest.html \
      --intent-html output/intent.html \
      --intent-json output/intent.json

The first successful crawl creates a baseline. Run the same source again to
produce only source-linked deltas.

## Funding and accountability

The project is preparing a 90-day public-interest pilot with defined
deliverables, a capped operating-cost line, and milestone reporting. Read:

- [Funding policy and treasury address](FUNDING.md)
- [90-day roadmap](docs/ROADMAP.md)
- [Governance and transparency commitments](docs/GOVERNANCE.md)
- [Funding application brief](docs/funding/grant-brief.md)
- [Campaign execution plan](docs/funding/campaign-plan.md)
- [Supporter FAQ](docs/funding/supporter-faq.md)

The current repository remains private while historical data and commit
metadata are audited. A clean public repository will be published before a
public fundraising campaign is promoted.

## Contributing and security

Contributions are welcome once the public repository is live. Proposed source
connectors must meet the public-source and reproducibility requirements in the
methodology. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md).

## License

Code and project materials are released under the [MIT License](LICENSE),
unless a source notice says otherwise.
