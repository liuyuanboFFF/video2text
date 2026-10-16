@echo off
REM 在 Windows 上把 video2text 打包成可双击的 video2text.exe
REM 用法: packaging\build_windows.bat

cd /d "%~dp0\.."

py -m PyInstaller ^
  --noconfirm --clean ^
  --name video2text ^
  --windowed ^
  --collect-all faster_whisper ^
  --collect-all ctranslate2 ^
  --collect-all imageio_ffmpeg ^
  --collect-all av ^
  --collect-all yt_dlp ^
  --collect-all onnxruntime ^
  --collect-all tokenizers ^
  --hidden-import huggingface_hub ^
  --hidden-import numpy ^
  packaging\entry.py

echo.
echo 完成。产物: dist\video2text\video2text.exe
