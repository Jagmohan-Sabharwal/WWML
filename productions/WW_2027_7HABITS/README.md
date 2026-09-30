# 7 Habits That Could Make You Richer AND Healthier in 2027

Narrated 16:9 review cut for Wealthy Wellness. Project source is project.json.
The workflow runs WWML's editorial utilities, synthesizes temporary narration, renders
a real H.264 MP4, writes measured sentence-level captions and validates the output.

Arthur voice is requested for the final version. Higgsfield workspace discovery, voice
listing and sandbox execution returned internal errors during this production.
The review cut uses Piper LibriTTS-R medium speaker 0, not Arthur. It contains original
motion typography and drawn graphics; no cinematic stock or generated footage is claimed.
Thumbnail is a locally rendered typography draft; Canva production is pending.
No music is added. No publishing is performed.

Source links and claim notes are in project.json and included in the output package.
Any meal or savings calculation is illustrative, in CAD.

## Render
Install ffmpeg, fonts-dejavu-core, Pillow and piper-tts.
Download the model with python -m piper.download_voices en_US-libritts_r-medium.
Then run:
```bash
python -m wwml_youtube.render_review productions/WW_2027_7HABITS/project.json --model en_US-libritts_r-medium.onnx --out output/WW_2027_7HABITS
```

The GitHub Actions artifact contains video_review.mp4, narration.wav, subtitles.srt,
thumbnail_draft.png, script.md, description.txt, timeline.json, editorial_review.json,
render_verification.json, contact_sheet.jpg and publish_manifest.json.
Technical checks do not replace visual or listening review.
