"""抓取层：元数据、字幕、音频。

使用 yt-dlp 的 Python API 而**不是**子进程调用——打包成独立应用后没有
Python 解释器可供 `python -m yt_dlp` 调用，子进程方式会失效。
"""
from __future__ import annotations

import glob
import os
import re
import shutil

import yt_dlp

from .models import Segment, VideoMeta

DEFAULT_SUB_LANGS = "zh-Hans,zh-Hant,zh-CN,zh,en"

_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "nocheckcertificate": True,
}


def get_metadata(url: str) -> VideoMeta:
    with yt_dlp.YoutubeDL({**_BASE_OPTS, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("无法获取视频元数据")

    if "entries" in info:  # 合集 / 播放列表：取第一条
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise RuntimeError("链接指向的合集为空")
        info = entries[0]

    return VideoMeta(
        id=str(info.get("id") or ""),
        title=info.get("title") or "untitled",
        uploader=info.get("uploader") or info.get("channel") or "unknown",
        duration=int(info.get("duration") or 0),
        webpage_url=info.get("webpage_url") or url,
        extractor=info.get("extractor_key") or info.get("extractor") or "unknown",
    )


def ensure_ffmpeg():
    """优先使用 imageio-ffmpeg 自带的 ffmpeg，免手动安装；否则回退系统 ffmpeg。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        exe = get_ffmpeg_exe()
        d = os.path.dirname(exe)
        if d and d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        return exe
    except Exception:
        return shutil.which("ffmpeg")


def _lang_list(langs: str):
    return [l.strip() for l in langs.split(",") if l.strip()]


def download_subtitles(url: str, workdir: str, langs: str = DEFAULT_SUB_LANGS):
    """尝试下载字幕（含自动字幕）。命中返回 vtt 路径，否则 None。"""
    opts = {
        **_BASE_OPTS,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": _lang_list(langs),
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(workdir, "sub.%(ext)s"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        return None

    files = sorted(glob.glob(os.path.join(workdir, "*.vtt")))
    if not files:
        return None
    order = [l.lower() for l in _lang_list(langs)]

    def rank(path):
        name = os.path.basename(path).lower()
        for i, lang in enumerate(order):
            if lang in name:
                return i
        return len(order)

    files.sort(key=lambda p: (rank(p), -os.path.getsize(p)))
    return files[0]


def download_audio(url: str, workdir: str):
    opts = {
        **_BASE_OPTS,
        "format": "bestaudio",
        "outtmpl": os.path.join(workdir, "audio.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    cands = [
        c
        for c in glob.glob(os.path.join(workdir, "audio.*"))
        if not c.endswith((".part", ".ytdl"))
    ]
    if not cands:
        raise RuntimeError("音频下载失败")
    return max(cands, key=os.path.getsize)


TAG_RE = re.compile(r"<[^>]+>")


def _parse_ts(token: str) -> float:
    token = token.strip().replace(",", ".")
    parts = token.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    except ValueError:
        return 0.0
    return 0.0


def parse_vtt(path: str) -> list:
    """把 VTT 解析为 Segment 列表，并对滚动式自动字幕做去重。"""
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()

    cues: list = []
    start = None
    end = None
    buf: list = []

    def flush():
        nonlocal start, end, buf
        if start is None:
            return
        text = TAG_RE.sub("", " ".join(x for x in buf if x)).strip()
        if text:
            cues.append(Segment(start, end if end is not None else start, text))
        start = None
        end = None
        buf = []

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            flush()
            continue
        if s.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        if "-->" in s:
            flush()
            left, _, right = s.partition("-->")
            start = _parse_ts(left)
            parts = right.split()
            end = _parse_ts(parts[0]) if parts else start
            continue
        if start is None:
            continue
        buf.append(s)
    flush()
    return _dedupe(cues)


def _dedupe(cues: list) -> list:
    """自动字幕常以滚动方式重复输出（后一句包含前一句），这里合并掉。"""
    out: list = []
    for c in cues:
        if not c.text:
            continue
        if out:
            prev = out[-1]
            if c.text == prev.text:
                continue
            if c.text.startswith(prev.text) and len(c.text) > len(prev.text):
                out[-1] = Segment(prev.start, c.end, c.text)
                continue
        out.append(c)
    return out
