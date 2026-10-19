"""流程编排层：CLI 与 GUI 共用，任何界面都只是它的外壳。"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass

from . import fetch, output, transcribe

EXT = {"md": "md", "txt": "txt", "srt": "srt", "json": "json"}


@dataclass
class Options:
    output: str = "./transcripts"
    format: str = "md"
    model: str = "medium"
    language: str = "zh"
    threads: int = 5
    sub_langs: str = fetch.DEFAULT_SUB_LANGS
    force_asr: bool = False
    frontmatter: bool = True
    summary_placeholder: bool = False
    keep_temp: bool = False
    hf_mirror: bool = True
    tolerance: int = 60
    prompt: str = ""
    simplify: bool = True


class ModelHolder:
    """惰性加载并缓存 Whisper 模型：批量任务只加载一次。"""

    def __init__(self, options: Options, log):
        self._options = options
        self._log = log
        self._model = None

    def get(self):
        if self._model is None:
            ff = fetch.ensure_ffmpeg()
            self._log(f"ffmpeg: {ff}")
            self._log(
                f"加载 Whisper 模型: {self._options.model} "
                f"(CPU int8, threads={self._options.threads}) ..."
            )
            self._model = transcribe.load_model(
                self._options.model,
                self._options.threads,
                hf_mirror=self._options.hf_mirror,
            )
        return self._model


def _dispatch(meta, segments, path, options: Options, source: str):
    fmt = options.format
    asr_model = options.model if source.startswith("whisper") else None
    if fmt == "md":
        output.write_markdown(
            meta, segments, path,
            frontmatter=options.frontmatter,
            source=source,
            model=asr_model,
            summary_placeholder=options.summary_placeholder,
        )
    elif fmt == "txt":
        output.write_text(segments, path)
    elif fmt == "srt":
        output.write_srt(segments, path)
    elif fmt == "json":
        output.write_json(meta, segments, path, source=source, model=asr_model)
    else:
        raise ValueError(f"未知输出格式: {fmt}")


def process_one(url: str, options: Options, model_getter, log, cancel=None) -> str:
    if cancel and cancel():
        raise RuntimeError("已取消")

    meta = fetch.get_metadata(url)
    log("=" * 60)
    log(f"标题: {meta.title}")
    log(f"作者: {meta.uploader} · 时长: {meta.duration_str} · 站点: {meta.extractor}")

    work = tempfile.mkdtemp(prefix="v2t_")
    segments = None
    source = ""
    try:
        if not options.force_asr:
            vtt = fetch.download_subtitles(url, work, options.sub_langs)
            if vtt:
                segments = fetch.parse_vtt(vtt)
                if segments:
                    source = f"subtitle:{os.path.basename(vtt)}"
                    log(f"命中字幕: {os.path.basename(vtt)}（{len(segments)} 段，免转写）")
                else:
                    segments = None
            else:
                log("无可用字幕，转为语音识别")

        if segments is None:
            fetch.ensure_ffmpeg()
            log("下载音频 ...")
            audio = fetch.download_audio(url, work)
            log("转写中（CPU int8，长视频请耐心）...")
            model = model_getter()
            segments, info = transcribe.transcribe(
                model,
                audio,
                options.language,
                prompt=options.prompt or None,
                simplify=options.simplify,
            )
            got = float(getattr(info, "duration", 0) or 0)
            if meta.duration and abs(got - meta.duration) > options.tolerance:
                raise RuntimeError(
                    f"时长校验失败：转写 {got:.0f}s 与元数据 {meta.duration}s 相差超过 "
                    f"{options.tolerance}s，疑似抓错资源，已终止以免写出错误内容"
                )
            source = f"whisper:{options.model}"
            log(f"转写完成：{len(segments)} 段")
            if options.simplify and options.language == "zh":
                if transcribe.simplified_available():
                    log("已统一转为简体中文（OpenCC tw2sp）")
                else:
                    log("提示：未安装 opencc，仅靠提示词引导简体，可能仍有个别繁体字")

        name = output.safe_filename(meta.title) + "." + EXT[options.format]
        path = os.path.join(options.output, name)
        _dispatch(meta, segments, path, options, source)
        log(f"已保存: {path}")
        return path
    finally:
        if options.keep_temp:
            log(f"临时目录保留: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


def run(urls, options: Options, log=print, cancel=None):
    """批量处理多个链接。返回 (成功路径列表, 失败列表)。"""
    os.makedirs(options.output, exist_ok=True)
    holder = ModelHolder(options, log)
    ok, fail = [], []
    for i, url in enumerate(urls, 1):
        if len(urls) > 1:
            log(f"[{i}/{len(urls)}] {url}")
        try:
            ok.append(process_one(url, options, holder.get, log, cancel=cancel))
        except Exception as e:
            if cancel and cancel():
                log("已取消")
                break
            fail.append((url, repr(e)))
            log(f"!!! 失败: {url} -> {e!r}")
    return ok, fail
