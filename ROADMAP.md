# Roadmap

## MVP (this release)

- Click the simple-bar widget, speak, click again.
- Record with the existing ffmpeg capture and BlaBla microphone permission.
- Transcribe the whole recording locally with whisper.cpp, model `large-v3-turbo`, Metal on Apple Silicon.
- Keep the model loaded in `whisper-server` between dictations.
- Apply a JSON vocabulary of deterministic replacements, and pass those spellings as a whisper initial prompt.
- Copy the finished text to the clipboard. Do not type it into the focused app.
- Log durations only, unless transcript logging is turned on.
- Install with `scripts/setup.sh` from a clean checkout. No cloud account.

## Later

- Streaming partial text in the widget while you speak. The clipboard is updated only after you stop.
- An optional local model for punctuation and contextual correction, behind the same post-processing step. Replacements stay deterministic and run first.
- A built-in global hotkey. Today, bind `scripts/blabla toggle` from skhd, Raycast, or Shortcuts (`examples/skhd.example`).
- A signed, prebuilt app on GitHub Releases so a checkout and compile are unnecessary.
- A Homebrew formula. Homebrew is not required to build or run BlaBla.
- A WhisperKit backend behind `TranscriptionService`, if a Swift transcription path becomes worth maintaining.
- Voice activity trimming before inference.
- Flash attention and other speed/memory switches once they are validated on Apple Silicon.
