# BlaBla

Speak. You do not have to be precise.

BlaBla is local dictation for the Mac. Click, talk the way you actually talk, click again. The words land on the clipboard. Nothing is typed into the app in front of you, and nothing is sent to a cloud speech service.

The name is the sound of talking. *Bla bla* is what you say when someone is speaking freely, loosely, even a little carelessly. That is the product. Dictate first. A small vocabulary file fixes the names that matter.

## Why

Cloud dictation is slow, and it gets awkward as soon as you talk for more than a minute. BlaBla keeps the model on the machine. You can ramble. When you stop, one finished transcript is copied to the clipboard, so a clipboard history app can hold it. The app you were using is left alone.

## Install

You need an Apple Silicon Mac on macOS 13 or newer, plus:

- Xcode Command Line Tools (`xcode-select --install`)
- Python 3.11 or newer
- ffmpeg
- git and curl

Homebrew is optional. Internet is required once, to fetch the whisper.cpp source, CMake if you do not already have it, and the model weights.

```bash
git clone https://github.com/Baraujo25/blabla.git
cd blabla
./scripts/setup.sh
./scripts/blabla doctor
./scripts/blabla warmup
```

`setup.sh` builds the microphone helper, builds whisper.cpp v1.9.6 with Metal, and downloads Whisper Large V3 Turbo (about 1.5 GB) into `~/Library/Application Support/BlaBla/models`. The download happens once. `warmup` loads the weights so the first real dictation does not pay that cost.

The first time you open the helper, macOS asks for the microphone:

```bash
open helper/BlaBla.app
```

Allow Microphone for **BlaBla**.

## Quick start

Point a menu-bar host such as [simple-bar](https://github.com/Jean-Tinland/simple-bar) at this checkout. Use the absolute paths from your own clone.

| Field | Value |
|---|---|
| Refresh | `1000` |
| Command | `/path/to/blabla/scripts/status.sh` |
| On click | `/path/to/blabla/scripts/toggle.sh` |
| On right click | `/path/to/blabla/scripts/reset.sh` |

Click. Speak. Click again. The text is on the clipboard.

| Label | Meaning |
|---|---|
| `BlaBla` | Idle |
| `REC 0:42` | Recording |
| `…` | Transcribing |
| `✓ 1234` | Done. That many characters were copied |
| `!` | Error. Run `./scripts/blabla doctor` and open the log it prints |

There is no length limit in BlaBla, and the recording is not split into one-minute pieces. One notification appears when the text is copied. A click during transcription does nothing.

BlaBla does not install a global hotkey. Point skhd, Raycast, or Shortcuts at:

```bash
/path/to/blabla/scripts/blabla toggle
```

`examples/skhd.example` is one binding.

## Configuration

The first launch creates two files under `~/.blabla` (or `BLABLA_HOME`):

- `config.toml`, from `config.example.toml`
- `vocabulary.json`, from `vocabulary.example.json`

Edit those copies. Ordinary settings do not require a source change.

```toml
model = "large-v3-turbo"
language = "en"
audio_device = "0"
log_transcripts = false
```

| Setting | Purpose |
|---|---|
| `model` | `large-v3-turbo`, another ggml name such as `large-v3-turbo-q5_0`, or a path to a `.bin` file |
| `model_dir` | Where weights are stored. Empty means `~/Library/Application Support/BlaBla/models` |
| `language` | `en`, `es`, `en-US` (treated as `en`), or `auto` |
| `audio_device` | ffmpeg input index from `./scripts/blabla devices` |
| `whisper_mode` | `server` (default, model stays loaded) or `cli` |
| `notify_preview` | When false, the notification does not contain the transcript |
| `log_transcripts` | Off by default. Logs then store durations and character counts only |

`large-v3-turbo-q5_0` is the smaller model if memory is tight. Change `model`, run `./scripts/blabla download-model`, then `./scripts/blabla server-stop`.

List microphones with `./scripts/blabla devices`. With a laptop lid closed, the built-in mic is off. Set `audio_device` to an external one.

## Vocabulary

`vocabulary.json` maps a heard phrase to the spelling you want:

```json
{
  "git hub": "GitHub",
  "jay son": "JSON",
  "eye phone": "iPhone",
  "mac os": "macOS"
}
```

Matching ignores case. A longer phrase wins over a shorter one. The replacement is a single pass in code. No language model is involved. The preferred spellings are also sent to Whisper as a hint. The JSON replacements are what the copied text actually uses.

## What is not in this repository

Model weights, recordings, logs, and your `config.toml` stay on the machine. They are listed in `.gitignore`. Download weights with `./scripts/blabla download-model`. Do not commit them.

The unit tests use made-up phrases. They do not read a microphone or a recording from anyone's computer. A real microphone check is `./scripts/blabla test-mic`, and you run that yourself.

## Commands

```bash
./scripts/blabla doctor
./scripts/blabla devices
./scripts/blabla test-mic
./scripts/blabla download-model
./scripts/blabla warmup
./scripts/blabla server-stop
./scripts/blabla transcribe recording.flac
./scripts/blabla toggle
./scripts/blabla reset
```

`transcribe` prints the text. It does not copy it. The widget path does.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Widget shows `!` | `./scripts/blabla doctor`, then open the log path it prints |
| Microphone prompt never appears | Open `helper/BlaBla.app` once. A menu-bar host cannot request the mic itself |
| Model not found | `./scripts/blabla download-model` |
| First dictation is slow, later ones are fast | Expected. Run `warmup`, or leave the server running |
| Recording is silent | Wrong `audio_device`, or the lid is closed. Run `devices` and `test-mic` |
| Several copies of the same text | Update to this version. A second click while BlaBla is already working is ignored |
| Need the memory back | `./scripts/blabla server-stop` |

Design notes are in `docs/ARCHITECTURE.md`. Later work is in `ROADMAP.md`.

## Model license

Weights are OpenAI Whisper weights in ggml form, published for whisper.cpp at [ggerganov/whisper.cpp on Hugging Face](https://huggingface.co/ggerganov/whisper.cpp). Whisper and whisper.cpp are MIT-licensed. This repository does not contain the weights.

## Development

```bash
python3 -m pip install pytest
python3 -m pytest
bash scripts/build-helper.sh
```
