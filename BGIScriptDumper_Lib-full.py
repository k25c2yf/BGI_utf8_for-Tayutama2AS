# -*- coding: utf-8 -*-
# BGIScriptDumper_Lib: for BGI library-type scripts (e.g. Custom) with a large
# header (function table) whose first pushed string is not the pool start.
# Use the original BGIScriptDumper for normal scenario chapters.
# Same output as the original for normal scripts; additionally handles scripts
# whose header is large (e.g. Custom) and whose first string push is not the
# start of the string pool. Also works on non-Windows ('<L' instead of 'L').
import sys, struct, unicodedata

if len(sys.argv) < 2:
    print("usage: " + sys.argv[0] + " <script>")
    sys.exit(1)
SC = sys.argv[1]; EX = SC + ".txt"
data = open(SC, 'rb').read()
if not data.startswith(b'BurikoCompiledScript'):
    print(SC + " Error!\tNot a script file!"); sys.exit(1)

# FIX 1: code start = 0x1C + header size (u32 at 0x1C), instead of scanning for 01 00 00 00
offset = 0x1C + struct.unpack_from('<I', data, 0x1C)[0]

# FIX 2: string pool start = smallest push-string (03) operand that points just
# after a NUL inside the file tail, instead of the operand of the first 03 found.
first = None; cands = []
for pos in range(offset, len(data) - 8, 4):
    if data[pos:pos+4] == b'\x03\x00\x00\x00':
        v = struct.unpack_from('<I', data, pos + 4)[0]
        if first is None: first = v
        a = offset + v
        if pos < a < len(data) and data[a-1] == 0:
            cands.append(v)
def _is_pool(seg):
    # True if seg is a run of NUL-terminated printable Shift-JIS/ASCII strings
    if not seg: return True
    for part in seg.split(b'\x00'):
        if not part: continue
        try: t = part.decode('cp932')
        except UnicodeDecodeError: return False
        if any(ord(c) < 0x20 and c not in '\r\n\t' for c in t): return False
    return True
# Start from the first-pushed string (original behaviour) and extend the pool
# start downward only while the bytes in between are clearly strings.
locate = first
for c in sorted(set(v for v in cands if first is not None and v < first), reverse=True):
    if _is_pool(data[offset + c: offset + locate]):
        locate = c
    else:
        break
textInFile = data[locate + offset:]
textOffset = locate
end = locate + offset

# Same loop as the original
out = open(EX, 'w', 1, "UTF_16")
p = offset
while p < end:
    test = data[p:p+4]; p += 4
    if test == b'\x03\x00\x00\x00':
        address = p
        v = struct.unpack_from('<L', data, p)[0]; p += 4
        tl = v - textOffset
        text = textInFile[tl:textInFile.find(b'\x00', tl)] if tl >= 0 else b''
        try:
            t = text.decode('Shift-JIS')
        except Exception:
            continue
        if t and unicodedata.east_asian_width(t[0]) != '':
            out.write('●' + '%.6d' % address + '●' + t + '\n')
out.close()
print("Finished!")
