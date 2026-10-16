# 打包成桌面应用

本目录用于把 video2text 打包成**双击即可运行**的独立应用（内含 Python 运行时，
使用者无需自己安装 Python）。

## 构建

```bash
pip install -r requirements.txt
pip install pyinstaller

# macOS → dist/video2text.app
PYTHON=/path/to/python3 bash packaging/build_macos.sh

# Windows → dist\video2text\video2text.exe
packaging\build_windows.bat
```

**必须在目标平台上分别构建**，无法交叉编译：macOS 上只能出 `.app`，
Windows 上只能出 `.exe`。

## 三个必须知道的限制

1. **模型仍需首次联网下载。** 打包体积里不含 Whisper 模型（medium 约 1.4 GB）。
   首次转写会下载并缓存到用户目录，之后离线可用。想彻底离线，可在构建前把模型
   放进包内并指定本地路径。
2. **yt-dlp 无法自我更新。** 视频站点的解析规则经常变动，而嵌进 App 的 yt-dlp 是
   冻结版本，用久了可能突然失效。届时需要重新构建，或等新版发布。
3. **体积较大**，含 ctranslate2 / onnxruntime / ffmpeg 等原生库，通常在数百 MB。

## 常见问题

**macOS 提示「无法验证开发者」**
未做代码签名时系统会拦截。右键点 App → 「打开」即可；或执行：

```bash
xattr -dr com.apple.quarantine dist/video2text.app
```

**构建后启动闪退**
用终端直接运行内部可执行文件看报错：

```bash
./dist/video2text.app/Contents/MacOS/video2text
```
