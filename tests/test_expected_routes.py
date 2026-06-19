import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = REPO_ROOT / "evals" / "expected_routes.yaml"
RESPONSES_DIR = REPO_ROOT / "samples" / "responses"


SAMPLE_CONTRACTS = {
    "mcp-retrieve.sample.json": {
        "query": "Find Microsoft Learn guidance for Azure AI Search knowledge sources.",
    },
    "fabric-airline-ops-retrieve.sample.json": {
        "query": "Which airlines have the highest customer-care exposure this month?",
    },
    "combined-airline-ops-retrieve.sample.json": {
        "query": (
            "Using the Airline Ops ontology, identify the airline with the highest customer-care exposure this month. "
            "Also cite Microsoft Learn guidance for how I should validate activity, references, and sourceData in the "
            "Knowledge Base retrieve response."
        ),
    },
}


def parse_scalar(value):
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def load_expected_routes():
    routes = []
    current = None
    list_key = None

    for raw_line in ROUTES_PATH.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        stripped = raw_line.strip()
        if stripped.startswith("- ") and list_key and current is not None:
            current[list_key].append(parse_scalar(stripped[2:]))
            continue

        if stripped.startswith("- "):
            if current:
                routes.append(current)
            current = {}
            list_key = None
            stripped = stripped[2:]

        if current is None or ":" not in stripped:
            raise AssertionError(f"Unsupported expected route line: {raw_line}")

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value:
            current[key] = parse_scalar(value)
            list_key = None
        else:
            current[key] = []
            list_key = key

    if current:
        routes.append(current)

    return routes


def response_text(response):
    text_parts = []
    for message in response.get("response", []):
        for content in message.get("content", []):
            if content.get("type") == "text":
                text_parts.append(content.get("text", ""))
    return "\n".join(text_parts)


def stringify_source_data(response):
    parts = []
    for reference in response.get("references", []):
        source_data = reference.get("sourceData")
        if source_data is not None:
            parts.append(json.dumps(source_data, sort_keys=True))
    return "\n".join(parts)


class ExpectedRoutesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = load_expected_routes()
        cls.routes_by_query = {route["query"]: route for route in cls.routes}

    def test_expected_routes_are_well_formed(self):
        self.assertGreaterEqual(len(self.routes), 3)
        self.assertEqual(len(self.routes_by_query), len(self.routes), "expected route queries must be unique")

        for route in self.routes:
            with self.subTest(query=route.get("query")):
                self.assertIsInstance(route.get("query"), str)
                self.assertTrue(route["query"])

                has_single = "expected_knowledge_source" in route
                has_many = "expected_knowledge_sources" in route
                self.assertNotEqual(has_single, has_many, "use one source key shape per route")

                sources = route.get("expected_knowledge_sources") or [route.get("expected_knowledge_source")]
                self.assertTrue(all(isinstance(source, str) and source for source in sources))

    def test_offline_sample_responses_match_expected_routes(self):
        for sample_name, sample_contract in SAMPLE_CONTRACTS.items():
            with self.subTest(sample=sample_name):
                route = self.routes_by_query[sample_contract["query"]]
                response = json.loads((RESPONSES_DIR / sample_name).read_text(encoding="utf-8"))
                activity = response.get("activity", [])
                references = response.get("references", [])

                expected_sources = route.get("expected_knowledge_sources") or [route.get("expected_knowledge_source")]
                activity_sources = {item.get("knowledgeSourceName") for item in activity}
                reference_sources = {item.get("knowledgeSourceName") for item in references}
                seen_sources = activity_sources | reference_sources

                for source in expected_sources:
                    self.assertIn(source, seen_sources)

                expected_tool = route.get("expected_tool")
                if expected_tool:
                    tools = {item.get("toolName") for item in activity + references}
                    self.assertIn(expected_tool, tools)

                if route.get("expected_reference_source_data"):
                    self.assertTrue(any("sourceData" in item for item in references))

                expected_hint = route.get("expected_answer_hint")
                if expected_hint:
                    haystack = response_text(response) + "\n" + stringify_source_data(response)
                    self.assertIn(expected_hint, haystack)


if __name__ == "__main__":
    unittest.main()
