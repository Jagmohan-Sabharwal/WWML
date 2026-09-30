# WWML

WWML is the Wealthy Wellness documentary production platform.

## YouTube editorial integration

Includes 11 project-local YouTube skills, six dependency-free editorial tools,
a Wealthy Wellness voice profile and a Python adapter.

See [integration instructions](docs/youtube-integration.md).

```bash
python -m unittest discover -s tests -v
python -m wwml_youtube prompt yt-script --brief "7 morning habits worth copying"
```

This checkout contains the editorial integration. The production engine, frontend,
database and provider integrations described in the original milestone are not present.
