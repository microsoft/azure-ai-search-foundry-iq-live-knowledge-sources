import contextlib
import io
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks import cli  # noqa: E402
from liveks.canary import protected_lifecycle_arguments  # noqa: E402
from liveks.config import resolve_config  # noqa: E402


@unittest.skipUnless(
    os.environ.get("LIVEKS_RUN_PROTECTED_MCP_SEARCH_INDEX") == "1",
    "protected MCP + Search Index contract is opt-in",
)
class ProtectedMcpSearchIndexContractTests(unittest.TestCase):
    def test_independent_sources_before_combined_routing(self):
        for name in (
            "LIVEKS_PROTECTED_CONFIG",
            "LIVEKS_INDEX_QUERY",
            "LIVEKS_INDEX_EXPECT_TERM",
            "LIVEKS_COMBINED_QUERY",
        ):
            self.assertTrue(os.environ.get(name, "").strip(), f"{name} must be configured")
        config_path = Path(os.environ["LIVEKS_PROTECTED_CONFIG"])
        config = resolve_config(profile=None, environment=None, config_path=config_path)
        report = cli.verify_report(
            config,
            query=os.environ["LIVEKS_INDEX_QUERY"],
            expected_terms=[os.environ["LIVEKS_INDEX_EXPECT_TERM"]],
            mcp_query=(
                os.environ.get("LIVEKS_MCP_QUERY")
                or "What must be configured for an Azure AI Search MCP Server knowledge source?"
            ),
            combined_query=os.environ["LIVEKS_COMBINED_QUERY"],
        )

        self.assertEqual(report["status"], "pass")
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(checks["search-index-retrieve"]["status"], "pass")
        self.assertEqual(checks["mcp-retrieve"]["status"], "pass")
        self.assertEqual(checks["combined-retrieve"]["status"], "pass")
        names = [check["name"] for check in report["checks"]]
        self.assertLess(names.index("search-index-retrieve"), names.index("mcp-retrieve"))
        self.assertLess(names.index("mcp-retrieve"), names.index("combined-retrieve"))
        self.assertTrue(checks["combined-retrieve"]["sourceTypes"])


@unittest.skipUnless(
    os.environ.get("LIVEKS_RUN_PROTECTED_MCP_SEARCH_INDEX_LIFECYCLE") == "1",
    "protected MCP + Search Index lifecycle canary is opt-in",
)
class ProtectedMcpSearchIndexLifecycleCanaryTests(unittest.TestCase):
    def test_guarded_e2e_always_requests_cleanup(self):
        config_path = Path(os.environ["LIVEKS_PROTECTED_CONFIG"])
        arguments = protected_lifecycle_arguments(
            config_path=config_path,
            environment=os.environ["LIVEKS_CANARY_ENVIRONMENT"],
            environ=os.environ,
        )
        self.assertIn("--cleanup", arguments)
        self.assertNotIn("--keep-resources", arguments)
        with contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(arguments)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
