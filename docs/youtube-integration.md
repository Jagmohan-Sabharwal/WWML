
# YouTube editorial integration

The repository's main branch contained only a README when this integration was prepared.
This supplies project-local skills and an executable Python adapter. There is no existing
production engine in this checkout to patch. No provider credentials are required for these tools.

## Use

From the repository root, with Python 3.11 or later:

```bash
python -m unittest discover -s tests -v
python -m wwml_youtube prompt yt-script --brief "7 morning habits worth copying"
python -m wwml_youtube tool hook --hook "Why could your first 30 seconds cost you viewers?"
python -m wwml_youtube tool package --title "7 Morning Habits Worth Copying" --thumb "START HERE"
python -m wwml_youtube tool edit /absolute/path/subtitles.srt
python -m wwml_youtube tool chapters /absolute/path/subtitles.srt --target 5
python -m wwml_youtube tool retention /absolute/path/retention.csv --duration 240 --transcript /absolute/path/subtitles.srt
python -m wwml_youtube tool viral /absolute/path/videos.json --min 2
```

The prompt command assembles instructions; an LLM must execute them. It does not generate a
script by itself. All six tool commands execute the upstream Python utilities and return JSON
with status pending_review. Restart Codex to discover project-local skills.

## Production engine interface

```python
from wwml_youtube.adapter import prompt, run_tool

script_task = prompt("yt-script", project_brief)
# Pass script_task to the engine's configured LLM executor.
hook_report = run_tool("hook", ["--hook", selected_hook])
# Store hook_report in the project's review records.
```

| WWML stage | Skill or tool | Consumer |
|---|---|---|
| Topic research | yt-viral, yt-audit | Research brief and backlog |
| Calendar | yt-plan | Production dashboard |
| Script | yt-script, hook | Narration preparation |
| Packaging | yt-package, package | Canva thumbnail brief |
| Editing | yt-edit, edit | Proposed Blender cuts |
| Metadata | yt-seo, yt-chapters, chapters | Metadata and description |
| Repurposing | yt-shorts | Shorts production queue |
| Performance review | yt-retention, retention | Five-video improvement review |
| Community | yt-comment | Draft replies |

Higgsfield/OpenAI narration, asset resolution, Blender rendering, Canva design creation,
YouTube OAuth/upload and live analytics collection remain engine responsibilities.
None is implemented by the upstream repo or this adapter. Never treat an editorial report
as approval of Narration.wav, subtitles.srt, VisualPlan.json, thumbnail.png or publish_manifest.json.
Render verification requires checking actual rendered media.

## Upstream and limitations

All eleven skill folders are vendored unchanged under .codex/skills. Relative dependencies
between yt-chapters, yt-retention and yt-edit, and between yt-viral and yt-script are preserved.
The MIT license and pinned revision/file hashes are recorded in third_party/youtube-agent.
Update deliberately after reviewing an upstream diff.

Skills use ~/.codex/youtube/voice.md when invoked directly; instruct Codex to use the
project profile at .codex/youtube/voice.md. The adapter includes that profile automatically.
It is a brief-based starting profile, not a measured imitation of Arthur's delivery.

Upstream scores are heuristic advice, not forecasts of CTR or retention.
Chapter titles need editorial revision. Edit proposals require checking against footage;
overlapping cuts may overcount removed time. The upstream transcript parser supports
Whisper object JSON, SRT and VTT; plain segment-list JSON currently fails.
Retention's axis is inferred from the maximum position: seconds-only exports of short
videos can be misclassified as percentages. Normalize to percentage positions and pass
the actual duration when using that utility. Missing exports cannot be replaced with
invented analytics.

Upstream skills end with "ship it, or change it?" and do not publish. The adapter does not
implement this as a runtime approval mechanism. WWML's engine owns publishing policy.
