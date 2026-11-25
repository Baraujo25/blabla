# Security

BlaBla records the microphone, transcribes the audio on this Mac, and copies the text to the clipboard. It does not send audio or transcripts to a cloud service.

## Data that stays on the machine

- Recordings, when `keep_recordings` is true, under the BlaBla data directory (`~/.blabla/recordings` unless `BLABLA_HOME` is set).
- `current.flac` for the recording in progress.
- `last_transcript.txt` for the latest text.
- Logs. Transcript text is written there only when `log_transcripts` is true.
- Model weights under Application Support, or the directory you set.

Delete those files when you no longer want them. `blabla server-stop` unloads the model from memory.

## Permissions

- Microphone: required. The prompt is for BlaBla.
- The transcription server listens on `127.0.0.1` only. The config rejects other hosts.

## Clipboard

The finished transcript replaces the clipboard contents. BlaBla does not paste into the focused application and does not restore what was there before.

## Reporting

Open a GitHub issue for a vulnerability, or contact the maintainers privately if the project has published a security contact. Do not include recordings or transcripts in the report unless the maintainer asks for a short sample.
