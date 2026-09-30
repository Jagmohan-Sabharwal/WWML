
"""Dependency-free boundary between upstream editorial tools and WWML.

Prompts need an LLM executor supplied by the production engine.
Tool reports are proposals; they never edit media or approve publication.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".codex" / "skills"
NAMES = ("yt-script", "yt-package", "yt-viral", "yt-retention", "yt-edit",
         "yt-plan", "yt-comment", "yt-seo", "yt-chapters", "yt-shorts", "yt-audit")
TOOLS = {
    "hook": ("yt-script", "hookscore.py"),
    "package": ("yt-package", "title.py"),
    "edit": ("yt-edit", "deadair.py"),
    "chapters": ("yt-chapters", "chapters.py"),
    "retention": ("yt-retention", "retention.py"),
    "viral": ("yt-viral", "swipe.py"),
}

def prompt(skill, brief=""):
    if skill not in NAMES:
        raise ValueError("Unknown skill: " + skill)
    voice = (ROOT / ".codex/youtube/voice.md").read_text(encoding="utf-8")
    instructions = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    return (
        "WWML editorial task. Use the project voice profile below instead of a global profile.\n"
        "Return a reviewable editorial artifact. Reports cannot mark render verification, "
        "thumbnail review, or publishing approval as passed. "
        "WWML's production engine owns execution and publishing policy.\n\n"
        + voice + "\n\n" + instructions + "\n\nPROJECT BRIEF\n" + brief
    )

def run_tool(name, args, timeout=30):
    if name not in TOOLS:
        raise ValueError("Unknown tool: " + name)
    skill, script = TOOLS[name]
    argv = [str(a) for a in args]
    if "--json" not in argv:
        argv.append("--json")
    proc = subprocess.run(
        [sys.executable, str(SKILLS / skill / script), *argv],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    if proc.returncode:
        raise RuntimeError(f"{name} failed ({proc.returncode}): {proc.stderr or proc.stdout}")
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} did not return JSON") from exc
    return {"schema_version": 1, "tool": name, "status": "pending_review",
            "report": report}
