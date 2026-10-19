# -*- coding: utf-8 -*-
# 繁體中文轉簡體中文 (big5 TC txt -> gbk SC txt)
# 用法：在專案根目錄執行  python 繁體中文轉簡體中文.py
# 讀 ./big5/*.txt，寫 ./gbk/（同檔名，UTF-8，保留各檔 BOM 有無與換行方式）
# 依賴：opencc-python-reimplemented
#
# 1. 有 ./sc_override/<同檔名> 時直接原樣複製（Custom、SetupForEtc 的人工校訂簡中）
# 2. 只轉換 ●ID● 之後的文字；ID、<...> 標籤、__ 控制碼行、jp/jpname 中列出的說話人行一律不動
# 3. opencc t2s 後再套用補正表（著→着 依語境、妳→你、想像→想象…）
import os, re, sys, shutil
import opencc

SRC, DST, OVR, JPN = './big5', './gbk', './sc_override', './jp/jpname'
cc = opencc.OpenCC('t2s')

# 「著」保留的詞（著作義）；其餘一律改「着」
KEEP_ZHU = ['著名', '著作', '著者', '著称', '著述', '著录', '显著', '名著', '原著', '拙著',
            '论著', '专著', '巨著', '编著', '昭著', '卓著', '土著', '遗著', '新著', '译著']
FIX = [('妳', '你'), ('想像', '想象'), ('瞇', '眯'), ('搆', '够'), ('摀', '捂'), ('睪', '睾'),
       ('痺', '痹'), ('砲', '炮'), ('悪', '恶'), ('艶', '艳'), ('簷', '檐'), ('撢', '掸'), ('牠', '它')]
TAG = re.compile(r'(<[^>]*>)')

def fix_zhu(s):
    s = s.replace('彰显著', '彰显着')
    keep = {}
    for i, w in enumerate(KEEP_ZHU):
        if w in s:
            k = '\uE000%d\uE001' % i; keep[k] = w; s = s.replace(w, k)
    s = s.replace('著', '着')
    for k, w in keep.items(): s = s.replace(k, w)
    return s

def conv_text(t):
    out = []
    for part in TAG.split(t):
        if not part or TAG.fullmatch(part):
            out.append(part); continue
        p = cc.convert(part)
        for a, b in FIX: p = p.replace(a, b)
        out.append(fix_zhu(p))
    return ''.join(out)

def speaker_ids(fn):
    base = fn[:-7] if fn.endswith('_tc.txt') else fn[:-4]
    p = os.path.join(JPN, base + '.txt'); ids = set()
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8-sig') as f:
            for l in f:
                if l.startswith('●') and len(l) > 8: ids.add(l[1:7])
    return ids

def main():
    if not os.path.isdir(SRC):
        print('找不到 ' + SRC); sys.exit(1)
    os.makedirs(DST, exist_ok=True)
    nfile = nover = nline = nskip = 0
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith('.txt'): continue
        nfile += 1
        if os.path.exists(os.path.join(OVR, fn)):
            shutil.copyfile(os.path.join(OVR, fn), os.path.join(DST, fn)); nover += 1
            print('[override] ' + fn); continue
        raw = open(os.path.join(SRC, fn), 'rb').read()
        bom = raw.startswith(b'\xef\xbb\xbf')
        text = raw.decode('utf-8-sig')
        sp = speaker_ids(fn)
        lines = text.splitlines(True)  # 保留原換行
        res = []
        for l in lines:
            body = l.rstrip('\r\n'); eol = l[len(body):]
            if body.startswith('●') and len(body) >= 8 and body[7] == '●':
                i, t = body[1:7], body[8:]
                if i in sp or t.startswith('__'):
                    nskip += 1; res.append(l); continue
                nt = conv_text(t)
                if nt != t: nline += 1
                res.append(body[:8] + nt + eol)
            else:
                res.append(l)
        data = ''.join(res).encode('utf-8')
        if bom: data = b'\xef\xbb\xbf' + data
        open(os.path.join(DST, fn), 'wb').write(data)
    print('完成：%d 檔（override %d），轉換 %d 行，保留說話人／控制行 %d 行' % (nfile, nover, nline, nskip))
    cnt = {}
    for fn in os.listdir(DST):
        if fn.endswith('.txt'):
            t = open(os.path.join(DST, fn), encoding='utf-8-sig').read()
            for ch in ('著', '妳'): cnt[ch] = cnt.get(ch, 0) + t.count(ch)
    print('剩餘：著 %d（著作義保留），妳 %d' % (cnt.get('著', 0), cnt.get('妳', 0)))

if __name__ == '__main__':
    main()
