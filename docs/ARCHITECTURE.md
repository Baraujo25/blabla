# Architecture

## What the previous version did

simple-bar calls three scripts:

| Widget action | Script | Effect |
|---|---|---|
| Refresh | `scripts/status.sh` | Prints `BlaBla`, `REC …`, `…`, `✓ N`, or `!` |
| Click | `scripts/toggle.sh` | Opens `BlaBla.app` |
| Right click | `scripts/reset.sh` | Stops the recorder and clears state |

`BlaBla` is a background app whose only job is the microphone permission prompt. macOS will not show that prompt for Übersicht, which is the process that hosts simple-bar. The helper then runs `python -m blabla toggle`.

Recording is ffmpeg using the AVFoundation device in the config. The pid lives in the BlaBla data directory. A second click stops ffmpeg and, previously, sent the FLAC to `gcloud ml speech recognize`. Files longer than about 55 seconds were split because that API call rejects longer audio. The text was copied to the clipboard with `pbcopy`. Nothing was pasted, and the previous clipboard was not restored.

## What this version changes

Only the transcription step and the delivery of the finished text. Recording, the widget labels, and the helper's microphone prompt stay.

```
simple-bar click
  -> BlaBla (microphone permission)
    -> python -m blabla toggle
      -> ffmpeg records current.flac
simple-bar click again
  -> python -m blabla stop
    -> whisper-server (model already in memory, or started once)
    -> vocabulary replacements
    -> copy the finished text to the clipboard
```

The whole file is one request. whisper.cpp splits audio into its own windows internally. BlaBla does not cut the recording into minute-long pieces.

## Why whisper.cpp

The process that records and talks to the widget is Python. The Swift code does not see the audio. WhisperKit would be a second application and a second place to keep a model resident.

whisper.cpp matches the old shape: a local binary, with a small HTTP server in front of it so the weights are not loaded on every click. `whisper-cli` remains available (`whisper_mode = "cli"`) when a single request would outlive the server's socket timeout. The pinned server build raises that timeout from 600 seconds to 3600. That limit is inference time, not a cap on how long you may speak.

Large V3 Turbo is the default because it is the accurate fast Whisper model, not because it is the largest file. The full ggml weights are about 1.5 GB. `large-v3-turbo-q5_0` is the smaller switch if memory is tight. Weights are downloaded from the ggml Hugging Face repo and are not stored in git. The Whisper weights and whisper.cpp are both MIT-licensed; users download the weights themselves.

The server binds to `127.0.0.1`. A non-loopback host is a config error.

## Interfaces

The names in the request map onto the existing layout:

| Role | Module |
|---|---|
| AudioRecorder | `blabla/recorder.py` |
| TranscriptionService | `blabla/transcription.py`, `blabla/backends/whisper_cpp.py` |
| VocabularyService | `blabla/vocabulary.py` |
| Clipboard | `blabla/util.py` (`copy_to_clipboard`) |
| DictationController | `blabla/cli.py` (`start`, `stop`, `toggle`, `reset`) |

`get_transcription_service` is the seam for a future engine. Post-processing is `apply_vocabulary`. A later local language model can run after that function without changing the recorder.

## Clipboard

When transcription finishes, BlaBla runs `pbcopy` with the final text. It does not send keystrokes, it does not paste into the focused app, and it does not put the previous clipboard contents back. A clipboard manager therefore sees one new item, which stays available until you copy something else.

Nothing is copied while you are still speaking.

## Logs

Info logs include durations, audio level in dB, character counts, and the delivery path. They omit the transcript unless `log_transcripts` is true. The whisper server is started with realtime printing off, so its log records progress rather than the words.
