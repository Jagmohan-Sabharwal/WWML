
import json
from pathlib import Path
import tempfile
import unittest
from wwml_youtube.adapter import NAMES, ROOT, prompt, run_tool

class IntegrationTests(unittest.TestCase):
    def test_all_skills_have_voice_and_instructions(self):
        for skill in NAMES:
            self.assertIn("Wealthy Wellness voice profile", prompt(skill, "test brief"))
            self.assertIn("test brief", prompt(skill, "test brief"))

    def test_hook_and_package(self):
        hook = run_tool("hook", ["--hook", "Why could your first 30 seconds cost you viewers?"])
        self.assertEqual(hook["status"], "pending_review")
        self.assertIn("verdict", hook["report"][0])
        pair = run_tool("package", ["--title", "7 Morning Habits Worth Copying", "--thumb", "START HERE"])
        self.assertIn("score", pair["report"][0])

    def test_transcript_tools_and_retention(self):
        with tempfile.TemporaryDirectory() as folder:
            transcript = Path(folder) / "transcript.srt"
            transcript.write_text("".join(
                f"{i+1}\n00:00:{i*8:02d},000 --> 00:00:{i*8+5:02d},000\n"
                f"Topic {i} explains savings and habits.\n\n" for i in range(7)
            ), encoding="utf-8")
            edit = run_tool("edit", [str(transcript)])
            self.assertTrue(edit["report"]["cuts"])
            chapters = run_tool("chapters", [str(transcript), "--target", "3"])
            self.assertTrue(chapters["report"]["valid"])
            csv = Path(folder) / "retention.csv"
            csv.write_text("position,retention\n" + "".join(
                f"{i*10},{100-i*5}\n" for i in range(11)), encoding="utf-8")
            retention = run_tool("retention", [str(csv), "--duration", "120",
                                               "--transcript", str(transcript)])
            self.assertEqual(retention["report"]["points"], 11)

    def test_viral_skips_thin_channels(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "videos.json"
            source.write_text(json.dumps(
                [{"channel": "A", "title": "Savings", "views": n} for n in (10,10,10,100)]
                + [{"channel": "B", "views": 100}]), encoding="utf-8")
            result = run_tool("viral", [str(source), "--min", "2"])
            self.assertEqual(result["report"]["outliers"][0]["multiple"], 10)
            self.assertEqual(result["report"]["skipped_thin_channels"][0][0], "B")

    def test_unknown_names_rejected(self):
        with self.assertRaises(ValueError):
            run_tool("../../bad", [])
        with self.assertRaises(ValueError):
            prompt("../../bad")

    def test_upstream_provenance(self):
        provenance = json.loads((ROOT / "third_party/youtube-agent/upstream.json").read_text())
        self.assertEqual(len(provenance["revision"]), 40)
        self.assertTrue((ROOT / "third_party/youtube-agent/LICENSE").is_file())

if __name__ == "__main__":
    unittest.main()
