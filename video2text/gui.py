"""桌面图形界面（Tkinter）。

选 Tkinter 的原因：它在标准库里，PyInstaller 能原生打包，不引入额外依赖，
打包体积最小。界面只做三件事：收参数、调 pipeline、显示日志。
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__, pipeline

MODELS = ["tiny", "base", "small", "medium", "large-v3"]
FORMATS = ["md", "txt", "srt", "json"]

DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "video2text")


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.queue: "queue.Queue" = queue.Queue()
        self.running = False
        root.title(f"video2text {__version__}")
        root.geometry("780x600")
        root.minsize(680, 520)
        self._build()
        self.root.after(100, self._drain)

    # ---------- 界面 ----------
    def _build(self):
        pad = {"padx": 12, "pady": 6}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="视频链接（每行一个，支持批量；B站 / YouTube / 播客等）").pack(anchor="w")
        self.txt_urls = tk.Text(top, height=4, wrap="word")
        self.txt_urls.pack(fill="x", pady=(4, 0))

        opt = ttk.Frame(self.root)
        opt.pack(fill="x", **pad)
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="输出目录").grid(row=0, column=0, sticky="w")
        self.var_out = tk.StringVar(value=DEFAULT_OUT)
        ttk.Entry(opt, textvariable=self.var_out).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(opt, text="选择…", command=self._pick_dir).grid(row=0, column=2)

        ttk.Label(opt, text="模型").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.var_model = tk.StringVar(value="medium")
        ttk.Combobox(opt, textvariable=self.var_model, values=MODELS,
                     state="readonly", width=12).grid(row=1, column=1, sticky="w",
                                                      padx=6, pady=(8, 0))

        ttk.Label(opt, text="格式").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.var_fmt = tk.StringVar(value="md")
        ttk.Combobox(opt, textvariable=self.var_fmt, values=FORMATS,
                     state="readonly", width=12).grid(row=2, column=1, sticky="w",
                                                      padx=6, pady=(8, 0))

        self.var_sub = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="优先使用字幕（无字幕时自动转写）",
                        variable=self.var_sub).grid(row=3, column=1, sticky="w",
                                                    padx=6, pady=(8, 0))
        self.var_mirror = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="使用国内镜像下载模型（海外可取消）",
                        variable=self.var_mirror).grid(row=4, column=1, sticky="w",
                                                       padx=6, pady=(2, 0))

        bar = ttk.Frame(self.root)
        bar.pack(fill="x", **pad)
        self.btn_run = ttk.Button(bar, text="开始", command=self._start)
        self.btn_run.pack(side="left")
        ttk.Button(bar, text="打开输出目录", command=self._open_out).pack(side="left", padx=6)
        ttk.Button(bar, text="清空日志", command=self._clear).pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.log = tk.Text(self.root, wrap="word", state="disabled", height=16)
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ---------- 事件 ----------
    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.var_out.get() or os.path.expanduser("~"))
        if d:
            self.var_out.set(d)

    def _open_out(self):
        path = self.var_out.get().strip() or DEFAULT_OUT
        try:
            os.makedirs(path, exist_ok=True)
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("打不开", str(e))

    def _clear(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _append(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _start(self):
        if self.running:
            return
        urls = [u.strip() for u in self.txt_urls.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("提示", "请先粘贴至少一个视频链接")
            return
        out = self.var_out.get().strip() or DEFAULT_OUT
        self.var_out.set(out)
        options = pipeline.Options(
            output=out,
            format=self.var_fmt.get(),
            model=self.var_model.get(),
            force_asr=not self.var_sub.get(),
            hf_mirror=self.var_mirror.get(),
        )
        self.running = True
        self.btn_run.config(state="disabled", text="处理中…")
        self.progress.start(12)
        self._append(f"开始处理 {len(urls)} 个链接，输出到 {out}")
        threading.Thread(target=self._worker, args=(urls, options), daemon=True).start()

    def _worker(self, urls, options):
        def log(msg):
            self.queue.put(("log", msg))

        try:
            ok, fail = pipeline.run(urls, options, log=log)
            self.queue.put(("done", (ok, fail)))
        except Exception as e:
            self.queue.put(("error", repr(e)))

    def _finish(self):
        self.running = False
        self.progress.stop()
        self.btn_run.config(state="normal", text="开始")

    def _drain(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._append(payload)
                elif kind == "done":
                    ok, fail = payload
                    self._append(f"\n完成：成功 {len(ok)} 个，失败 {len(fail)} 个")
                    if fail:
                        for url, err in fail:
                            self._append(f"  失败 → {url}：{err}")
                    self._finish()
                elif kind == "error":
                    self._append(f"错误：{payload}")
                    self._finish()
        except queue.Empty:
            pass
        self.root.after(100, self._drain)


def main():
    # 打包成窗口应用后 stdout/stderr 可能为 None，任何 print 都会崩，这里兜底。
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    root = tk.Tk()
    try:
        ttk.Style().theme_use("aqua" if sys.platform == "darwin" else "clam")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
