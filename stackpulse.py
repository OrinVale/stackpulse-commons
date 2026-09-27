#!/usr/bin/env python3
"""Create source-linked change events from publicly available job postings.

StackPulse deliberately keeps only a compact previous-state file. It does not
archive job-description text or attempt to infer private business intent.
"""

import argparse
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except Exception:  # Allows deterministic tests to run without requests.
    requests = None


STATE_VERSION = 1

TECH = {
    "crm": ["salesforce", "hubspot", "dynamics 365"],
    "erp": ["netsuite", "sap", "oracle erp"],
    "data": ["snowflake", "dbt", "databricks", "bigquery"],
    "automation": ["workato", "mulesoft", "boomi", "zapier"],
    "revenue": ["gong", "zoominfo", "leandata", "marketo"],
    "ai": ["claude", "openai", "chatgpt", "langchain", "llamaindex", "langgraph"],
    "cloud": ["aws", "azure", "gcp"],
}

CHANGE_TERMS = (
    "migration",
    "implement",
    "implementation",
    "transformation",
    "architect",
    "redesign",
    "integration",
    "integrate",
    "build",
    "rollout",
    "replace",
    "consolidat",
)

SENIORITY_TERMS = ("director", "head", "architect", "administrator", "manager", "engineer")


@dataclass(frozen=True)
class Posting:
    source: str
    site: str
    company: str
    job_id: str
    title: str
    location: str
    url: str
    text: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def site_key(posting: Posting) -> str:
    return f"{posting.source}:{posting.site}"


def mentions(text: str) -> list[tuple[str, str]]:
    low = (text or "").lower()
    found: list[tuple[str, str]] = []
    for category, terms in TECH.items():
        for term in terms:
            if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", low):
                found.append((category, term))
    return found


def technologies(posting: Posting) -> list[str]:
    return sorted({term for _, term in mentions(f"{posting.title} {posting.text}")})


def score_change(posting: Posting, added: list[str]) -> tuple[int, list[str]]:
    """Rank review priority, not commercial value or truthfulness."""
    low = f"{posting.title} {posting.text}".lower()
    change_language = [term for term in CHANGE_TERMS if term in low]
    score = 18 + 8 * len(added) + 4 * len(change_language)
    if any(term in posting.title.lower() for term in SENIORITY_TERMS):
        score += 6
    return min(score, 100), change_language


def empty_state() -> dict:
    return {"version": STATE_VERSION, "updated_at": None, "sites": {}}


def load_state(path: Path) -> dict:
    if not path.exists():
        return empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"State file is not valid JSON: {path}") from exc
    if data.get("version") != STATE_VERSION or not isinstance(data.get("sites"), dict):
        raise RuntimeError(f"State file has an unsupported format: {path}")
    return data


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def compact_state(postings: list[Posting], observed_at: str) -> dict:
    """Persist only what is needed to compare a future crawl.

    Description text is intentionally omitted. This keeps the committed state
    small and reduces retention of source material.
    """
    sites: dict[str, dict] = {}
    for posting in sorted(postings, key=lambda item: (item.source, item.site, item.job_id)):
        key = site_key(posting)
        site = sites.setdefault(
            key,
            {
                "company": posting.company,
                "jobs": {},
                "site": posting.site,
                "source": posting.source,
            },
        )
        if posting.job_id:
            site["jobs"][posting.job_id] = {"technologies": technologies(posting)}
    return {"version": STATE_VERSION, "updated_at": observed_at, "sites": sites}


def detect_change_events(postings: list[Posting], previous_state: dict) -> list[dict]:
    """Return only deltas against a prior successful observation for each site."""
    previous_sites = previous_state.get("sites", {})
    events: list[dict] = []

    for posting in sorted(postings, key=lambda item: (item.source, item.site, item.job_id)):
        current_technologies = technologies(posting)
        if not current_technologies or not posting.job_id:
            continue

        earlier_site = previous_sites.get(site_key(posting))
        if earlier_site is None:
            # First observation is a baseline, never a signal.
            continue

        prior_job = (earlier_site.get("jobs") or {}).get(posting.job_id)
        if prior_job is None:
            event_type = "NEW JOB"
            added = current_technologies
        else:
            old_technologies = set(prior_job.get("technologies") or [])
            added = sorted(set(current_technologies) - old_technologies)
            if not added:
                continue
            event_type = "JOB CHANGED"

        score, change_language = score_change(posting, added)
        if score < 30:
            continue
        events.append(
            {
                "change_language": change_language,
                "company": posting.company,
                "event": event_type,
                "location": posting.location,
                "new_technologies": added,
                "score": score,
                "source": posting.source,
                "source_site": posting.site,
                "title": posting.title,
                "url": posting.url,
            }
        )
    return sorted(events, key=lambda item: (-item["score"], item["company"], item["title"]))


def fetch_lever(site: str) -> list[Posting]:
    if requests is None:
        raise RuntimeError("requests is not installed")
    response = requests.get(
        f"https://api.lever.co/v0/postings/{site}?mode=json",
        timeout=20,
        headers={"User-Agent": "StackPulse/0.3 public-change-monitor"},
    )
    response.raise_for_status()
    postings: list[Posting] = []
    for job in response.json():
        categories = job.get("categories") or {}
        text = " ".join(
            filter(
                None,
                [
                    job.get("openingPlain"),
                    job.get("descriptionPlain"),
                    job.get("descriptionBodyPlain"),
                    job.get("additionalPlain"),
                ],
            )
        )
        postings.append(
            Posting(
                source="lever",
                site=site,
                company=site,
                job_id=job.get("id", ""),
                title=job.get("text", ""),
                location=categories.get("location", ""),
                url=job.get("hostedUrl", ""),
                text=text,
            )
        )
    return postings


