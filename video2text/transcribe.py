"""转写层：本地 faster-whisper，CPU int8，无需 API key。"""
from __future__ import annotations

import os

from .models import Segment


def patch_av():
    """兼容 av 版本差异：旧版 av.open 不接受 metadata_errors 参数。"""
    try:
        import av
    except Exception:
        return
    if getattr(av.open, "__v2t_patched__", False):
        return
    orig = av.open

    def patched(*a, **kw):
        kw.pop("metadata_errors", None)
        return orig(*a, **kw)

    patched.__v2t_patched__ = True
    av.open = patched


def load_model(size: str = "medium", threads: int = 5, hf_mirror: bool = True):
    if hf_mirror:
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    import faster_whisper

    patch_av()
    return faster_whisper.WhisperModel(
        size, device="cpu", compute_type="int8", cpu_threads=threads
    )


def transcribe(model, audio_path: str, language: str = "zh", beam_size: int = 5, vad: bool = True):
    lang = None if language in ("auto", "", None) else language
    segs, info = model.transcribe(
        audio_path,
        language=lang,
        beam_size=beam_size,
        vad_filter=vad,
        condition_on_previous_text=True,
    )
    out = [Segment(float(s.start), float(s.end), s.text.strip()) for s in segs if s.text.strip()]
    return out, info
