#!/usr/bin/env bash
# 在 macOS 上把 video2text 打包成可双击的 video2text.app
#
# 用法:
#   PYTHON=/path/to/python3 bash packaging/build_macos.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

"$PYTHON" -m PyInstaller \
  --noconfirm --clean \
  --name video2text \
  --windowed \
  --osx-bundle-identifier com.video2text.app \
  --collect-all faster_whisper \
  --collect-all ctranslate2 \
  --collect-all imageio_ffmpeg \
  --collect-all av \
  --collect-all yt_dlp \
  --collect-all onnxruntime \
  --collect-all tokenizers \
  --hidden-import huggingface_hub \
  --hidden-import numpy \
  packaging/entry.py

echo
echo "完成。产物: dist/video2text.app"
echo "首次运行会下载 Whisper 模型（可选 tiny/base 以减小下载量）。"
echo "若系统提示「无法验证开发者」：右键点 App → 打开，或执行"
echo "  xattr -dr com.apple.quarantine dist/video2text.app"
