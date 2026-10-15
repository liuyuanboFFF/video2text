"""命令行入口。"""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile

from . import __version__, fetch, output, transcribe

MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]
EXT = {"md": "md", "txt": "txt", "srt": "srt", "json": "json"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="video2text",
        description="把一个视频链接变成逐字稿：优先抓官方字幕，没有字幕再用本地 Whisper 转写。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  video2text "https://www.bilibili.com/video/BV1xx411c7mD"
  video2text "链接1" "链接2" -o ./notes
  video2text "链接" -f srt                 出字幕文件
  video2text "链接" --force-asr            忽略字幕，强制语音识别
  video2text "链接" -m small               更快、更省内存
  video2text "链接" -l auto --no-hf-mirror 自动检测语言 + 海外网络
""",
    )
    p.add_argument("urls", nargs="+", help="一个或多个视频链接（yt-dlp 支持的站点均可）")
    p.add_argument("-o", "--output", default="./transcripts", help="输出目录（默认 ./transcripts）")
    p.add_argument("-f", "--format", default="md", choices=list(EXT), help="输出格式（默认 md）")
    p.add_argument("-m", "--model", default="medium", choices=MODEL_CHOICES,
                   help="Whisper 模型大小（默认 medium）")
    p.add_argument("-l", "--language", default="zh", help="转写语言代码，auto 为自动检测（默认 zh）")
    p.add_argument("--threads", type=int, default=5, help="CPU 转写线程数（默认 5）")
    p.add_argument("--sub-langs", default=fetch.DEFAULT_SUB_LANGS,
                   help="字幕语言优先级，逗号分隔（默认 zh-Hans,zh-Hant,zh-CN,zh,en）")
    p.add_argument("--force-asr", action="store_true", help="忽略已有字幕，一律走语音识别")
    p.add_argument("--no-frontmatter", action="store_true", help="md 输出不加 YAML frontmatter")
    p.add_argument("--summary-placeholder", action="store_true",
                   help="md 输出插入「内容概要（待补充）」占位段")
    p.add_argument("--keep-temp", action="store_true", help="保留临时文件（调试用）")
    p.add_argument("--no-hf-mirror", action="store_true", help="不使用 hf-mirror.com（海外网络可加）")
    p.add_argument("--tolerance", type=int, default=60,
                   help="转写时长与元数据不符的容差秒数，超出即终止（默认 60）")
    p.add_argument("-q", "--quiet", action="store_true", help="减少输出")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _dispatch(meta, segments, path, args, source):
    fmt = args.format
    if fmt == "md":
        output.write_markdown(
            meta, segments, path,
            frontmatter=not args.no_frontmatter,
            source=source,
            model=args.model if source.startswith("whisper") else None,
            summary_placeholder=args.summary_placeholder,
        )
    elif fmt == "txt":
        output.write_text(segments, path)
    elif fmt == "srt":
        output.write_srt(segments, path)
    else:
        output.write_json(meta, segments, path, source=source,
                          model=args.model if source.startswith("whisper") else None)


def process_one(url: str, args, get_model, log) -> str:
    meta = fetch.get_metadata(url)
    log("=" * 60)
    log(f"标题: {meta.title}")
    log(f"作者: {meta.uploader} · 时长: {meta.duration_str} · 站点: {meta.extractor}")

    work = tempfile.mkdtemp(prefix="v2t_")
    segments = None
    source = ""
    try:
        if not args.force_asr:
            vtt = fetch.download_subtitles(url, work, args.sub_langs)
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
            model = get_model()
            segments, info = transcribe.transcribe(model, audio, args.language)
            got = float(getattr(info, "duration", 0) or 0)
            if meta.duration and abs(got - meta.duration) > args.tolerance:
                raise RuntimeError(
                    f"时长校验失败：转写 {got:.0f}s 与元数据 {meta.duration}s 相差超过 "
                    f"{args.tolerance}s，疑似抓错资源，已终止以免写出错误内容"
                )
            source = f"whisper:{args.model}"
            log(f"转写完成：{len(segments)} 段")

        name = output.safe_filename(meta.title) + "." + EXT[args.format]
        path = os.path.join(args.output, name)
        _dispatch(meta, segments, path, args, source)
        log(f"已保存: {path}")
        return path
    finally:
        if args.keep_temp:
            log(f"临时目录保留: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    os.makedirs(args.output, exist_ok=True)

    def log(msg):
        if not args.quiet:
            print(msg, flush=True)

    log(f"输出目录: {os.path.abspath(args.output)}")

    holder = {}

    def get_model():
        if "model" not in holder:
            ff = fetch.ensure_ffmpeg()
            log(f"ffmpeg: {ff}")
            log(f"加载 Whisper 模型: {args.model} (CPU int8, threads={args.threads}) ...")
            holder["model"] = transcribe.load_model(
                args.model, args.threads, hf_mirror=not args.no_hf_mirror
            )
        return holder["model"]

    ok, fail = [], []
    for url in args.urls:
        try:
            ok.append(process_one(url, args, get_model, log))
        except Exception as e:
            fail.append((url, repr(e)))
            print(f"!!! 失败: {url} -> {e!r}", flush=True)

    log("=" * 60)
    log(f"完成: {len(ok)}/{len(args.urls)} 成功")
    for p in ok:
        log(f" - {p}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
