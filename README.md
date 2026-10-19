# video2text

丢一个视频链接进去，出一份带时间戳的逐字稿。

**优先抓官方字幕**（秒出、零误差）；没有字幕才回退到**本地 Whisper 语音识别**（离线运行、不需要任何 API key、音视频不出本机）。

```bash
video2text "https://www.bilibili.com/video/BV1xx411c7mD"
```

---

## 为什么是它

| | 说明 |
|---|---|
| **字幕优先** | 有官方字幕或自动字幕就直接解析，几秒钟出稿且零识别误差；没有才转写。 |
| **完全本地** | 转写跑在本机 CPU 上，不调用任何云端接口，不需要 API key，音视频文件用完即删。 |
| **站点通吃** | 底层是 yt-dlp，B 站、YouTube、播客等 1000+ 站点都能用，短链（如 `b23.tv/xxx`）也能直接丢进来。 |
| **四种输出** | Markdown（带 YAML frontmatter，Obsidian 友好）、TXT、SRT、JSON。 |
| **不出错稿** | 转写完成后会用视频元数据做**时长硬校验**，对不上就终止——避免出现"标题是 A、内容是 B"的错稿。 |
| **批量与并行安全** | 一次传多个链接，模型只加载一次；每个任务独立临时目录，多个进程同时跑也不会互相覆盖。 |

## 安装

需要 Python 3.9+。**ffmpeg 不用手动装**，`imageio-ffmpeg` 会自带一份。

```bash
git clone https://github.com/liuyuanboFFF/video2text.git
cd video2text

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

也可以装成命令：

```bash
pip install .
video2text "链接"
```

不安装也能直接用模块方式跑：

```bash
python -m video2text "链接"
```

> **国内网络**：默认从 `hf-mirror.com` 拉取 Whisper 模型，通常不必额外处理。
> 如果你在海外，加 `--no-hf-mirror` 走官方源。

## 桌面版（双击即用）

不想碰命令行的话，可以把它打包成带界面的独立应用：

**已有构建好的 macOS 版**，可直接从 [Releases](https://github.com/liuyuanboFFF/video2text/releases) 下载 `.zip`，解压后双击运行（未签名，首次打开需右键 →「打开」）。

也可以自己构建：

```bash
pip install pyinstaller

# macOS → dist/video2text.app
PYTHON=/path/to/python3 bash packaging/build_macos.sh

# Windows → dist\video2text\video2text.exe
packaging\build_windows.bat
```

打包后是一个窗口程序：粘贴链接、选模型与格式、点「开始」，日志实时滚动，完成后一键打开输出目录。**使用者无需安装 Python。**

三点限制，先知道再看值不值得：

- **模型首次仍需联网下载**（medium 约 1.4 GB），之后离线可用。
- **yt-dlp 无法自我更新**。视频站点解析规则经常变，嵌进 App 的 yt-dlp 是冻结版本，用久了可能失效，需要重新构建。
- **必须在目标平台分别构建**，macOS 只能出 `.app`、Windows 只能出 `.exe`；体积数百 MB（含 ffmpeg 与推理库）。

完整说明见 [`packaging/README.md`](packaging/README.md)。

## 用法

```bash
# 单个视频
video2text "https://www.bilibili.com/video/BV1xx411c7mD"

# 批量处理，输出到指定目录
video2text "链接1" "链接2" -o ./notes

# 直接出 SRT 字幕文件
video2text "链接" -f srt

# 有字幕也强制走语音识别（比如字幕质量太差）
video2text "链接" --force-asr

# 更快、更省内存（准确度略降）
video2text "链接" -m small

# 自动检测语言（非中文视频）
video2text "链接" -l auto
```

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `urls` | — | 一个或多个视频链接（必填） |
| `-o, --output` | `./transcripts` | 输出目录 |
| `-f, --format` | `md` | 输出格式：`md` / `txt` / `srt` / `json` |
| `-m, --model` | `medium` | Whisper 模型：`tiny` / `base` / `small` / `medium` / `large-v3` |
| `-l, --language` | `zh` | 转写语言代码，`auto` 为自动检测 |
| `--threads` | `5` | CPU 转写线程数 |
| `--sub-langs` | `zh-Hans,zh-Hant,zh-CN,zh,en` | 字幕语言优先级，逗号分隔 |
| `--force-asr` | 关 | 忽略字幕，一律语音识别 |
| `--no-frontmatter` | 关 | md 输出不加 YAML frontmatter |
| `--summary-placeholder` | 关 | md 输出插入「内容概要（待补充）」占位段 |
| `--keep-temp` | 关 | 保留临时文件，便于排查问题 |
| `--no-hf-mirror` | 关 | 不使用 hf-mirror.com |
| `--tolerance` | `60` | 时长校验容差（秒），超出即终止 |
| `-q, --quiet` | 关 | 减少输出 |

## 输出示例（Markdown）

```markdown
---
title: "一期很棒的访谈"
source: "https://www.bilibili.com/video/BV1xx411c7mD"
author: "某 UP 主"
duration: "38:12"
date: 2026-10-16
tags: [transcript]
transcript_source: "whisper:medium"
asr_model: "medium"
---

