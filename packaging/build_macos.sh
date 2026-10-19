#!/usr/bin/env bash
# 在 macOS 上把 video2text 打包成可双击的 video2text.app
#
# 用法:
#   PYTHON=/path/to/python3 bash packaging/build_macos.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

# 版本号从 pyproject.toml 读，避免 .app 显示 0.0.0
VERSION="$("$PYTHON" - <<'PY'
import re, pathlib
t = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
m = re.search(r'^version\s*=\s*"([^"]+)"', t, re.M)
print(m.group(1) if m else "0.0.0")
PY
)"
echo "打包版本: $VERSION"

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
  --collect-all opencc \
  --hidden-import huggingface_hub \
  --hidden-import numpy \
  packaging/entry.py

# PyInstaller 不支持从命令行设置 bundle 版本（默认写 0.0.0），只能构建后改 Info.plist。
# 注意：改完 Info.plist 会让原有签名失效，必须重新 ad-hoc 签名。
PLIST="dist/video2text.app/Contents/Info.plist"
if [ -f "$PLIST" ]; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$PLIST"
  /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST"
  /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 11.0" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion 11.0" "$PLIST"

  codesign --force --deep --sign - "dist/video2text.app" >/dev/null 2>&1 || true
  echo "Info.plist 版本: $(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")"
  echo "最低系统: $(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$PLIST")"
  codesign --verify --deep --strict "dist/video2text.app" && echo "签名校验: 通过"
fi

echo
echo "完成。产物: dist/video2text.app"
echo "首次运行会下载 Whisper 模型（可选 tiny/base 以减小下载量）。"
echo "若系统提示「无法验证开发者」：右键点 App → 打开，或执行"
echo "  xattr -dr com.apple.quarantine dist/video2text.app"
