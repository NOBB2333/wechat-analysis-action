import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

import wechat


class MarkdownReportNamingTests(unittest.TestCase):
    def test_render_report_writes_one_markdown_per_group(self):
        summaries = {
            "AI干中学Agentic Engineering": {
                "count": 2,
                "summary": "今日总结",
                "sample": "[10:00] Alice: hello",
            },
            "家": {
                "count": 1,
                "summary": None,
                "sample": "[11:00] Bob: hi",
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(wechat, "REPORTS_DIR", tmp):
                paths = wechat.render_report(summaries, "2026-06-01")

            basenames = sorted(os.path.basename(path) for path in paths)
            self.assertEqual(
                basenames,
                [
                    "report_2026-06-01_AI干中学Agentic_Engineering.md",
                    "report_2026-06-01_家.md",
                ],
            )
            for path in paths:
                self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
