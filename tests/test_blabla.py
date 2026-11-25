import json
from pathlib import Path

import pytest

from blabla.audio import silence_message
from blabla.backends.whisper_cpp import encode_multipart, parse_inference_body
from blabla.config import ensure_user_files, load_config
from blabla.control import cancel_transcription, write_transcribe_pid
from blabla.models import default_model_url, ggml_filename
from blabla.paths import config_path, transcribe_pid_path
from blabla.state import AppState, widget_label
from blabla.timings import Timings
from blabla.transcription import normalize_transcript, whisper_language
from blabla.vocabulary import apply_vocabulary, build_prompt, load_vocabulary

ROOT = Path(__file__).resolve().parents[1]
HOME_PREFIX = "/" + "Users/"


def test_widget_labels():
    assert widget_label(AppState()) == "BlaBla"
    assert widget_label(AppState(status="recording", started_at=10**10)).startswith("REC")
    assert widget_label(AppState(status="processing", message="Transcribing")) == "…"
    assert widget_label(AppState(status="done", chars=12)) == "✓ 12"
    assert widget_label(AppState(status="error")) == "!"


def test_example_config_is_portable():
    text = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    assert "backend = \"whisper\"" in text
    assert HOME_PREFIX not in text
    assert "gcloud" not in text.lower()
    loaded = load_config()
    assert loaded.backend == "whisper"
    assert loaded.model == "large-v3-turbo"
    assert loaded.server_host == "127.0.0.1"


def test_legacy_cloud_settings_are_not_the_active_backend(isolated_home):
    config_path().write_text(
        'backend = "speech"\nspeech_language = "en-US"\nchunk_seconds = 55\n'
        'gcloud_bin = "/tmp/gcloud"\nkeep_recordings = false\n',
        encoding="utf-8",
    )
    config = load_config()
    assert config.backend == "whisper"
    assert config.removed_backend
    assert whisper_language(config.language) == "en"
    assert "gcloud_bin" in config.ignored_legacy
    assert "chunk_seconds" in config.ignored_legacy
    assert config.keep_recordings is False


def test_remote_server_host_is_rejected():
    config_path().write_text('server_host = "0.0.0.0"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="server_host"):
        load_config()


def test_ensure_user_files_writes_samples(isolated_home):
    config = ensure_user_files()
    assert (isolated_home / "config.toml").is_file()
    vocab = isolated_home / "vocabulary.json"
    assert vocab.is_file()
    text = vocab.read_text(encoding="utf-8")
    assert HOME_PREFIX not in text
    assert "GitHub" in text
    assert config.language == "en"


def test_vocabulary_replacements_are_deterministic():
    sample = json.loads((ROOT / "vocabulary.example.json").read_text(encoding="utf-8"))
    text = "I use git hub, jay son, eye phone and mac os."
    assert apply_vocabulary(text, sample) == "I use GitHub, JSON, iPhone and macOS."
    assert apply_vocabulary("GIT HUB", sample) == "GitHub"
    assert apply_vocabulary("github", sample) == "github"
    longer = {"hub": "X", "git hub": "GitHub"}
    assert apply_vocabulary("git hub and hub", longer) == "GitHub and X"


def test_vocabulary_file_shapes(tmp_path):
    flat = tmp_path / "flat.json"
    flat.write_text('{"mac os": "macOS"}\n', encoding="utf-8")
    loaded = load_vocabulary(flat)
    prompt = build_prompt(loaded, "", 800)
    assert "macOS" in prompt
    structured = tmp_path / "structured.json"
    structured.write_text(
        '{"replacements": {"git hub": "GitHub"}, "prompt": "GitHub"}\n',
        encoding="utf-8",
    )
    loaded = load_vocabulary(structured)
    assert loaded.prompt == "GitHub"
    assert apply_vocabulary("git hub", loaded.replacements) == "GitHub"


def test_prompt_is_truncated():
    from blabla.vocabulary import Vocabulary

    vocab = Vocabulary(replacements={"a": "AlphaBeta"})
    assert len(build_prompt(vocab, "hello", 8)) <= 8


def test_language_and_transcript_normalization():
    assert whisper_language("en-US") == "en"
    assert whisper_language("auto") == "auto"
    assert normalize_transcript(" hello \n world ") == "hello world"
    with pytest.raises(ValueError):
        whisper_language("123")


def test_model_url_uses_the_official_ggml_name():
    assert ggml_filename("large-v3-turbo") == "ggml-large-v3-turbo.bin"
    assert default_model_url("large-v3-turbo").endswith("/ggml-large-v3-turbo.bin")


def test_inference_body_is_one_audio_file():
    boundary, body = encode_multipart(
        {"prompt": "GitHub", "language": "en"},
        b"RIFFfake",
    )
    assert f"--{boundary}--".encode() in body
    assert body.count(b'name="file"') == 1
    assert b'filename="audio.wav"' in body
    assert b"GitHub" in body
    assert parse_inference_body(b'{"text": " hello "}', "application/json") == "hello"


def test_silence_message_threshold():
    assert silence_message(-10, "0") is None
    assert "silent" in silence_message(-60, "0")


def test_paste_settings_are_ignored(isolated_home):
    config_path().write_text(
        "insert_text = true\nrestore_clipboard = true\nclipboard_restore_delay_sec = 0.1\n",
        encoding="utf-8",
    )
    config = load_config()
    assert "insert_text" in config.ignored_legacy
    assert "restore_clipboard" in config.ignored_legacy
    assert not hasattr(config, "insert_text")


def test_delivery_is_clipboard_only():
    swift = (ROOT / "helper" / "RequestMicAndRun.swift").read_text(encoding="utf-8")
    cli = (ROOT / "blabla" / "cli.py").read_text(encoding="utf-8")
    example = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    assert "CGEvent" not in swift
    assert "NSPasteboard" not in swift
    assert "keystroke" not in swift
    assert "insert_transcription" not in cli
    assert "copy_to_clipboard" in cli
    assert "Recording started" not in cli
    assert "insert_text" not in example
    assert not (ROOT / "blabla" / "insert.py").exists()


def test_timings_log_has_the_required_fields():
    line = Timings(
        recording_sec=1,
        model_init_sec=2,
        transcription_sec=3,
        postprocess_sec=0.1,
        stop_to_insert_sec=4,
    ).log_line()
    for name in (
        "recording_sec",
        "model_init_sec",
        "transcription_sec",
        "postprocess_sec",
        "stop_to_insert_sec",
    ):
        assert name in line


def test_cancel_transcription_stops_the_recorded_pid():
    import subprocess

    proc = subprocess.Popen(["sleep", "30"])
    transcribe_pid_path().write_text(str(proc.pid), encoding="utf-8")
    assert cancel_transcription()
    proc.wait(timeout=3)
    assert not transcribe_pid_path().exists()


def test_a_second_action_does_not_run_alongside_the_first():
    from blabla.control import exclusive_action

    with exclusive_action() as first:
        assert first is True
        with exclusive_action() as second:
            assert second is False
    with exclusive_action() as third:
        assert third is True
    assert cancel_transcription() is False
    write_transcribe_pid()
    assert cancel_transcription() is False


def test_repository_has_no_personal_paths_or_cloud_client():
    banned_dirs = {".venv", ".tools", ".git", "__pycache__", "build"}
    suffixes = {".py", ".sh", ".swift", ".toml", ".json", ".yml", ".yaml", ".plist", ".md"}
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if banned_dirs.intersection(path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if HOME_PREFIX in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
    for path in (ROOT / "blabla").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "google.cloud" not in source
        assert "resolve_gcloud" not in source
        assert "ml speech" not in source
