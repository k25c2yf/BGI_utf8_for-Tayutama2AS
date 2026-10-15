#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TXT 轉編碼 GUI 版 v2.0 - 含 HELP
"""
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

ENCODING_OPTIONS = [
    "utf-8 (無BOM, 通用)",
    "utf-8-sig (UTF8 BOM)",
    "utf-16-le (UTF16 LE, Windows記事本預設)",
    "utf-16-be (UTF16 BE)",
    "utf-16 (自動帶BOM)",
    "utf-32-le",
    "utf-32-be",
    "gbk (簡中)",
    "gb18030",
    "big5 (繁中)",
    "ascii",
    "mbcs (Windows ANSI 自動)",
]

ENC_MAP = {
    "utf-8 (無BOM, 通用)": "utf-8",
    "utf-8-sig (UTF8 BOM)": "utf-8-sig",
    "utf-16-le (UTF16 LE, Windows記事本預設)": "utf-16-le",
    "utf-16-be (UTF16 BE)": "utf-16-be",
    "utf-16 (自動帶BOM)": "utf-16",
    "utf-32-le": "utf-32-le",
    "utf-32-be": "utf-32-be",
    "gbk (簡中)": "gbk",
    "gb18030": "gb18030",
    "big5 (繁中)": "big5",
    "ascii": "ascii",
    "mbcs (Windows ANSI 自動)": "mbcs",
}

COMMON_DETECT = ["utf-8-sig","utf-8","utf-16","utf-16-le","utf-16-be","gb18030","gbk","big5"]

HELP_TEXT = """
【TXT批量轉編碼工具 - 使用說明】

1. 選擇要處理的資料夾
2. 來源編碼建議保持 auto 自動偵測
3. 目標編碼選擇你想要的：
   • utf-8 (無BOM) = 網站、Python通用
   • utf-8-sig (BOM) = Excel打開CSV不亂碼
   • utf-16-le = Windows記事本Unicode
   • gbk/big5 = 舊Windows系統

4. 副檔名：預設 txt，可填 txt,srt,log,csv
5. 勾選「包含子資料夾」會遞迴處理
6. 勾選「備份原檔」安全起見建議勾上

【常見問題】
Q: UTF8 LE 是什麼？
A: UTF8沒有大小端，選 utf-8 就對了

Q: UTF8 BOM 是什麼？
A: 就是 utf-8-sig，會在檔頭多3個字節 EF BB BF，讓Windows認得是UTF8

Q: 亂碼怎麼修？
A: 來源選 gbk 或 big5，目標選 utf-8-sig

