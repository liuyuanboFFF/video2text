"""命令行入口（图形界面的对等物见 gui.py，两者共用 pipeline）。"""
from __future__ import annotations

import argparse
import os

from . import __version__, fetch, pipeline


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
  video2text "链接" --prompt "Chatbox、SKILL.md"   用术语提示纠正专有名词
  video2text "链接" --keep-traditional     保留繁体输出
""",
    )
    p.add_argument("urls", nargs="+", help="一个或多个视频链接（yt-dlp 支持的站点均可）")
    p.add_argument("-o", "--output", default="./transcripts", help="输出目录（默认 ./transcripts）")
    p.add_argument("-f", "--format", default="md", choices=list(pipeline.EXT),
                   help="输出格式（默认 md）")
    p.add_argument("-m", "--model", default="medium",
                   choices=["tiny", "base", "small", "medium", "large-v3"],
                   help="Whisper 模型大小（默认 medium）")
    p.add_argument("-l", "--language", default="zh", help="转写语言代码，auto 为自动检测（默认 zh）")
    p.add_argument("--prompt", default="",
                   help="术语提示：把容易听错的人名/产品名/专业词写进来，能显著提升识别准确率，"
                        "例如 --prompt \"AI Agent、Chatbox、SKILL.md\"")
    p.add_argument("--keep-traditional", action="store_true",
                   help="保留繁体中文（默认会把中文输出统一转成简体）")
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


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    options = pipeline.Options(
        output=args.output,
        format=args.format,
        model=args.model,
        language=args.language,
        threads=args.threads,
        sub_langs=args.sub_langs,
        force_asr=args.force_asr,
        frontmatter=not args.no_frontmatter,
        summary_placeholder=args.summary_placeholder,
        keep_temp=args.keep_temp,
        hf_mirror=not args.no_hf_mirror,
        tolerance=args.tolerance,
        prompt=args.prompt,
        simplify=not args.keep_traditional,
    )

    def log(msg):
        if not args.quiet:
            print(msg, flush=True)

    log(f"输出目录: {os.path.abspath(options.output)}")
    ok, fail = pipeline.run(args.urls, options, log=log)
    log("=" * 60)
    log(f"完成: {len(ok)}/{len(args.urls)} 成功")
    for p in ok:
        log(f" - {p}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
