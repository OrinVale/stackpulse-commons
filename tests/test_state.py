import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stackpulse", ROOT / "stackpulse.py")
stackpulse = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(stackpulse)


def posting(job_id: str, text: str, title: str = "Platform Engineer"):
    return stackpulse.Posting(
        source="lever",
        site="example",
        company="Example",
        job_id=job_id,
        title=title,
        location="Remote",
        url=f"https://jobs.example/{job_id}",
        text=text,
    )


class StateComparisonTests(unittest.TestCase):
    def test_first_observation_is_a_baseline(self):
        first = [posting("a", "Build integrations with Salesforce and Snowflake.")]
        self.assertEqual(stackpulse.detect_change_events(first, stackpulse.empty_state()), [])

    def test_new_job_after_a_baseline_is_reported(self):
        first = [posting("a", "Build integrations with Salesforce.")]
        state = stackpulse.compact_state(first, "2026-01-01T00:00:00+00:00")
        second = first + [posting("b", "Lead an OpenAI implementation and integration.", "AI Architect")]

        events = stackpulse.detect_change_events(second, state)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "NEW JOB")
        self.assertEqual(events[0]["new_technologies"], ["openai"])

    def test_new_technology_in_an_existing_job_is_reported(self):
        first = [posting("a", "Build integrations with Salesforce.")]
        state = stackpulse.compact_state(first, "2026-01-01T00:00:00+00:00")
        second = [posting("a", "Build integrations with Salesforce and Snowflake.")]

        events = stackpulse.detect_change_events(second, state)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "JOB CHANGED")
        self.assertEqual(events[0]["new_technologies"], ["snowflake"])

    def test_unchanged_job_is_not_reported(self):
        first = [posting("a", "Build integrations with Salesforce.")]
        state = stackpulse.compact_state(first, "2026-01-01T00:00:00+00:00")

        self.assertEqual(stackpulse.detect_change_events(first, state), [])


if __name__ == "__main__":
    unittest.main()
