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


# Whisper 对中文默认倾向输出繁体，显式用简体提示词把它掰回来。
SIMPLIFIED_HINT = "以下是普通话内容，请使用简体中文输出，不要使用繁体字。"

_T2S = None


def _converter():
    """惰性加载 OpenCC 的 tw2sp（繁体字形 + 台湾用词 → 简体 + 大陆用词）。

    纯 Python 实现，打包体积仅约 1.2MB；缺失时静默降级，不影响主流程。
    """
    global _T2S
    if _T2S is None:
        try:
            import opencc

            _T2S = opencc.OpenCC("tw2sp")
        except Exception:
            _T2S = False
    return _T2S


def to_simplified(text: str) -> str:
    conv = _converter()
    if not conv or not text:
        return text
    try:
        return conv.convert(text)
    except Exception:
        return text


def simplified_available() -> bool:
    """是否装了 OpenCC（决定能否做确定性繁→简兜底）。"""
    return bool(_converter())


# Whisper 中文的已知误识：把「么」写成「幺」。只在固定搭配里替换，避免误伤
# 真的表示「排行最小/幺鸡」这类用法的「幺」。
_ASR_FIXES = (
    ("什幺", "什么"),
    ("那幺", "那么"),
    ("怎幺", "怎么"),
    ("这幺", "这么"),
    ("多幺", "多么"),
    ("要幺", "要么"),
    ("为幺", "为么"),
    ("幺样", "么样"),
)


def fix_common_asr_errors(text: str) -> str:
    """修正 Whisper 中文里反复出现的固定误识。"""
    for bad, good in _ASR_FIXES:
        if bad in text:
            text = text.replace(bad, good)
    return text


def build_initial_prompt(prompt: str | None, simplify: bool) -> str | None:
    """拼装 initial_prompt：简体指令 + 用户自定义术语提示。

    术语提示能显著改善人名、产品名、专业词的识别准确率——把这些词
    写进提示词，等于提前告诉模型「这些词长什么样」。
    """
    parts = []
    if simplify:
        parts.append(SIMPLIFIED_HINT)
    if prompt:
        parts.append(prompt.strip())
    return " ".join(p for p in parts if p) or None


def transcribe(
    model,
    audio_path: str,
    language: str = "zh",
    beam_size: int = 5,
    vad: bool = True,
    prompt: str | None = None,
    simplify: bool = True,
):
    lang = None if language in ("auto", "", None) else language
    is_zh = lang == "zh"
    initial = build_initial_prompt(prompt, simplify) if is_zh else (prompt or None)
    segs, info = model.transcribe(
        audio_path,
        language=lang,
        beam_size=beam_size,
        vad_filter=vad,
        condition_on_previous_text=True,
        initial_prompt=initial,
    )
    out = []
    for s in segs:
        text = s.text.strip()
        if not text:
            continue
        # initial_prompt 只能降低概率，不能保证；这里做确定性兜底。
        if is_zh:
            if simplify:
                text = to_simplified(text)
            text = fix_common_asr_errors(text)
        out.append(Segment(float(s.start), float(s.end), text))
    return out, info
