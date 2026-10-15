#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文字尋找器 GUI v1.1 - 全目錄搜尋
支援: 自動編碼辨識(UTF8/BIG5/GBK/UTF16)、正則表達式、大小寫、子目錄、預覽、匯出
更新: 關鍵字/路徑/副檔名輸入框支援右鍵複製貼上 + Ctrl+A 全選
"""
import os
import re
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

COMMON_ENCODINGS = ["utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk", "big5", "cp950", "ascii"]

def detect_bom(b: bytes):
    if b.startswith(b'\xef\xbb\xbf'): return 'utf-8-sig'
    if b.startswith(b'\xff\xfe\x00\x00'): return 'utf-32-le'
    if b.startswith(b'\x00\x00\xfe\xff'): return 'utf-32-be'
    if b.startswith(b'\xff\xfe'): return 'utf-16-le'
    if b.startswith(b'\xfe\xff'): return 'utf-16-be'
    return None

def read_text_smart(path: Path):
    """嘗試多種編碼讀取，回傳 (lines, encoding_used)"""
    raw = path.read_bytes()
    if len(raw) > 10*1024*1024: # 超過10MB跳過避免卡死
        raise ValueError("檔案過大>10MB跳過")
    bom = detect_bom(raw)
    try_orders = ([bom] if bom else []) + COMMON_ENCODINGS
    for enc in try_orders:
        if not enc: continue
        try:
            text = raw.decode(enc)
            return text.splitlines(), enc
        except:
            continue
    # 最後用 replace
    text = raw.decode('utf-8', errors='replace')
    return text.splitlines(), 'utf-8(replace)'

HELP_TEXT = """
【文字尋找器 v1.1 使用說明】

1. 選擇資料夾：點「瀏覽」選擇要搜尋的目錄
2. 輸入關鍵字：要找的文字，支援中文（可右鍵複製貼上 / Ctrl+V）
3. 設定選項：
   • 區分大小寫：勾選後 A≠a
   • 正則表達式：可用 Regex，如 \\d+ 找數字、error.*timeout
   • 全字匹配：只找完整單詞
   • 包含子資料夾：遞迴搜尋
   • 副檔名：預設 txt,log,srt,csv,py,md 等，逗號分隔

4. 按「開始搜尋」：結果會顯示在下方列表
5. 點擊結果：下方預覽該行前後文
6. 雙擊結果：用系統預設程式打開檔案並定位
7. 右鍵選單：打開檔案位置、複製路徑
8. 匯出：把結果存成 txt/csv

【正則範例】
  \\bError\\b         找完整單詞 Error
  \\d{4}-\\d{2}-\\d{2}   找日期 2023-01-01
  TODO|FIXME         找 TODO 或 FIXME
  ^\\s*def\\s+        找 Python函數定義

