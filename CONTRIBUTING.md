# Contributing

## Setup

1. Install Xcode Command Line Tools, Python 3.11 or newer, and ffmpeg.
2. Run `scripts/setup.sh`.
3. Install the test runner: `python3 -m pip install pytest` inside `.venv`, or `pip install -e ".[dev]"`.

## Tests

```bash
.venv/bin/python -m pytest
```

The automated tests do not use a microphone, do not download model weights, and do not call a network service. They cover configuration, vocabulary replacement, the whisper.cpp request body, widget labels, cancellation of a transcription process, and a check that the source tree has no personal paths.

These checks are manual:

- `./scripts/blabla test-mic`
- Record from the simple-bar widget and confirm the text lands in the app that was focused.
- `./scripts/blabla transcribe some-long-recording.flac` for audio longer than a minute.
- Right-click the widget while a transcription is running and confirm it returns to `BlaBla`.

## Pull requests

- Keep model weights, recordings, `.venv`, and local config out of the diff.
- Do not add cloud API credentials or machine-specific paths.
- Note user-visible changes in `CHANGELOG.md`.

whisper.cpp is pinned in `scripts/setup.sh`. If you move that pin, confirm the `/inference` request fields still match `blabla/backends/whisper_cpp.py`.
