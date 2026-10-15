#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文本批量修改器 GUI，單檔運行。

收埋：十六進制↔文字、刪行、半形轉全形、提取短行、文字取代、
二進制 hex / 字串取代。ANSI 指遊戲用嘅 Shift-JIS 或 Big5，唔係 Python 的 ANSI。
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

ENCODINGS = (
    ("Shift-JIS（日文）", "shift_jis"),
    ("Big5（繁中）", "big5"),
    ("GBK（簡中）", "gbk"),
    ("UTF-8", "utf-8"),
)

HALF = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
FULL = "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
HALF_NUM = "0123456789"
FULL_NUM = "０１２３４５６７８９"
DEFAULT_SKIP = "『（─！―「」、…°。"


def to_hex(text: str, encoding: str) -> str:
    return text.encode(encoding).hex().upper()


def from_hex(hex_string: str, encoding: str) -> str:
    cleaned = "".join(hex_string.split())
    cleaned = cleaned.replace("0x", "").replace("0X", "").replace(",", "")
    if cleaned.startswith(("ANSI=", "UTF8=", "UTF-8=")):
        cleaned = cleaned.split("=", 1)[1].strip().strip('"')
    if len(cleaned) % 2:
        raise ValueError("十六進制長度必須是雙數")
    return bytes.fromhex(cleaned).decode(encoding)


def half_to_full(text: str, digits: bool = False) -> str:
    text = text.translate(str.maketrans(HALF, FULL))
    if digits:
        text = text.translate(str.maketrans(HALF_NUM, FULL_NUM))
    return text


def delete_lines(text: str, words: list[str]) -> str:
    words = [w for w in words if w]
    if not words:
        return text
    keep = [line for line in text.splitlines(keepends=True) if not any(w in line for w in words)]
    return "".join(keep)