提示：大量檔案時建議先用副檔名過濾加快速度
關鍵字欄位支援：右鍵 → 剪下/複製/貼上/全選，以及 Ctrl+A / Ctrl+C / Ctrl+V / Ctrl+X
"""

class TextFinderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("文字尋找器 GUI - 全目錄搜尋 v1.1")
        self.geometry("980x700")
        
        # 狀態
        self.searching = False
        self.results = []  # list of dict
        self.files_scanned = 0
        
        self._build_ui()

    def _add_clipboard_menu(self, entry):
        """為 Entry 加入右鍵複製貼上選單，並支援 Ctrl+A 全選"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="剪下", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="複製", command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="貼上", command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="全選", command=lambda: entry.select_range(0, tk.END))

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        entry.bind("<Button-3>", show_menu)
        # 確保 Ctrl+A 全選（部分平台預設沒有）
        entry.bind("<Control-a>", lambda e: (entry.select_range(0, tk.END), "break"))
        entry.bind("<Control-A>", lambda e: (entry.select_range(0, tk.END), "break"))

    def _build_ui(self):
        # === 頂部路徑區 ===
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="資料夾:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value=str(Path.home()))
        self.path_entry = ttk.Entry(top, textvariable=self.path_var, width=55)
        self.path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self._add_clipboard_menu(self.path_entry)
        ttk.Button(top, text="瀏覽...", command=self.browse).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="HELP", command=self.show_help).pack(side=tk.LEFT, padx=5)

        # === 搜尋設定區 ===
        setting = ttk.LabelFrame(self, text="搜尋設定", padding=10)
        setting.pack(fill=tk.X, padx=10, pady=5)

        # 第一行：關鍵字
        row1 = ttk.Frame(setting)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="關鍵字:").pack(side=tk.LEFT)
        self.keyword_var = tk.StringVar()
        self.keyword_entry = ttk.Entry(row1, textvariable=self.keyword_var, width=50, font=("", 11))
        self.keyword_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.keyword_entry.bind('<Return>', lambda e: self.start_search())
        self._add_clipboard_menu(self.keyword_entry)  # ← 關鍵字支援複製貼上
        ttk.Button(row1, text="開始搜尋", command=self.start_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="停止", command=self.stop_search).pack(side=tk.LEFT)

        # 第二行：選項
        row2 = ttk.Frame(setting)
        row2.pack(fill=tk.X, pady=3)
        self.case_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.word_var = tk.BooleanVar(value=False)
        self.recursive_var = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(row2, text="區分大小寫", variable=self.case_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row2, text="正則表達式", variable=self.regex_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row2, text="全字匹配", variable=self.word_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row2, text="包含子資料夾", variable=self.recursive_var).pack(side=tk.LEFT, padx=15)

        ttk.Label(row2, text="副檔名:").pack(side=tk.LEFT, padx=(20,2))
        self.ext_var = tk.StringVar(value="txt, log, srt, csv, md, py, json, xml, html, ini, conf")
        self.ext_entry = ttk.Entry(row2, textvariable=self.ext_var, width=35)
        self.ext_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self._add_clipboard_menu(self.ext_entry)

        # === 結果區 ===
        result_frame = ttk.Frame(self, padding=(10,5))
        result_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview
        columns = ("file", "line", "preview", "encoding")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=15)
        self.tree.heading("file", text="檔案路徑")
        self.tree.heading("line", text="行號")
        self.tree.heading("preview", text="內容預覽")
        self.tree.heading("encoding", text="編碼")
        self.tree.column("file", width=350)
        self.tree.column("line", width=60, anchor=tk.CENTER)
        self.tree.column("preview", width=450)
        self.tree.column("encoding", width=80, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(result_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 右鍵選單
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="打開檔案", command=self.open_selected_file)
        self.menu.add_command(label="打開所在資料夾", command=self.open_selected_folder)
        self.menu.add_command(label="複製檔案路徑", command=self.copy_path)
        self.menu.add_separator()
        self.menu.add_command(label="複製該行內容", command=self.copy_content)

        # === 預覽區 ===
        preview_frame = ttk.LabelFrame(self, text="內容預覽 (點擊上方結果)", padding=5)
        preview_frame.pack(fill=tk.BOTH, padx=10, pady=5)
        self.preview_text = tk.Text(preview_frame, height=8, font=("Consolas", 10), wrap=tk.NONE)
        self.preview_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        preview_scroll = ttk.Scrollbar(preview_frame, command=self.preview_text.yview)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.config(yscrollcommand=preview_scroll.set)

        # === 底部狀態列 ===
        bottom = ttk.Frame(self, padding=5)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="就緒 | 輸入關鍵字後按開始搜尋")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT)
        
        btn_box = ttk.Frame(bottom)
        btn_box.pack(side=tk.RIGHT)
        ttk.Button(btn_box, text="清空結果", command=self.clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="匯出結果", command=self.export).pack(side=tk.LEFT, padx=2)

    def browse(self):
        d = filedialog.askdirectory()
        if d:
            self.path_var.set(d)

    def show_help(self):
        messagebox.showinfo("HELP 說明", HELP_TEXT)

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.results.clear()
        self.preview_text.delete('1.0', tk.END)
        self.status_var.set("已清空")

    def get_exts(self):
        raw = self.ext_var.get()
        exts = set([e.strip().lower().lstrip('.') for e in raw.replace('，', ',').split(',') if e.strip()])
        return exts

    def compile_pattern(self, keyword):
        if not keyword:
            return None
        flags = 0 if self.case_var.get() else re.IGNORECASE
        if self.regex_var.get():
            try:
                pat = re.compile(keyword, flags)
            except re.error as e:
                messagebox.showerror("正則錯誤", f"正則表達式錯誤:\n{e}")
                return None
        else:
            # 普通文字搜尋，轉義後看是否全字匹配
            esc = re.escape(keyword)
            if self.word_var.get():
                esc = r'\b' + esc + r'\b'
            pat = re.compile(esc, flags)
        return pat

    def start_search(self):
        if self.searching:
            return
        keyword = self.keyword_var.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "請輸入關鍵字")
            return
        root = Path(self.path_var.get())
        if not root.is_dir():
            messagebox.showerror("錯誤", "資料夾不存在")
            return
        
        pattern = self.compile_pattern(keyword)
        if pattern is None:
            return

        self.clear()
        self.searching = True
        self.files_scanned = 0
        self.status_var.set(f"搜尋中: {keyword} ...")
        
        # 在新線程搜尋避免卡UI
        thread = threading.Thread(target=self.search_worker, args=(root, pattern), daemon=True)
        thread.start()

    def stop_search(self):
        self.searching = False
        self.status_var.set("已停止")

    def search_worker(self, root: Path, pattern: re.Pattern):
        exts = self.get_exts()
        recursive = self.recursive_var.get()
        
        files = []
        try:
            if recursive:
                for dirpath, _, filenames in os.walk(root):
                    if not self.searching: break
                    for fn in filenames:
                        p = Path(dirpath) / fn
                        if not exts or p.suffix.lower().lstrip('.') in exts:
                            files.append(p)
            else:
                for p in root.iterdir():
                    if p.is_file():
                        if not exts or p.suffix.lower().lstrip('.') in exts:
                            files.append(p)
        except Exception as e:
            self.after(0, lambda: self.status_var.set(f"遍歷失敗: {e}"))
            self.searching = False
            return

        matched_count = 0
        for idx, fpath in enumerate(files):
            if not self.searching:
                break
            self.files_scanned += 1
            if idx % 20 == 0:
                self.after(0, lambda c=self.files_scanned, t=len(files): self.status_var.set(f"掃描中 {c}/{t} | 已找到 {matched_count} 筆..."))
            try:
                lines, enc = read_text_smart(fpath)
            except Exception:
                continue
            
            for line_no, line in enumerate(lines, start=1):
                if not self.searching:
                    break
                if pattern.search(line):
                    matched_count += 1
                    item = {
                        "file": str(fpath),
                        "line": line_no,
                        "preview": line.strip()[:500],
                        "encoding": enc,
                        "full_line": line,
                    }
                    self.results.append(item)
                    # 回主線程更新UI
                    self.after(0, lambda it=item: self.add_result_row(it))
        
        self.searching = False
        self.after(0, lambda: self.status_var.set(f"完成 | 掃描 {self.files_scanned} 個檔案 | 找到 {matched_count} 筆 | {datetime.now().strftime('%H:%M:%S')}"))

    def add_result_row(self, item):
        self.tree.insert("", tk.END, values=(item["file"], item["line"], item["preview"], item["encoding"]))

    def get_selected_item(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = self.tree.index(sel[0])
        if idx < len(self.results):
            return self.results[idx]
        return None

    def on_select(self, event):
        item = self.get_selected_item()
        if not item:
            return
        self.preview_text.delete('1.0', tk.END)
        # 讀取前後文
        try:
            lines, _ = read_text_smart(Path(item["file"]))
            start = max(0, item["line"]-4)
            end = min(len(lines), item["line"]+3)
            for i in range(start, end):
                prefix = ">>> " if i+1 == item["line"] else "    "
                self.preview_text.insert(tk.END, f"{prefix}{i+1:4d} | {lines[i]}\n")
        except Exception as e:
            self.preview_text.insert(tk.END, f"{item['full_line']}\n\n[讀取失敗: {e}]")

    def on_double_click(self, event):
        self.open_selected_file()

    def open_selected_file(self):
        item = self.get_selected_item()
        if not item: return
        try:
            # Windows用os.startfile，其他用webbrowser
            if sys.platform.startswith('win'):
                os.startfile(item["file"])
            else:
                webbrowser.open(item["file"])
        except Exception as e:
            messagebox.showerror("打開失敗", str(e))

    def open_selected_folder(self):
        item = self.get_selected_item()
        if not item: return
        folder = str(Path(item["file"]).parent)
        try:
            if sys.platform.startswith('win'):
                os.startfile(folder)
            else:
                webbrowser.open(folder)
        except Exception as e:
            messagebox.showerror("打開失敗", str(e))

    def copy_path(self):
        item = self.get_selected_item()
        if not item: return
        self.clipboard_clear()
        self.clipboard_append(item["file"])
        self.status_var.set("已複製路徑到剪貼簿")

    def copy_content(self):
        item = self.get_selected_item()
        if not item: return
        self.clipboard_clear()
        self.clipboard_append(item["full_line"])
        self.status_var.set("已複製內容到剪貼簿")

    def show_context_menu(self, event):
        # 選中該行
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.menu.post(event.x_root, event.y_root)

    def export(self):
        if not self.results:
            messagebox.showinfo("提示", "沒有結果可匯出")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("CSV file", "*.csv"), ("All", "*.*")],
            initialfile=f"search_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                if path.lower().endswith('.csv'):
                    f.write("檔案,行號,編碼,內容\n")
                    for r in self.results:
                        safe = r["preview"].replace('"', '""')
                        f.write(f'"{r["file"]}",{r["line"]},"{r["encoding"]}","{safe}"\n')
                else:
                    for r in self.results:
                        f.write(f"{r['file']}:{r['line']} [{r['encoding']}] {r['preview']}\n")
            messagebox.showinfo("完成", f"已匯出 {len(self.results)} 筆到\n{path}")
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))

if __name__ == "__main__":
    app = TextFinderApp()
    app.mainloop()
