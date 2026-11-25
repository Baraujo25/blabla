# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.0] - 2026-11-25

### Added

- Local transcription with whisper.cpp and Whisper Large V3 Turbo.
- A resident `whisper-server` process so the model stays loaded between dictations.
- Configurable vocabulary replacements and an initial prompt built from those spellings.
- Copying the finished transcript to the clipboard. BlaBla does not paste it.
- Timing logs for recording, model load, transcription, post-processing, and stop-to-insert.
- `scripts/setup.sh`, sample config, tests, and a GitHub Actions workflow.

### Removed

- Google Cloud Speech-to-Text and the one-minute audio chunking path.
- Any requirement for the Google Cloud CLI or cloud credentials.
- Pasting the transcript into the focused application, and restoring the previous clipboard.

### Changed

- The project name is BlaBla.
- The helper bundle id is `app.blabla.helper`. Grant Microphone access for BlaBla.
