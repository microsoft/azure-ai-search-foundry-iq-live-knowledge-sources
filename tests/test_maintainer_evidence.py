import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MaintainerEvidenceTests(unittest.TestCase):
    def test_v2_report_flows_through_summary_and_review_extractor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = root / "test-report.md"
            summary = root / "summary.md"
            report.write_text(
                "# LiveKS E2E Test Report\n\n"
                "- Deployment mode: `byo-fabric`\n"
                "- Location: `eastus`\n"
                "- Cleanup requested: `yes`\n"
                "- Generated: `2026-07-16 12:00 KST`\n\n"
                "| Status | Check | Note |\n"
                "| --- | --- | --- |\n"
                "| `PASS` | app-status | HTTP 200 |\n"
                "| `PASS` | mcp-retrieve | MCP evidence |\n"
                "| `PASS` | fabric-retrieve | Fabric evidence |\n"
                "| `PASS` | combined-retrieve | Fabric selected |\n"
                "| `PASS` | fabric-cleanup | BYO preserved |\n"
                "| `PASS` | azure-cleanup | deleted |\n"
                "| `PASS` | resource-group-absent | absent |\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/maintainers/summarize-e2e-evidence.py"),
                    str(report),
                    "--output",
                    str(summary),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            extracted = subprocess.run(
                [sys.executable, str(ROOT / "scripts/maintainers/extract-review-evidence.py"), str(summary)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        self.assertIn("Microsoft Learn MCP KS PASS in byo-fabric", extracted)
        self.assertIn("Fabric Ontology KS PASS in byo-fabric", extracted)
        self.assertIn("Combined KB PASS in byo-fabric", extracted)
        self.assertIn("all required absence checks PASS in byo-fabric", extracted)


if __name__ == "__main__":
    unittest.main()