def load_fixture(path: Path) -> list[Posting]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    postings: list[Posting] = []
    for index, row in enumerate(rows, start=1):
        company = row.get("company", "fixture")
        title = row.get("title", "")
        postings.append(
            Posting(
                source=row.get("source", "fixture"),
                site=row.get("site", company.lower().replace(" ", "-")),
                company=company,
                job_id=row.get("job_id", f"fixture-{index}"),
                title=title,
                location=row.get("location", ""),
                url=row.get("url", ""),
                text=row.get("text", ""),
            )
        )
    return postings


def render_html(rows: list[dict], path: Path, title: str, subtitle: str) -> None:
    cards: list[str] = []
    for row in rows:
        technologies_text = ", ".join(row.get("new_technologies", [])) or "—"
        language_text = ", ".join(row.get("change_language", [])) or "—"
        source_url = html.escape(row.get("url", ""), quote=True)
        cards.append(
            "<article>"
            f"<div class='score'>{row['score']}</div>"
            "<div>"
            f"<div class='event'>{html.escape(row.get('event', 'OBSERVED CHANGE'))}</div>"
            f"<h2>{html.escape(row.get('company', 'Unknown source'))}</h2>"
            f"<h3>{html.escape(row.get('title', 'Untitled posting'))}</h3>"
            f"<p>{html.escape(row.get('location', 'Location not stated'))}</p>"
            f"<p><strong>Observed technology change:</strong> {html.escape(technologies_text)}</p>"
            f"<p><strong>Change language:</strong> {html.escape(language_text)}</p>"
            f"<a href='{source_url}' rel='noopener noreferrer'>Open source posting</a>"
            "</div></article>"
        )
    page = f"""<!doctype html>
<html lang='en'>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{html.escape(title)}</title>
<style>
body{{font-family:ui-sans-serif,system-ui,sans-serif;max-width:980px;margin:40px auto;padding:0 18px;background:#f7f7f7;color:#181818}}
header{{margin-bottom:28px}} article{{display:grid;grid-template-columns:80px 1fr;gap:18px;background:#fff;margin:14px 0;padding:20px;border-radius:14px;box-shadow:0 1px 5px #0001}}
.score{{font-size:32px;font-weight:800}} .event{{display:inline-block;padding:4px 7px;border:1px solid #333;border-radius:8px;font-weight:700;font-size:.8rem}}
h1,h2,h3,p{{margin-top:0}} h2{{margin-bottom:4px}} h3{{font-weight:600;margin-bottom:8px}} p{{margin-bottom:8px}} a{{color:#111}} small{{color:#666}}
</style>
<header><h1>StackPulse</h1><p>{html.escape(subtitle)}</p><small>Generated {html.escape(now_iso())}</small></header>
{''.join(cards) or '<p>No verified changes since the previous successful crawl.</p>'}
</html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def crawl_lever(sites: list[str]) -> list[Posting]:
    postings: list[Posting] = []
    workers = min(12, max(1, len(sites)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_lever, site): site for site in sites}
        for future in as_completed(futures):
            site = futures[future]
            try:
                received = future.result()
                postings.extend(received)
                print(f"{site}: {len(received)} postings", file=sys.stderr)
            except Exception as exc:
                print(f"{site}: ERROR {exc}", file=sys.stderr)
    return postings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    demo = subcommands.add_parser("demo", help="Render deterministic fixture observations.")
    demo.add_argument("--fixture", default="fixtures/demo.json")
    demo.add_argument("--html", default="output/demo.html")
    demo.add_argument("--json", default="output/demo.json")

    crawl = subcommands.add_parser("crawl-lever", help="Crawl public Lever boards and report verified deltas.")
    crawl.add_argument("sites", nargs="+", help="Lever board slugs to crawl.")
    crawl.add_argument("--state", default="stackpulse-state.json", help="Compact state file persisted between crawls.")
    crawl.add_argument("--html", default="output/latest.html")
    crawl.add_argument("--intent-html", default="output/intent.html")
    crawl.add_argument("--intent-json", default="output/intent.json")

    args = parser.parse_args()
    if args.command == "demo":
        postings = load_fixture(Path(args.fixture))
        rows = []
        for posting in postings:
            observed = technologies(posting)
            score, change_language = score_change(posting, observed)
            rows.append(
                {
                    "change_language": change_language,
                    "company": posting.company,
                    "event": "FIXTURE OBSERVATION",
                    "location": posting.location,
                    "new_technologies": observed,
                    "score": score,
                    "source": posting.source,
                    "source_site": posting.site,
                    "title": posting.title,
                    "url": posting.url,
                }
            )
        rows.sort(key=lambda item: (-item["score"], item["company"], item["title"]))
        render_html(rows, Path(args.html), "StackPulse — fixture observations", "Deterministic example data for local validation.")
        write_json(Path(args.json), rows)
        print(json.dumps(rows, indent=2))
        return

    state_path = Path(args.state)
    previous_state = load_state(state_path)
    postings = crawl_lever(args.sites)
    if not postings:
        raise SystemExit("No postings fetched; previous state was left unchanged.")
    events = detect_change_events(postings, previous_state)
    observed_at = now_iso()
    write_state(state_path, compact_state(postings, observed_at))
    subtitle = "Source-linked changes in public postings. First observations are baselines, not signals."
    render_html(events, Path(args.html), "StackPulse — source-linked change events", subtitle)
    render_html(events, Path(args.intent_html), "StackPulse — verified change events", subtitle)
    write_json(Path(args.intent_json), events)
    print(json.dumps(events, indent=2))


if __name__ == "__main__":
    main()