def extract_lines(text: str, max_len: int, skip_chars: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s and len(s) <= max_len and not any(ch in s for ch in skip_chars):
            out.append(s)
    return "\n".join(out) + ("\n" if out else "")


def apply_replaces(text: str, pairs: list[tuple[str, str]]) -> str:
    for old, new in pairs:
        if old:
            text = text.replace(old, new)
    return text


def parse_pairs(raw: str) -> list[tuple[str, str]]:
    pairs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" in line:
            old, new = line.split("=>", 1)
        elif "=" in line:
            old, new = line.split("=", 1)
        else:
            raise ValueError(f"取代行要寫成 舊=新 ：{line}")
        pairs.append((old, new))
    return pairs


def pad_bytes(src: bytes, dst: bytes, pad: bytes = b"\x00") -> bytes:
    if len(dst) > len(src):
        raise ValueError(f"新內容較長（{len(dst)} > {len(src)} bytes）。二進制取代要等長，否則會移位。")
    if len(dst) < len(src):
        dst += pad * (len(src) - len(dst))
    return dst


def replace_bytes(data: bytes, old: bytes, new: bytes, first_only: bool) -> tuple[bytes, int]:
    if not old:
        raise ValueError("搜尋內容是空的")
    count = data.count(old)
    if count == 0:
        return data, 0
    if first_only:
        idx = data.index(old)
        return data[:idx] + new + data[idx + len(old):], 1
    return data.replace(old, new), count


try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False


HELP = """
【文本批量修改器】單檔即可跑

1. 文字↔十六進制
   輸出格式同舊腳本：ANSI="..."  UTF8="..."
   ANSI 要自己選 Shift-JIS 或 Big5。

2. 文本批次
   處理資料夾入面嘅 .txt。
   刪行、取代、半形英文轉全形、抽出短行，可以疊加。
   預設寫去輸出資料夾，唔覆蓋原檔。

3. 二進制取代
   字串會先轉成所選編碼再搜。
   新內容較短會補 00；較長會拒絕，避免腳本移位。
   只取代第一個，同舊 hex 腳本一樣。勾選就可以全部取代。
"""


class App:
    def __init__(self, root):
        self.root = root
        root.title("文本批量修改器")
        root.geometry("980x740")
        self.busy = False
        nb = ttk.Notebook(root)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.tab_hex = ttk.Frame(nb, padding=10)
        self.tab_txt = ttk.Frame(nb, padding=10)
        self.tab_bin = ttk.Frame(nb, padding=10)
        nb.add(self.tab_hex, text="文字 ↔ 十六進制")
        nb.add(self.tab_txt, text="文本批次")
        nb.add(self.tab_bin, text="二進制取代")
        self._build_hex()
        self._build_txt()
        self._build_bin()

        bottom = ttk.Frame(root, padding=6)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="HELP", command=lambda: messagebox.showinfo("HELP", HELP)).pack(side=tk.LEFT)
        self.status = tk.StringVar(value="就緒")
        ttk.Label(bottom, textvariable=self.status).pack(side=tk.LEFT, padx=12)
        self.progress = ttk.Progressbar(bottom, mode="indeterminate")
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=8)

        logf = ttk.LabelFrame(root, text="日誌", padding=6)
        logf.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 8))
        self.log_text = tk.Text(logf, height=8, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sb = ttk.Scrollbar(logf, command=self.log_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=sb.set)

    def log(self, msg: str):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def _enc_box(self, parent):
        box = ttk.Combobox(parent, state="readonly", width=22, values=[n for n, _ in ENCODINGS])
        box.current(0)
        return box

    def _enc(self, box) -> str:
        return dict(ENCODINGS)[box.get()]

    def _build_hex(self):
        f = self.tab_hex
        row = ttk.Frame(f)
        row.pack(fill=tk.X)
        ttk.Label(row, text="ANSI 編碼").pack(side=tk.LEFT)
        self.hex_enc = self._enc_box(row)
        self.hex_enc.pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="文字 → Hex", command=self.do_to_hex).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="Hex → 文字", command=self.do_from_hex).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="複製結果", command=self.copy_hex).pack(side=tk.LEFT, padx=4)
        ttk.Label(f, text="輸入").pack(anchor=tk.W, pady=(8, 2))
        self.hex_in = tk.Text(f, height=10, font=("Consolas", 11))
        self.hex_in.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="結果").pack(anchor=tk.W, pady=(8, 2))
        self.hex_out = tk.Text(f, height=10, font=("Consolas", 11))
        self.hex_out.pack(fill=tk.BOTH, expand=True)

    def do_to_hex(self):
        text = self.hex_in.get("1.0", "end-1c")
        enc = self._enc(self.hex_enc)
        try:
            ansi = to_hex(text, enc)
            utf = to_hex(text, "utf-8")
        except Exception as e:
            messagebox.showerror("轉換失敗", str(e))
            return
        self.hex_out.delete("1.0", tk.END)
        self.hex_out.insert(tk.END, f'ANSI="{ansi}"\nUTF8="{utf}"')
        self.log(f"文字→Hex  {enc}  {len(ansi)//2} bytes")

    def do_from_hex(self):
        raw = self.hex_in.get("1.0", "end-1c").strip()
        enc = self._enc(self.hex_enc)
        try:
            text = from_hex(raw, enc)
        except Exception as e:
            messagebox.showerror("轉換失敗", str(e))
            return
        self.hex_out.delete("1.0", tk.END)
        self.hex_out.insert(tk.END, f'{enc}="{text}"')
        self.log(f"Hex→文字  {enc}  {text}")

    def copy_hex(self):
        text = self.hex_out.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("已複製結果")

    def _build_txt(self):
        f = self.tab_txt
        top = ttk.Frame(f)
        top.pack(fill=tk.X)
        self.txt_in = tk.StringVar()
        self.txt_out = tk.StringVar()
        ttk.Label(top, text="輸入資料夾").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.txt_in, width=62).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(top, text="選資料夾", command=lambda: self._pick_dir(self.txt_in)).grid(row=0, column=2)
        ttk.Label(top, text="輸出資料夾").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(top, textvariable=self.txt_out, width=62).grid(row=1, column=1, padx=4, sticky=tk.EW)
        ttk.Button(top, text="選資料夾", command=lambda: self._pick_dir(self.txt_out)).grid(row=1, column=2)
        top.columnconfigure(1, weight=1)

        opt = ttk.Frame(f)
        opt.pack(fill=tk.X, pady=6)
        ttk.Label(opt, text="讀檔編碼").pack(side=tk.LEFT)
        self.txt_enc = self._enc_box(opt)
        self.txt_enc.current(3)
        self.txt_enc.pack(side=tk.LEFT, padx=6)
        self.do_del = tk.BooleanVar(value=True)
        self.do_rep = tk.BooleanVar(value=True)
        self.do_full = tk.BooleanVar(value=False)
        self.do_ext = tk.BooleanVar(value=False)
        self.do_digits = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="刪含字行", variable=self.do_del).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(opt, text="取代", variable=self.do_rep).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(opt, text="半形英文→全形", variable=self.do_full).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(opt, text="連數字", variable=self.do_digits).pack(side=tk.LEFT)
        ttk.Checkbutton(opt, text="只抽出短行", variable=self.do_ext).pack(side=tk.LEFT, padx=6)

        mid = ttk.PanedWindow(f, orient=tk.HORIZONTAL)
        mid.pack(fill=tk.BOTH, expand=True, pady=4)
        left = ttk.LabelFrame(mid, text="刪除這些字（一行一個）", padding=6)
        mid.add(left, weight=1)
        self.words = tk.Text(left, height=8, font=("Microsoft JhengHei UI", 10))
        self.words.pack(fill=tk.BOTH, expand=True)
        self.words.insert("1.0", "Ｈｅｌｌｏ，ｇｏｏｄ−ｂｙｅ：")
        right = ttk.LabelFrame(mid, text="取代  舊=新   一行一組", padding=6)
        mid.add(right, weight=1)
        self.pairs = tk.Text(right, height=8, font=("Microsoft JhengHei UI", 10))
        self.pairs.pack(fill=tk.BOTH, expand=True)
        self.pairs.insert("1.0", "喫=吃")

        ext = ttk.Frame(f)
        ext.pack(fill=tk.X, pady=4)
        ttk.Label(ext, text="短行上限").pack(side=tk.LEFT)
        self.max_len = tk.StringVar(value="22")
        ttk.Entry(ext, textvariable=self.max_len, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(ext, text="含這些字就跳過").pack(side=tk.LEFT, padx=(12, 4))
        self.skip = tk.StringVar(value=DEFAULT_SKIP)
        ttk.Entry(ext, textvariable=self.skip, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(f, text="開始處理文本", command=self.start_txt).pack(anchor=tk.E, pady=4)

    def _build_bin(self):
        f = self.tab_bin
        top = ttk.Frame(f)
        top.pack(fill=tk.X)
        self.bin_in = tk.StringVar()
        self.bin_out = tk.StringVar()
        ttk.Label(top, text="輸入檔案或資料夾").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.bin_in, width=52).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(top, text="選檔案", command=self._pick_bin_file).grid(row=0, column=2)
        ttk.Button(top, text="選資料夾", command=lambda: self._pick_dir(self.bin_in)).grid(row=0, column=3, padx=2)
        ttk.Label(top, text="輸出（留空就覆蓋，會先做 .bak）").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(top, textvariable=self.bin_out, width=52).grid(row=1, column=1, padx=4, sticky=tk.EW)
        ttk.Button(top, text="選資料夾", command=lambda: self._pick_dir(self.bin_out)).grid(row=1, column=3)
        top.columnconfigure(1, weight=1)

        opt = ttk.Frame(f)
        opt.pack(fill=tk.X, pady=6)
        self.bin_mode = tk.StringVar(value="text")
        ttk.Radiobutton(opt, text="字串", variable=self.bin_mode, value="text").pack(side=tk.LEFT)
        ttk.Radiobutton(opt, text="Hex", variable=self.bin_mode, value="hex").pack(side=tk.LEFT, padx=8)
        ttk.Label(opt, text="字串編碼").pack(side=tk.LEFT, padx=(12, 4))
        self.bin_enc = self._enc_box(opt)
        self.bin_enc.pack(side=tk.LEFT)
        self.bin_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="全部取代（預設只第一個）", variable=self.bin_all).pack(side=tk.LEFT, padx=12)

        box = ttk.Frame(f)
        box.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(box, text="搵", padding=6)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        self.bin_old = tk.Text(left, height=8, font=("Consolas", 11))
        self.bin_old.pack(fill=tk.BOTH, expand=True)
        right = ttk.LabelFrame(box, text="換成（較短會補 00）", padding=6)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.bin_new = tk.Text(right, height=8, font=("Consolas", 11))
        self.bin_new.pack(fill=tk.BOTH, expand=True)
        ttk.Button(f, text="開始取代", command=self.start_bin).pack(anchor=tk.E, pady=6)

    def _pick_dir(self, var):
        d = filedialog.askdirectory()
        if d:
            var.set(d)

    def _pick_bin_file(self):
        f = filedialog.askopenfilename()
        if f:
            self.bin_in.set(f)

    def start_txt(self):
        if self.busy:
            return
        src = self.txt_in.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("錯誤", "請先選擇輸入資料夾")
            return
        try:
            pairs = parse_pairs(self.pairs.get("1.0", "end-1c")) if self.do_rep.get() else []
            max_len = int(self.max_len.get())
        except Exception as e:
            messagebox.showerror("設定錯誤", str(e))
            return
        words = [w.strip() for w in self.words.get("1.0", tk.END).splitlines() if w.strip()]
        self._run(self._txt_worker, src, self.txt_out.get().strip(), self._enc(self.txt_enc), words, pairs, max_len)

    def _txt_worker(self, src, out, enc, words, pairs, max_len):
        outdir = out or os.path.join(src, "temp")
        os.makedirs(outdir, exist_ok=True)
        files = [n for n in sorted(os.listdir(src)) if n.lower().endswith(".txt")]
        ok = fail = 0
        for name in files:
            try:
                raw = Path(os.path.join(src, name)).read_text(encoding=enc)
                if self.do_del.get():
                    raw = delete_lines(raw, words)
                if self.do_rep.get():
                    raw = apply_replaces(raw, pairs)
                if self.do_full.get():
                    raw = half_to_full(raw, self.do_digits.get())
                if self.do_ext.get():
                    raw = extract_lines(raw, max_len, self.skip.get())
                    dest_name = f"jp_{name}"
                else:
                    dest_name = name
                Path(os.path.join(outdir, dest_name)).write_text(raw, encoding="utf-8")
                ok += 1
                self.root.after(0, lambda n=name: self.log(f"OK  {n}"))
            except Exception as e:
                fail += 1
                self.root.after(0, lambda n=name, e=e: self.log(f"失敗  {n} : {e}"))
        self.root.after(0, lambda: self._done(ok, fail, outdir))

    def start_bin(self):
        if self.busy:
            return
        src = self.bin_in.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showerror("錯誤", "請先選擇檔案或資料夾")
            return
        old = self.bin_old.get("1.0", "end-1c")
        new = self.bin_new.get("1.0", "end-1c")
        try:
            old_b, new_b = self._bin_payload(old, new)
        except Exception as e:
            messagebox.showerror("內容錯誤", str(e))
            return
        self._run(self._bin_worker, src, self.bin_out.get().strip(), old_b, new_b, self.bin_all.get())

    def _bin_payload(self, old: str, new: str) -> tuple[bytes, bytes]:
        if self.bin_mode.get() == "hex":
            old_b = bytes.fromhex("".join(old.split()))
            new_b = bytes.fromhex("".join(new.split()))
        else:
            enc = self._enc(self.bin_enc)
            old_b = old.encode(enc)
            new_b = new.encode(enc)
        return old_b, pad_bytes(old_b, new_b)

    def _bin_worker(self, src, out, old_b, new_b, all_hits):
        paths = []
        if os.path.isdir(src):
            for name in sorted(os.listdir(src)):
                path = os.path.join(src, name)
                if os.path.isfile(path):
                    paths.append(path)
            outdir = out or src
        else:
            paths = [src]
            outdir = out or os.path.dirname(src)
        os.makedirs(outdir, exist_ok=True)
        ok = fail = 0
        for path in paths:
            try:
                data = Path(path).read_bytes()
                updated, n = replace_bytes(data, old_b, new_b, not all_hits)
                if n == 0:
                    self.root.after(0, lambda p=path: self.log(f"找不到  {os.path.basename(p)}"))
                    fail += 1
                    continue
                dest = os.path.join(outdir, os.path.basename(path))
                if os.path.abspath(dest) == os.path.abspath(path):
                    bak = path + ".bak"
                    if not os.path.exists(bak):
                        Path(bak).write_bytes(data)
                Path(dest).write_bytes(updated)
                ok += 1
                self.root.after(0, lambda p=path, n=n: self.log(f"OK  {os.path.basename(p)}  取代 {n}"))
            except Exception as e:
                fail += 1
                self.root.after(0, lambda p=path, e=e: self.log(f"失敗  {os.path.basename(p)} : {e}"))
        self.root.after(0, lambda: self._done(ok, fail, outdir))

    def _run(self, fn, *args):
        self.busy = True
        self.progress.start(10)
        self.status.set("處理中...")
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _done(self, ok, fail, folder):
        self.busy = False
        self.progress.stop()
        self.status.set(f"完成 | 成功 {ok} | 失敗 {fail}")
        self.log(f"完成 | 成功 {ok} | 失敗 {fail} | {folder}")
        if ok and folder and os.path.isdir(folder):
            if messagebox.askyesno("完成", f"完成 {ok} 個\n打開資料夾？"):
                try:
                    if os.name == "nt":
                        os.startfile(folder)
                    else:
                        os.system(f'xdg-open "{folder}"')
                except Exception:
                    pass


def main():
    if not HAS_TK:
        print("找不到 tkinter。Windows 請用 python.org 的 Python。")
        return 1
    root = tk.Tk()
    try:
        from tkinter import font
        font.nametofont("TkDefaultFont").configure(family="Microsoft JhengHei UI", size=10)
    except Exception:
        pass
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