# 一期很棒的访谈

> 来源：[链接](https://...) · 作者：某 UP 主 · 时长：38:12
> 说明：该视频无可用字幕，本文由 Whisper 本地语音识别生成，**可能存在识别误差，建议通读校对**。

## 逐字稿

[00:00] 大家好，今天我们来聊聊……
[00:07] 这个问题其实要从三年前说起……
```

`transcript_source` 字段会标明这份稿子是 `subtitle:*`（来自字幕）还是 `whisper:*`（来自语音识别），方便你判断可信度。

## 工作流程

```
链接
  │
  ├─ 1) 取元数据（yt-dlp --dump-json）
  │
  ├─ 2) 探测字幕（--write-subs / --write-auto-subs）
  │      命中 → 解析 VTT，合并滚动重复 → 直接成稿   ← 最快、最准
  │
  ├─ 3) 未命中 → 下载 bestaudio
  │              → faster-whisper（CPU int8）转写
  │              → 时长硬校验（防抓错资源）
  │
  └─ 4) 写入输出文件 → 清理临时目录
```

## 模型怎么选

| 模型 | 相对速度 | 内存占用 | 准确度 | 适合 |
|---|---|---|---|---|
| `tiny` | 最快 | 最小 | 较低 | 只想快速看个大概 |
| `base` | 快 | 小 | 一般 | 短视频、试跑 |
| `small` | 较快 | 较小 | 尚可 | 机器一般 / 想省时间 |
| `medium` | 中等 | 中等 | **好** | **中文场景的推荐默认** |
| `large-v3` | 慢 | 大 | 最好 | 在意准确度、不着急 |

### 性能参考（Apple M4，CPU int8）

- `medium` 约 **2 倍实时**：38 分钟视频 ≈ 19 分钟转完；78 分钟 ≈ 39 分钟。
- 转写过程内存占用约 **2.5–3.5 GB**（模型本身缓存在磁盘约 1.4 GB，不常驻内存）。
- 首次运行会下载模型，之后复用缓存。

> 想更快：并行跑多个链接时把 `--threads` 调小（避免抢核），或换 `-m small`。
> 有 NVIDIA 显卡的话可以把 `device="cpu"` 改成 `cuda` 并换 `compute_type`，会快一个数量级。

## 常见问题

**模型下载失败 / HuggingFace 连不上**
默认已走 `hf-mirror.com`。仍然失败的话检查网络代理，或手动设置 `HF_ENDPOINT` 环境变量。

**报 `av.open() got an unexpected keyword argument 'metadata_errors'`**
这是 `av` 与 `faster-whisper` 的版本不匹配，本工具已内置兼容补丁，正常不会遇到。若出现请升级 `av`。

**报「时长校验失败」**
说明抓到的音频长度和视频元数据对不上，通常是链接指向分 P、合集或已被删改。用 `--keep-temp` 保留临时文件排查，或换用完整 BV 链接（而非短链）。

**中文人名 / 专名识别错了**
这是 ASR 的固有局限，尤其生僻人名。建议成稿后通读校对——`transcript_source: whisper:*` 的稿子默认就带这句提醒。

**想要更好的断句和标点**
换 `-m large-v3`，或对非中文内容用 `-l auto`，让模型自己判断语言。

## 支持的站点

凡是 [yt-dlp 支持的站点](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) 都能用，包括 B 站、YouTube、Vimeo、各类播客托管平台等。本项目不针对任何站点做特殊适配，全部交给 yt-dlp。

## 开发

```bash
pip install -e .
python -m video2text --help
```

跑测试（不联网、不下载模型，只验证解析与输出逻辑）：

```bash
python tests/test_core.py
# 或
python -m unittest discover -s tests -t .
```

代码结构：

```
video2text/
├── models.py       数据结构（Segment / VideoMeta）
├── fetch.py        元数据、字幕抓取与 VTT 解析、音频下载
├── transcribe.py   Whisper 加载与转写（含 av 兼容补丁）
├── output.py       md / txt / srt / json 输出
└── cli.py          命令行与流程编排
```

## 许可证

[MIT](LICENSE)。你可以自由使用、修改、商用，只需保留署名。