Q: 命令行怎麼用？
A: python txt_encoding_converter_v2.py --help 查看
"""

def detect_bom(data: bytes):
    if data.startswith(b'\xef\xbb\xbf'): return 'utf-8-sig'
    if data.startswith(b'\xff\xfe\x00\x00'): return 'utf-32-le'
    if data.startswith(b'\x00\x00\xfe\xff'): return 'utf-32-be'
    if data.startswith(b'\xff\xfe'): return 'utf-16-le'
    if data.startswith(b'\xfe\xff'): return 'utf-16-be'
    return None

def decode_auto(filepath: Path, src_enc):
    raw = filepath.read_bytes()
    if not raw:
        return "", "empty"
    if src_enc != "auto":
        return raw.decode(src_enc), src_enc
    bom = detect_bom(raw)
    order = ([bom] if bom else []) + COMMON_DETECT
    for enc in order:
        if not enc: continue
        try:
            return raw.decode(enc), enc
        except:
            continue
    return raw.decode('utf-8', errors='replace'), 'utf-8(replace)'

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TXT 批量轉編碼工具 v2.0 - 含HELP")
        self.geometry("720x580")
        
        frm = ttk.Frame(self, padding=15)
        frm.pack(fill=tk.X)
        ttk.Label(frm, text="資料夾:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.path_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(frm, text="瀏覽...", command=self.browse).pack(side=tk.LEFT)

        opt = ttk.LabelFrame(self, text="轉換設定", padding=15)
        opt.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(opt, text="來源編碼:").grid(row=0, column=0, sticky=tk.W)
        self.from_var = tk.StringVar(value="auto (自動偵測)")
        self.from_combo = ttk.Combobox(opt, textvariable=self.from_var, values=["auto (自動偵測)"]+ENCODING_OPTIONS, width=35)
        self.from_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(opt, text="目標編碼:").grid(row=1, column=0, sticky=tk.W)
        self.to_var = tk.StringVar(value="utf-8-sig (UTF8 BOM)")
        self.to_combo = ttk.Combobox(opt, textvariable=self.to_var, values=ENCODING_OPTIONS, width=35)
        self.to_combo.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(opt, text="副檔名:").grid(row=2, column=0, sticky=tk.W)
        self.ext_var = tk.StringVar(value="txt")
        ttk.Entry(opt, textvariable=self.ext_var, width=20).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        self.rec_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="包含子資料夾", variable=self.rec_var).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        self.bak_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="備份原檔 (.bak)", variable=self.bak_var).grid(row=4, column=0, columnspan=2, sticky=tk.W)

        btn_frm = ttk.Frame(self, padding=10)
        btn_frm.pack(fill=tk.X)
        ttk.Button(btn_frm, text="開始轉換", command=self.convert).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frm, text="HELP 說明", command=self.show_help).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frm, text="清空日誌", command=lambda: self.log.delete('1.0', tk.END)).pack(side=tk.LEFT, padx=5)

        self.log = tk.Text(self, height=20)
        self.log.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        self.log.insert(tk.END, "提示：點擊 HELP 查看詳細說明\n")
        self.log.insert(tk.END, "命令行可用 --help 和 --list-encodings\n")

    def browse(self):
        d = filedialog.askdirectory()
        if d:
            self.path_var.set(d)

    def show_help(self):
        messagebox.showinfo("使用說明 HELP", HELP_TEXT)
        self.log.insert(tk.END, HELP_TEXT + "\n")

    def log_msg(self, msg):
        self.log.insert(tk.END, msg+"\n")
        self.log.see(tk.END)
        self.update()

    def convert(self):
        root = Path(self.path_var.get())
        if not root.is_dir():
            messagebox.showerror("錯誤", "請先選擇有效資料夾")
            return
        
        def parse_enc(s):
            if "auto" in s: return "auto"
            for k,v in ENC_MAP.items():
                if s == k: return v
            return s

        from_enc = parse_enc(self.from_var.get())
        to_enc = parse_enc(self.to_var.get())
        exts = set([e.strip().lower().lstrip('.') for e in self.ext_var.get().split(',')])

        files = []
        if self.rec_var.get():
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    p = Path(dirpath)/fn
                    if p.suffix.lower().lstrip('.') in exts:
                        files.append(p)
        else:
            for p in root.iterdir():
                if p.is_file() and p.suffix.lower().lstrip('.') in exts:
                    files.append(p)

        if not files:
            messagebox.showinfo("提示", "沒有找到檔案")
            return

        self.log_msg(f"開始: {root} | {from_enc} -> {to_enc} | 共 {len(files)} 個檔案")
        ok=fail=0
        for f in files:
            try:
                text, det = decode_auto(f, from_enc)
                if self.bak_var.get():
                    shutil.copy2(f, f.with_suffix(f.suffix+".bak"))
                tmp = f.with_suffix(f.suffix+".tmp")
                with open(tmp, 'w', encoding=to_enc, newline='') as out:
                    out.write(text)
                tmp.replace(f)
                self.log_msg(f"[成功] {f.name} : {det} -> {to_enc}")
                ok+=1
            except Exception as e:
                self.log_msg(f"[失敗] {f.name} : {e}")
                fail+=1
        self.log_msg(f"--- 完成 成功:{ok} 失敗:{fail} ---")
        messagebox.showinfo("完成", f"成功 {ok} 個，失敗 {fail} 個\n\nHELP可在日誌查看")

if __name__ == "__main__":
    App().mainloop()
