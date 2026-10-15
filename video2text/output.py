"""输出层：md / txt / srt / json。"""
from __future__ import annotations

import datetime
import json
import os
import re


def safe_filename(title: str, limit: int = 60) -> str:
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", (title or "untitled").strip())
    return (name[:limit].strip() or "untitled")


def _md_time(t: float) -> str:
    return f"[{int(t // 60):02d}:{int(t % 60):02d}]"


def _srt_time(t: float) -> str:
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def write_markdown(meta, segments, path, frontmatter=True, source="", model=None,
                   summary_placeholder=False):
    def q(v):
        return json.dumps(str(v), ensure_ascii=False)

    lines = []
    if frontmatter:
        lines += [
            "---",
            f"title: {q(meta.title)}",
            f"source: {q(meta.webpage_url)}",
            f"author: {q(meta.uploader)}",
            f"duration: {q(meta.duration_str)}",
            f"date: {datetime.date.today().isoformat()}",
            "tags: [transcript]",
            f"transcript_source: {q(source)}",
        ]
        if model:
            lines.append(f"asr_model: {q(model)}")
        lines += ["---", ""]

    lines += [f"# {meta.title}", ""]
    lines.append(f"> 来源：[链接]({meta.webpage_url}) · 作者：{meta.uploader} · 时长：{meta.duration_str}")
    if source.startswith("whisper"):
        lines.append("> 说明：该视频无可用字幕，本文由 Whisper 本地语音识别生成，**可能存在识别误差，建议通读校对**。")
    lines.append("")
    if summary_placeholder:
        lines += ["## 内容概要", "", "（待补充）", ""]
    lines += ["## 逐字稿", ""]
    for s in segments:
        lines.append(f"{_md_time(s.start)} {s.text}")
    lines.append("")
    _write(path, "\n".join(lines))


def write_text(segments, path, with_timestamps=True):
    lines = []
    for s in segments:
        lines.append(f"{_md_time(s.start)} {s.text}" if with_timestamps else s.text)
    _write(path, "\n".join(lines) + "\n")


def write_srt(segments, path):
    blocks = []
    for i, s in enumerate(segments, 1):
        blocks.append(f"{i}\n{_srt_time(s.start)} --> {_srt_time(s.end)}\n{s.text}\n")
    _write(path, "\n".join(blocks))


def write_json(meta, segments, path, source="", model=None):
    payload = {
        "title": meta.title,
        "source": meta.webpage_url,
        "author": meta.uploader,
        "duration": meta.duration,
        "site": meta.extractor,
        "transcript_source": source,
        "asr_model": model,
        "segments": [
            {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text}
            for s in segments
        ],
    }
    _write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
