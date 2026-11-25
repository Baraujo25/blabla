from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Timings:
    recording_sec: float = 0.0
    model_init_sec: float = 0.0
    transcription_sec: float = 0.0
    postprocess_sec: float = 0.0
    stop_to_insert_sec: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {key: round(value, 3) for key, value in asdict(self).items()}

    def log_line(self) -> str:
        values = self.as_dict()
        parts = [f"{key}={values[key]:.3f}" for key in values]
        return "timings " + " ".join(parts)
