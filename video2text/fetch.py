"""抓取层：元数据、字幕、音频。全部通过 yt-dlp，天然支持 1000+ 站点。"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys

from .models import Segment, VideoMeta

DEFAULT_SUB_LANGS = "zh-Hans,zh-Hant,zh-CN,zh,en"


def run_ytdlp(args, timeout: int = 900):
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def get_metadata(url: str, timeout: int = 180) -> VideoMeta:
    r = run_ytdlp(["--dump-json", url], timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"无法获取元数据：{(r.stderr or '').strip()[-400:]}")
    info = json.loads(r.stdout.strip().splitlines()[0])
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


def download_subtitles(url, workdir, langs: str = DEFAULT_SUB_LANGS, timeout: int = 600):
    """尝试下载字幕（含自动字幕）。命中返回 vtt 路径，否则 None。"""
    run_ytdlp(
        [
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            langs,
            "--sub-format",
            "vtt",
            "-o",
            os.path.join(workdir, "sub.%(ext)s"),
            url,
        ],
        timeout=timeout,
    )
    files = sorted(glob.glob(os.path.join(workdir, "*.vtt")))
    if not files:
        return None
    order = [l.strip().lower() for l in langs.split(",") if l.strip()]

    def rank(path):
        name = os.path.basename(path).lower()
        for i, lang in enumerate(order):
            if lang in name:
                return i
        return len(order)

    files.sort(key=lambda p: (rank(p), -os.path.getsize(p)))
    return files[0]


def download_audio(url, workdir, timeout: int = 1800):
    r = run_ytdlp(
        ["-f", "bestaudio", "-o", os.path.join(workdir, "audio.%(ext)s"), url],
        timeout=timeout,
    )
    cands = [
        c
        for c in glob.glob(os.path.join(workdir, "audio.*"))
        if not c.endswith((".part", ".ytdl"))
    ]
    if not cands:
        raise RuntimeError(f"音频下载失败：{(r.stderr or '').strip()[-300:]}")
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
