#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BMP / PNG ↔ BGI / CompressedBG 互轉器 GUI，單檔運行。

介面跟 BMP-BGI-Converter-GUI：輸入/輸出、自動或指定方向、預覽、日誌。
認得 CompressedBG v1/v2，並可以轉返 CompressedBG v1，避免 raw BGI 太大。
圖像輸出可選帶 Alpha 的 BMP，或 PhotoCraft 開得到的 PNG。
"""
from __future__ import annotations

import os
import struct
import zlib
from typing import Optional, Tuple

class BgiError(ValueError):
    pass


# ---------------------------------------------------------------------------
# BMP <-> raw BGI
# ---------------------------------------------------------------------------

def read_bmp(path: str) -> Tuple[int, int, int, bytes]:
    with open(path, "rb") as f:
        data = f.read()
    return parse_bmp(data, path)


def parse_bmp(data: bytes, label: str = "bmp") -> Tuple[int, int, int, bytes]:
    if len(data) < 54 or data[:2] != b"BM":
        raise BgiError(f"不是 BMP：{label}")
    bf_off = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40 or bf_off > len(data):
        raise BgiError(f"不支援或檔頭損壞：{label} (DIB={dib_size}, off={bf_off})")
    width = struct.unpack_from("<i", data, 18)[0]
    height_signed = struct.unpack_from("<i", data, 22)[0]
    planes, bpp = struct.unpack_from("<HH", data, 26)
    compression = struct.unpack_from("<I", data, 30)[0]
    if width <= 0:
        raise BgiError(f"非法寬度 {width}")
    height = abs(height_signed)
    top_down = height_signed < 0
    if planes != 1:
        raise BgiError(f"不支援 planes={planes}")
    if bpp not in (24, 32):
        raise BgiError(f"只支援 24/32-bit BMP（實際 {bpp}）")
    if compression not in (0, 3, 6):
        raise BgiError(f"不支援壓縮 BMP（compression={compression}）")

    masks = None
    if compression in (3, 6) or dib_size >= 56:
        mask_off = 54
        if mask_off + 16 <= len(data):
            r_m, g_m, b_m, a_m = struct.unpack_from("<IIII", data, mask_off)
            if any((r_m, g_m, b_m)):
                masks = (b_m, g_m, r_m, a_m)

    src_stride = ((width * bpp + 31) // 32) * 4
    end = bf_off + src_stride * height
    if end > len(data):
        raise BgiError(f"像素區被截斷：需要 {end} bytes，檔案只有 {len(data)}")
    raw = data[bf_off:end]
    dst_pp = bpp // 8
    dst_stride = width * dst_pp
    out = bytearray(dst_stride * height)
    standard_bgra = masks in (
        None,
        (0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000),
        (0x000000FF, 0x0000FF00, 0x00FF0000, 0x00000000),
    )
    for y in range(height):
        src_y = y if top_down else (height - 1 - y)
        src = raw[src_y * src_stride : src_y * src_stride + dst_stride]
        dst_off = y * dst_stride
        if standard_bgra or bpp == 24:
            out[dst_off : dst_off + dst_stride] = src
        else:
            b_m, g_m, r_m, a_m = masks
            for x in range(width):
                px = int.from_bytes(src[x * 4 : x * 4 + 4], "little")

                def ch(mask: int, is_a: bool = False) -> int:
                    if mask == 0:
                        return 0xFF if is_a else 0
                    shift = (mask & -mask).bit_length() - 1
                    bits = (mask >> shift).bit_count()
                    val = (px & mask) >> shift
                    if bits >= 8:
                        return (val >> (bits - 8)) & 0xFF
                    return (val * 255) // ((1 << bits) - 1)

                out[dst_off + x * 4 : dst_off + x * 4 + 4] = bytes(
                    (ch(b_m), ch(g_m), ch(r_m), ch(a_m, True) if a_m else 0xFF)
                )
    return width, height, bpp, bytes(out)


def write_bgi(path: str, width: int, height: int, bpp: int, pixels: bytes) -> None:
    if not (0 < width <= 0x7FFF and 0 < height <= 0x7FFF):
        raise BgiError(f"BGI 長寬是 int16，無法寫入 {width}x{height}")
    if bpp not in (24, 32):
        raise BgiError(f"BGI bpp 僅 24/32，收到 {bpp}")
    expected = width * height * (bpp // 8)
    if len(pixels) != expected:
        raise BgiError(f"像素長度 {len(pixels)} != {expected}")
    header = struct.pack("<hhhhii", width, height, bpp, 0, 0, 0)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header)
        f.write(pixels)


def write_bmp_v4(path: str, width: int, height: int, bpp: int, topdown: bytes) -> None:
    if bpp not in (24, 32):
        raise BgiError(f"BMP 匯出僅 24/32，收到 {bpp}")
    row = width * (bpp // 8)
    stride = ((bpp * width + 31) // 32) * 4
    pad = stride - row
    body = bytearray()
    for y in range(height):
        body.extend(topdown[y * row : (y + 1) * row])
        if pad:
            body.extend(b"\x00" * pad)
    dib = 108
    off = 14 + dib
    compression = 3 if bpp == 32 else 0
    file_size = off + len(body)
    buf = bytearray()
    buf += b"BM"
    buf += struct.pack("<IHHI", file_size, 0, 0, off)
    buf += struct.pack(
        "<IiiHHIIiiII",
        dib, width, -height, 1, bpp, compression, len(body), 0, 0, 0, 0,
    )
    if bpp == 32:
        buf += struct.pack("<IIII", 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    else:
        buf += struct.pack("<IIII", 0, 0, 0, 0)
    buf += b"Win "
    buf += b"\x00" * 48
    if len(buf) != off:
        raise RuntimeError(f"internal header {len(buf)} != {off}")
    buf += body
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(buf)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path: str, width: int, height: int, bpp: int, topdown: bytes) -> None:
    """寫 8-bit 非交錯 PNG。32-bit 輸入是 BGRA，24-bit 是 BGR。保留半透明。"""
    if bpp not in (24, 32):
        raise BgiError(f"PNG 匯出僅 24/32，收到 {bpp}")
    src_pp = bpp // 8
    expected = width * height * src_pp
    if len(topdown) < expected:
        raise BgiError(f"PNG 像素不足：{len(topdown)} < {expected}")
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        row = topdown[y * width * src_pp : (y + 1) * width * src_pp]
        if bpp == 32:
            for x in range(width):
                b, g, r, a = row[x * 4 : x * 4 + 4]
                raw.extend((r, g, b, a))
        else:
            for x in range(width):
                b, g, r = row[x * 3 : x * 3 + 3]
                raw.extend((r, g, b))
    color_type = 6 if bpp == 32 else 2
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _png_chunk(b"IEND", b"")
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def parse_png(data: bytes, label: str = "png") -> Tuple[int, int, int, bytes]:
    """讀 8-bit 非交錯 RGB/RGBA PNG，回傳 top-down BGRA。灰階會升成不透明 BGRA。"""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BgiError(f"不是 PNG：{label}")
    pos = 8
    width = height = bit_depth = color_type = interlace = None
    idat = []
    while pos + 12 <= len(data):
        length, tag = struct.unpack_from(">I4s", data, pos)
        pos += 8
        chunk = data[pos : pos + length]
        pos += length + 4
        if tag == b"IHDR":
            if len(chunk) < 13:
                raise BgiError(f"PNG IHDR 損壞：{label}")
            width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
        elif tag == b"IDAT":
            idat.append(chunk)
        elif tag == b"IEND":
            break
    if not width or not height or not idat:
        raise BgiError(f"PNG 缺少影像資料：{label}")
    if interlace:
        raise BgiError(f"不支援交錯 PNG：{label}")
    if bit_depth != 8 or color_type not in (0, 2, 3, 4, 6):
        raise BgiError(f"只支援 8-bit PNG（bit={bit_depth}, color={color_type}）：{label}")
    if color_type == 3:
        raise BgiError(f"不支援索引色 PNG，請先轉 RGBA：{label}")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as e:
        raise BgiError(f"PNG 解壓失敗：{label}") from e
    stride = width * channels
    need = height * (stride + 1)
    if len(raw) < need:
        raise BgiError(f"PNG 像素被截斷：{label}")
    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    i = 0
    for y in range(height):
        filt = raw[i]
        i += 1
        row = bytearray(raw[i : i + stride])
        i += stride
        if filt == 1:
            for x in range(channels, stride):
                row[x] = (row[x] + row[x - channels]) & 0xFF
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 0xFF
        elif filt == 3:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 0xFF
        elif filt == 4:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                up_left = prev[x - channels] if x >= channels else 0
                row[x] = (row[x] + _paeth(left, prev[x], up_left)) & 0xFF
        elif filt != 0:
            raise BgiError(f"不支援 PNG filter {filt}：{label}")
        prev = row
        dst = y * width * 4
        if channels == 4:
            for x in range(width):
                r, g, b, a = row[x * 4 : x * 4 + 4]
                out[dst + x * 4 : dst + x * 4 + 4] = bytes((b, g, r, a))
        elif channels == 3:
            for x in range(width):
                r, g, b = row[x * 3 : x * 3 + 3]
                out[dst + x * 4 : dst + x * 4 + 4] = bytes((b, g, r, 0xFF))
        elif channels == 2:
            for x in range(width):
                g, a = row[x * 2 : x * 2 + 2]
                out[dst + x * 4 : dst + x * 4 + 4] = bytes((g, g, g, a))
        else:
            for x in range(width):
                g = row[x]
                out[dst + x * 4 : dst + x * 4 + 4] = bytes((g, g, g, 0xFF))
    return width, height, 32, bytes(out)


def expand_24_to_32(bgr: bytes) -> bytes:
    out = bytearray(len(bgr) // 3 * 4)
    si = di = 0
    while si < len(bgr):
        out[di : di + 3] = bgr[si : si + 3]
        out[di + 3] = 0xFF
        si += 3
        di += 4
    return bytes(out)


def read_bgi(path: str) -> Tuple[int, int, int, bytes]:
    with open(path, "rb") as f:
        data = f.read()
    return parse_bgi(data, path)


def parse_bgi(data: bytes, label: str = "bgi") -> Tuple[int, int, int, bytes]:
    if len(data) < 16:
        raise BgiError(f"不是 BGI 資源：{label}")
    width, height, bpp, flag = struct.unpack_from("<hhhh", data, 0)
    width, height, bpp = abs(width), abs(height), abs(bpp)
    if flag != 0:
        raise BgiError(f"{label} flag={flag}，可能是壓縮資源，本工具只處理 raw")
    if bpp not in (24, 32):
        raise BgiError(f"{label} bpp={bpp}，本工具只處理 24/32")
    pixels = data[16:]
    expected = width * height * (bpp // 8)
    if len(pixels) < expected:
        raise BgiError(f"{label} 像素不足：{len(pixels)} < {expected}")
    return width, height, bpp, pixels[:expected]


# ---------------------------------------------------------------------------
# CompressedBG
# ---------------------------------------------------------------------------

DCT_TABLE = (
    1.00000000, 1.38703990, 1.30656302, 1.17587554, 1.00000000, 0.78569496, 0.54119611, 0.27589938,
    1.38703990, 1.92387950, 1.81225491, 1.63098633, 1.38703990, 1.08979023, 0.75066054, 0.38268343,
    1.30656302, 1.81225491, 1.70710683, 1.53635550, 1.30656302, 1.02655995, 0.70710677, 0.36047992,
    1.17587554, 1.63098633, 1.53635550, 1.38268340, 1.17587554, 0.92387950, 0.63637930, 0.32442334,
    1.00000000, 1.38703990, 1.30656302, 1.17587554, 1.00000000, 0.78569496, 0.54119611, 0.27589938,
    0.78569496, 1.08979023, 1.02655995, 0.92387950, 0.78569496, 0.61731654, 0.42521504, 0.21677275,
    0.54119611, 0.75066054, 0.70710677, 0.63637930, 0.54119611, 0.42521504, 0.29289323, 0.14931567,
    0.27589938, 0.38268343, 0.36047992, 0.32442334, 0.27589938, 0.21677275, 0.14931567, 0.07612047,
)

BLOCK_FILL = (
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
)


class _Node:
    __slots__ = ("valid", "parent", "weight", "left", "right")

    def __init__(self, valid, weight, parent=False, left=0, right=0):
        self.valid = valid
        self.parent = parent
        self.weight = weight
        self.left = left
        self.right = right


class HuffmanTree:
    def __init__(self, weights, v2: bool = False):
        nodes = [_Node(w != 0, w) for w in weights]
        root_weight = sum(weights) & 0xFFFFFFFF
        while True:
            weight = 0
            child = [-1, -1]
            for i in range(2):
                min_w = 0xFFFFFFFF
                n = 0
                if v2:
                    while n < len(nodes):
                        if nodes[n].valid:
                            min_w = nodes[n].weight
                            child[i] = n
                            n += 1
                            break
                        n += 1
                    n = max(n, i + 1)
                while n < len(nodes):
                    if nodes[n].valid and nodes[n].weight < min_w:
                        min_w = nodes[n].weight
                        child[i] = n
                    n += 1
                if child[i] == -1:
                    continue
                nodes[child[i]].valid = False
                weight = (weight + nodes[child[i]].weight) & 0xFFFFFFFF
            nodes.append(_Node(True, weight, True, child[0], child[1]))
            if weight >= root_weight:
                break
        self.nodes = nodes

    def decode(self, br: "BitReader") -> int:
        idx = len(self.nodes) - 1
        while self.nodes[idx].parent:
            bit = br.get_bits(1)
            if bit < 0:
                raise BgiError("Huffman 串流提早結束")
            idx = self.nodes[idx].left if bit == 0 else self.nodes[idx].right
            if idx < 0:
                raise BgiError("Huffman 節點損壞")
        return idx


class BitReader:
    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.pos = offset
        self.bits = 0
        self.nbits = 0

    def read_byte(self) -> int:
        if self.pos >= len(self.data):
            return -1
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read(self, n: int) -> bytes:
        chunk = self.data[self.pos : self.pos + n]
        self.pos += len(chunk)
        return chunk

    def get_bits(self, count: int) -> int:
        if count == 0:
            return 0
        while self.nbits < count:
            b = self.read_byte()
            if b < 0:
                return -1
            self.bits = ((self.bits << 8) | b) & 0xFFFFFFFFFFFFFFFF
            self.nbits += 8
        self.nbits -= count
        return (self.bits >> self.nbits) & ((1 << count) - 1)

    def align_byte(self) -> None:
        extra = self.nbits & 7
        if extra:
            self.get_bits(extra)


def _read_varint(read_byte) -> int:
    v = 0
    code_length = 0
    while True:
        code = read_byte()
        if code < 0 or code_length >= 32:
            return -1
        v |= (code & 0x7F) << code_length
        code_length += 7
        if (code & 0x80) == 0:
            return v


def _sign_extend(v: int, count: int) -> int:
    if count and (v >> (count - 1)) == 0:
        return ((-1 << count) | v) + 1
    return v


def _update_key(key: int, magic: int) -> Tuple[int, int]:
    v0 = (20021 * (key & 0xFFFF)) & 0xFFFFFFFF
    v1 = (magic | (key >> 16)) & 0xFFFFFFFF
    v1 = (v1 * 20021 + key * 346) & 0xFFFFFFFF
    v1 = (v1 + (v0 >> 16)) & 0xFFFF
    key = ((v1 << 16) + (v0 & 0xFFFF) + 1) & 0xFFFFFFFF
    return key, v1 & 0xFF


def _float_to_short(f: float) -> int:
    a = 0x80 + (int(f) >> 3)
    if a <= 0:
        return 0
    if a <= 0xFF:
        return a
    if a < 0x180:
        return 0xFF
    return 0


def _float_to_byte(f: float) -> int:
    if f >= 255:
        return 255
    if f <= 0:
        return 0
    return int(f)


def _decode_dct(channel: int, data, src: int, dct) -> list:
    d = 1 if channel > 0 else 0
    tmp = [[0.0] * 8 for _ in range(8)]
    for i in range(8):
        if (
            data[src + 8 + i] == 0
            and data[src + 16 + i] == 0
            and data[src + 24 + i] == 0
            and data[src + 32 + i] == 0
            and data[src + 40 + i] == 0
            and data[src + 48 + i] == 0
            and data[src + 56 + i] == 0
        ):
            t = data[src + i] * dct[d][i]
            for r in range(8):
                tmp[r][i] = t
            continue
        v1 = data[src + i] * dct[d][i]
        v2 = data[src + 8 + i] * dct[d][8 + i]
        v3 = data[src + 16 + i] * dct[d][16 + i]
        v4 = data[src + 24 + i] * dct[d][24 + i]
        v5 = data[src + 32 + i] * dct[d][32 + i]
        v6 = data[src + 40 + i] * dct[d][40 + i]
        v7 = data[src + 48 + i] * dct[d][48 + i]
        v8 = data[src + 56 + i] * dct[d][56 + i]
        v10 = v1 + v5
        v11 = v1 - v5
        v12 = v3 + v7
        v13 = (v3 - v7) * 1.414213562 - v12
        v1 = v10 + v12
        v7 = v10 - v12
        v3 = v11 + v13
        v5 = v11 - v13
        v14 = v2 + v8
        v15 = v2 - v8
        v16 = v6 + v4
        v17 = v6 - v4
        v8 = v14 + v16
        v11 = (v14 - v16) * 1.414213562
        v9 = (v17 + v15) * 1.847759065
        v10 = 1.082392200 * v15 - v9
        v13 = -2.613125930 * v17 + v9
        v6 = v13 - v8
        v4 = v11 - v6
        v2 = v10 + v4
        tmp[0][i] = v1 + v8
        tmp[1][i] = v3 + v6
        tmp[2][i] = v5 + v4
        tmp[3][i] = v7 - v2
        tmp[4][i] = v7 + v2
        tmp[5][i] = v5 - v4
        tmp[6][i] = v3 - v6
        tmp[7][i] = v1 - v8
    block = [0] * 64
    dst = 0
    for i in range(8):
        v10 = tmp[i][0] + tmp[i][4]
        v11 = tmp[i][0] - tmp[i][4]
        v12 = tmp[i][2] + tmp[i][6]
        v13 = tmp[i][2] - tmp[i][6]
        v14 = tmp[i][1] + tmp[i][7]
        v15 = tmp[i][1] - tmp[i][7]
        v16 = tmp[i][5] + tmp[i][3]
        v17 = tmp[i][5] - tmp[i][3]
        v13 = 1.414213562 * v13 - v12
        v1 = v10 + v12
        v7 = v10 - v12
        v3 = v11 + v13
        v5 = v11 - v13
        v8 = v14 + v16
        v11 = (v14 - v16) * 1.414213562
        v9 = (v17 + v15) * 1.847759065
        v10 = v9 - v15 * 1.082392200
        v13 = v9 - v17 * 2.613125930
        v6 = v13 - v8
        v4 = v11 - v6
        v2 = v10 - v4
        block[dst] = _float_to_short(v1 + v8); dst += 1
        block[dst] = _float_to_short(v3 + v6); dst += 1
        block[dst] = _float_to_short(v5 + v4); dst += 1
        block[dst] = _float_to_short(v7 + v2); dst += 1
        block[dst] = _float_to_short(v7 - v2); dst += 1
        block[dst] = _float_to_short(v5 - v4); dst += 1
        block[dst] = _float_to_short(v3 - v6); dst += 1
        block[dst] = _float_to_short(v1 - v8); dst += 1
    return block


def _unpack_v1(data: bytes, pos: int, width: int, height: int, bpp: int, key: int, enc_len: int, checksum: int, checkxor: int, inter_len: int) -> bytes:
    enc = bytearray(data[pos : pos + enc_len])
    if len(enc) != enc_len:
        raise BgiError("CompressedBG 加密區被截斷")
    magic = 0
    total = 0
    xx = 0
    for i in range(enc_len):
        key, sub = _update_key(key, magic)
        enc[i] = (enc[i] - sub) & 0xFF
        total = (total + enc[i]) & 0xFF
        xx ^= enc[i]
    if total != checksum or xx != checkxor:
        raise BgiError("CompressedBG 校驗失敗")
    br = BitReader(bytes(enc))
    weights = []
    for _ in range(0x100):
        w = _read_varint(br.read_byte)
        if w < 0:
            raise BgiError("Huffman 權重損壞")
        weights.append(w)
    tree = HuffmanTree(weights, False)
    file_br = BitReader(data, pos + enc_len)
    packed = bytearray(inter_len)
    for i in range(inter_len):
        packed[i] = tree.decode(file_br) & 0xFF
    pixel_size = bpp // 8
    stride = width * pixel_size
    out = bytearray(stride * height)
    dst = 0
    dec_zero = 0
    src = 0
    while dst < len(out):
        code_length = 0
        count = 0
        while True:
            if src >= len(packed):
                dst = len(out)
                break
            code = packed[src]
            src += 1
            count |= (code & 0x7F) << code_length
            code_length += 7
            if (code & 0x80) == 0:
                break
        if dst >= len(out):
            break
        if dst + count > len(out):
            break
        if dec_zero == 0:
            if src + count > len(packed):
                break
            out[dst : dst + count] = packed[src : src + count]
            src += count
        dst += count
        dec_zero ^= 1
    for y in range(height):
        line = y * stride
        for x in range(width):
            pixel = line + x * pixel_size
            for p in range(pixel_size):
                avg = 0
                if x > 0:
                    avg += out[pixel + p - pixel_size]
                if y > 0:
                    avg += out[pixel + p - stride]
                if x > 0 and y > 0:
                    avg //= 2
                if avg:
                    out[pixel + p] = (out[pixel + p] + avg) & 0xFF
    return bytes(out)


def _unpack_block(blob: bytes, offset: int, length: int, tree1: HuffmanTree, tree2: HuffmanTree, bpp: int, width: int, output: bytearray, dst: int, dct) -> None:
    end = min(len(blob), offset + length)
    chunk = blob[offset:end]
    br = BitReader(chunk)
    block_size = _read_varint(br.read_byte)
    if block_size < 0:
        return
    color = [0] * block_size
    acc = 0
    i = 0
    while i < block_size and br.pos < len(chunk):
        count = tree1.decode(br)
        if count:
            v = br.get_bits(count)
            if v < 0:
                break
            acc += _sign_extend(v, count)
        color[i] = acc & 0xFFFF
        if color[i] >= 0x8000:
            color[i] -= 0x10000
        i += 64
    br.align_byte()
    i = 0
    while i < block_size and br.pos < len(chunk):
        index = 1
        while index < 64 and br.pos < len(chunk):
            code = tree2.decode(br)
            if code == 0:
                break
            if code == 0xF:
                index += 0x10
                continue
            index += code & 0xF
            if index >= len(BLOCK_FILL):
                break
            nbits = code >> 4
            v = br.get_bits(nbits)
            if v < 0:
                break
            color[i + BLOCK_FILL[index]] = _sign_extend(v, nbits)
            index += 1
        i += 64
    if bpp == 8:
        src = 0
        block_count = width // 8
        local = dst
        for _b in range(block_count):
            ycc = _decode_dct(0, color, src, dct)
            src += 64
            for j in range(64):
                y = j >> 3
                x = j & 7
                p = (y * width + x) * 4
                val = ycc[j] & 0xFF
                output[local + p] = val
                output[local + p + 1] = val
                output[local + p + 2] = val
            local += 32
        return
    block_count = width // 8
    local = dst
    for bi in range(block_count):
        src = bi * 64
        planes = []
        for channel in range(3):
            planes.append(_decode_dct(channel, color, src, dct))
            src += width * 8
        for j in range(64):
            cy = planes[0][j]
            cb = planes[1][j]
            cr = planes[2][j]
            r = cy + 1.402 * cr - 178.956
            g = cy - 0.34414 * cb - 0.71414 * cr + 135.95984
            b = cy + 1.772 * cb - 226.316
            y = j >> 3
            x = j & 7
            p = (y * width + x) * 4
            output[local + p] = _float_to_byte(b)
            output[local + p + 1] = _float_to_byte(g)
            output[local + p + 2] = _float_to_byte(r)
        local += 32


def _unpack_alpha(blob: bytes, offset: int, width: int, output: bytearray) -> bool:
    if offset < 0 or offset + 4 > len(blob):
        return False
    if struct.unpack_from("<i", blob, offset)[0] != 1:
        return False
    pos = offset + 4
    dst = 3
    ctl = 1 << 1
    while dst < len(output):
        ctl >>= 1
        if ctl == 1:
            if pos >= len(blob):
                return False
            ctl = blob[pos] | 0x100
            pos += 1
        if ctl & 1:
            if pos + 2 > len(blob):
                return False
            v = struct.unpack_from("<H", blob, pos)[0]
            pos += 2
            x = v & 0x3F
            if x > 0x1F:
                x |= -0x40
            y = (v >> 6) & 7
            if y != 0:
                y |= -8
            count = ((v >> 9) & 0x7F) + 3
            src = dst + (x + y * width) * 4
            if src < 0 or src >= dst:
                return False
            for _ in range(count):
                if dst >= len(output) or src >= len(output):
                    return False
                output[dst] = output[src]
                src += 4
                dst += 4
        else:
            if pos >= len(blob) or dst >= len(output):
                return False
            output[dst] = blob[pos]
            pos += 1
            dst += 4
    return True


def decode_cbg(data: bytes, label: str = "cbg") -> Tuple[int, int, int, bytes, dict]:
    if not data.startswith(b"CompressedBG___"):
        raise BgiError(f"{label} 不是 CompressedBG")
    if len(data) < 0x30:
        raise BgiError(f"{label} 檔頭不足")
    width, height = struct.unpack_from("<HH", data, 0x10)
    bpp = struct.unpack_from("<I", data, 0x14)[0]
    inter_len = struct.unpack_from("<I", data, 0x20)[0]
    key = struct.unpack_from("<I", data, 0x24)[0]
    enc_len = struct.unpack_from("<I", data, 0x28)[0]
    checksum, checkxor = data[0x2C], data[0x2D]
    version = struct.unpack_from("<H", data, 0x2E)[0]
    meta = {"version": version, "key": key, "compressed": True}
    if bpp not in (8, 24, 32):
        raise BgiError(f"{label} 不支援 bpp={bpp}")
    if version < 2:
        pixels = _unpack_v1(data, 0x30, width, height, bpp, key, enc_len, checksum, checkxor, inter_len)
        if bpp == 8:
            # gray to 32
            out = bytearray(width * height * 4)
            for i, g in enumerate(pixels):
                out[i * 4 : i * 4 + 4] = bytes((g, g, g, 0xFF))
            return width, height, 32, bytes(out), meta
        if bpp == 24:
            return width, height, 24, pixels, meta
        return width, height, 32, pixels, meta
    if version != 2:
        raise BgiError(f"{label} 不支援 CompressedBG version {version}")
    if enc_len < 0x80:
        raise BgiError(f"{label} EncLength 太短")
    enc = bytearray(data[0x30 : 0x30 + enc_len])
    if len(enc) != enc_len:
        raise BgiError("加密區被截斷")
    magic = 0
    total = 0
    xx = 0
    for i in range(enc_len):
        key, sub = _update_key(key, magic)
        enc[i] = (enc[i] - sub) & 0xFF
        total = (total + enc[i]) & 0xFF
        xx ^= enc[i]
    if total != checksum or xx != checkxor:
        raise BgiError("CompressedBG 校驗失敗（key 或檔案損壞）")
    dct = [[0.0] * 64 for _ in range(2)]
    for i in range(0x80):
        dct[i >> 6][i & 0x3F] = enc[i] * DCT_TABLE[i & 0x3F]
    pos = 0x30 + enc_len
    base = pos
    br = BitReader(data, pos)
    w1 = []
    for _ in range(0x10):
        w = _read_varint(br.read_byte)
        if w < 0:
            raise BgiError("Tree1 權重損壞")
        w1.append(w)
    w2 = []
    for _ in range(0xB0):
        w = _read_varint(br.read_byte)
        if w < 0:
            raise BgiError("Tree2 權重損壞")
        w2.append(w)
    tree1 = HuffmanTree(w1, True)
    tree2 = HuffmanTree(w2, True)
    pad_w = (width + 7) & ~7
    pad_h = (height + 7) & ~7
    y_blocks = pad_h // 8
    input_base = (br.pos + (y_blocks + 1) * 4) - base
    offsets = []
    for _ in range(y_blocks + 1):
        if br.pos + 4 > len(data):
            raise BgiError("偏移表被截斷")
        raw = struct.unpack_from("<i", data, br.pos)[0]
        br.pos += 4
        offsets.append(raw - input_base)
    blob = data[br.pos :]
    output = bytearray(pad_w * pad_h * 4)
    pad_skip = ((pad_w >> 3) + 7) >> 3
    dst = 0
    for i in range(y_blocks):
        block_off = offsets[i] + pad_skip
        next_off = len(blob) if i + 1 == y_blocks else offsets[i + 1]
        if block_off < 0 or next_off < block_off:
            raise BgiError(f"區塊偏移異常 strip {i}: {block_off}..{next_off}")
        _unpack_block(blob, block_off, next_off - block_off, tree1, tree2, bpp, pad_w, output, dst, dct)
        dst += pad_w * 32
    has_alpha = False
    if bpp == 32:
        has_alpha = _unpack_alpha(blob, offsets[y_blocks], pad_w, output)
    # crop padding, default opaque if no alpha
    pp = 4
    out = bytearray(width * height * 4)
    for y in range(height):
        src = y * pad_w * 4
        dst_row = y * width * 4
        out[dst_row : dst_row + width * 4] = output[src : src + width * 4]
    if not has_alpha:
        for i in range(3, len(out), 4):
            out[i] = 0xFF
    meta["alpha"] = has_alpha
    meta["padded"] = (pad_w, pad_h)
    return width, height, 32, bytes(out), meta


# ---------------------------------------------------------------------------
# Sniff + high level convert
# ---------------------------------------------------------------------------

def sniff(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"BM"):
        return "bmp"
    if data.startswith(b"CompressedBG___"):
        return "cbg"
    if len(data) >= 16:
        width, height, bpp, flag = struct.unpack_from("<hhhh", data, 0)
        width, height, bpp = abs(width), abs(height), abs(bpp)
        if flag == 0 and bpp in (24, 32) and 0 < width <= 8192 and 0 < height <= 8192:
            if len(data) >= 16 + width * height * (bpp // 8):
                return "bgi"
    return "unknown"


def load_image(path: str) -> Tuple[int, int, int, bytes, dict]:
    with open(path, "rb") as f:
        data = f.read()
    kind = sniff(data)
    if kind == "png":
        w, h, bpp, pixels = parse_png(data, path)
        return w, h, bpp, pixels, {"format": "PNG", "compressed": False, "alpha": True}
    if kind == "bmp":
        w, h, bpp, pixels = parse_bmp(data, path)
        return w, h, bpp, pixels, {"format": "BMP", "compressed": False}
    if kind == "bgi":
        w, h, bpp, pixels = parse_bgi(data, path)
        return w, h, bpp, pixels, {"format": "BGI raw", "compressed": False}
    if kind == "cbg":
        w, h, bpp, pixels, meta = decode_cbg(data, path)
        meta["format"] = f"CompressedBG v{meta.get('version')}"
        return w, h, bpp, pixels, meta
    raise BgiError(f"認不出格式：{os.path.basename(path)}")


def load_png(path: str) -> Tuple[int, int, int, bytes, dict]:
    with open(path, "rb") as f:
        data = f.read()
    w, h, bpp, pixels = parse_png(data, path)
    return w, h, bpp, pixels, {"format": "PNG", "compressed": False, "alpha": True}


def to_rgba(width: int, height: int, bpp: int, pixels: bytes) -> bytes:
    if bpp == 32 and len(pixels) >= width * height * 4:
        return pixels[: width * height * 4]
    if bpp == 24:
        return expand_24_to_32(pixels[: width * height * 3])
    raise BgiError(f"無法預覽 bpp={bpp}")


# ---------- CompressedBG v1 encode ----------


class _Node:
    __slots__ = ("valid", "parent", "weight", "left", "right")

    def __init__(self, valid, weight, parent=False, left=0, right=0):
        self.valid = valid
        self.parent = parent
        self.weight = weight
        self.left = left
        self.right = right


def _build_tree(weights: List[int]) -> List[_Node]:
    nodes = [_Node(w != 0, w) for w in weights]
    root_weight = sum(weights) & 0xFFFFFFFF
    while True:
        weight = 0
        child = [-1, -1]
        for i in range(2):
            min_w = 0xFFFFFFFF
            n = 0
            while n < len(nodes):
                if nodes[n].valid and nodes[n].weight < min_w:
                    min_w = nodes[n].weight
                    child[i] = n
                n += 1
            if child[i] == -1:
                continue
            nodes[child[i]].valid = False
            weight = (weight + nodes[child[i]].weight) & 0xFFFFFFFF
        nodes.append(_Node(True, weight, True, child[0], child[1]))
        if weight >= root_weight:
            break
    return nodes


def _codes(nodes: List[_Node]) -> List[Tuple[int, int]]:
    codes = [(0, 0)] * 256

    def walk(idx: int, bits: int, length: int) -> None:
        node = nodes[idx]
        if not node.parent:
            if 0 <= idx < 256:
                codes[idx] = (bits, length)
            return
        if node.left >= 0:
            walk(node.left, bits << 1, length + 1)
        if node.right >= 0:
            walk(node.right, (bits << 1) | 1, length + 1)

    if nodes:
        walk(len(nodes) - 1, 0, 0)
    return codes


class _BitWriter:
    def __init__(self):
        self.buf = bytearray()
        self.acc = 0
        self.free = 8

    def write(self, value: int, nbits: int) -> None:
        while nbits > 0:
            take = min(self.free, nbits)
            mask = (1 << take) - 1
            nbits -= take
            self.free -= take
            self.acc |= ((value >> nbits) & mask) << self.free
            if self.free == 0:
                self.buf.append(self.acc)
                self.acc = 0
                self.free = 8

    def flush(self) -> bytes:
        if self.free != 8:
            self.buf.append(self.acc)
            self.acc = 0
            self.free = 8
        return bytes(self.buf)


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            b |= 0x80
        out.append(b)
        if not value:
            return bytes(out)


def _key_stream(n: int, key: int = 0) -> bytes:
    out = bytearray(n)
    for i in range(n):
        v0 = (20021 * (key & 0xFFFF)) & 0xFFFFFFFF
        v1 = key >> 16
        v1 = (v1 * 20021 + key * 346) & 0xFFFFFFFF
        v1 = (v1 + (v0 >> 16)) & 0xFFFF
        key = ((v1 << 16) + (v0 & 0xFFFF) + 1) & 0xFFFFFFFF
        out[i] = v1 & 0xFF
    return bytes(out)


def _average_sample(pixels: bytearray, width: int, height: int) -> None:
    stride = width * 4
    for y in range(height - 1, -1, -1):
        line = y * stride
        for x in range(width - 1, -1, -1):
            pix = line + x * 4
            for p in range(3, -1, -1):
                avg = 0
                if x:
                    avg += pixels[pix + p - 4]
                if y:
                    avg += pixels[pix + p - stride]
                if x and y:
                    avg //= 2
                if avg:
                    pixels[pix + p] = (pixels[pix + p] - avg) & 0xFF


def _rle(pixels: bytes) -> bytes:
    out = bytearray()
    zero_start = -1
    prev_end = 0
    n = len(pixels)
    for i, b in enumerate(pixels):
        if b == 0:
            if zero_start < 0:
                zero_start = i
        else:
            if zero_start >= 0 and i - zero_start > 4:
                out += _varint(zero_start - prev_end)
                out += pixels[prev_end:zero_start]
                out += _varint(i - zero_start)
                prev_end = i
            zero_start = -1
    if zero_start >= 0 and n - zero_start > 4:
        out += _varint(zero_start - prev_end)
        out += pixels[prev_end:zero_start]
        out += _varint(n - zero_start)
    else:
        out += _varint(n - prev_end)
        out += pixels[prev_end:]
    return bytes(out)


def encode_cbg(width: int, height: int, pixels: bytes) -> bytes:
    if not (0 < width <= 0x7FFF and 0 < height <= 0x7FFF):
        raise BgiError(f"尺寸超出 BGI：{width}x{height}")
    expected = width * height * 4
    if len(pixels) < expected:
        raise BgiError("像素不足，要 32-bit BGRA")
    sampled = bytearray(pixels[:expected])
    _average_sample(sampled, width, height)
    packed = _rle(sampled)
    weights = [0] * 256
    for b in packed:
        weights[b] += 1
    codes = _codes(_build_tree(weights))
    writer = _BitWriter()
    for b in packed:
        bits, nbits = codes[b]
        if nbits == 0 and weights[b]:
            bits, nbits = 0, 1
        writer.write(bits, nbits)
    compressed = writer.flush()

    plain = b"".join(_varint(w) for w in weights)
    keys = _key_stream(len(plain))
    enc = bytes((b + k) & 0xFF for b, k in zip(plain, keys))
    checksum = sum(plain) & 0xFF
    checkxor = 0
    for b in plain:
        checkxor ^= b

    header = bytearray(b"CompressedBG___\x00")
    header += struct.pack("<HH", width, height)
    header += struct.pack("<I", 32)
    header += struct.pack("<II", 0, 0)
    header += struct.pack("<I", len(packed))
    header += struct.pack("<I", 0)
    header += struct.pack("<I", len(enc))
    header += struct.pack("<BBH", checksum, checkxor, 1)
    if len(header) != 0x30:
        raise BgiError(f"header {len(header)} != 48")
    return bytes(header) + enc + compressed

# ---------- GUI（單檔，介面跟 BMP-BGI-Converter-GUI） ----------
import sys
import threading
import webbrowser

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False

HELP_TEXT = """
【BGI ↔ BMP / PNG / CompressedBG】單檔即可跑

1. 輸入可以係單個檔或成個資料夾
   • .bmp / .png → BGI raw，或 CompressedBG
   • raw BGI / CompressedBG → BMP、PNG，或再壓成 CompressedBG

2. 輸出留空就自動：
   • 轉 BGI / CompressedBG：去掉副檔名（遊戲檔名）
   • 轉 BMP：加 .bmp；轉 PNG：加 .png
   • 資料夾：輸出到原資料夾

3. 模式
   • 自動：BMP/PNG → BGI raw；BGI / CompressedBG → 下面揀嘅圖像格式
   • BMP/PNG → BGI：未壓縮，最大，引擎一定接受
   • → CompressedBG：壓成 v1。引擎接受 v1，即使原圖係 v2
   • BGI → BMP / PNG：方便 PhotoCraft 改圖

4. 點解要 CompressedBG
   raw 32-bit 好大。1280x720 raw 約 3.6MB，CompressedBG v1 約 2MB。
   v2 可以再細少少，但 v1 已經夠遊戲用。

預覽要 Pillow：pip install pillow
轉檔本身唔使 Pillow。
"""


def sniff_path(path: str) -> str:
    try:
        with open(path, "rb") as f:
            head = f.read(48)
            size = os.path.getsize(path)
    except OSError:
        return "unknown"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"BM"):
        return "bmp"
    if head.startswith(b"CompressedBG___"):
        return "cbg"
    if len(head) >= 16:
        width, height, bpp, flag = struct.unpack_from("<hhhh", head, 0)
        width, height, bpp = abs(width), abs(height), abs(bpp)
        if flag == 0 and bpp in (24, 32) and 0 < width <= 8192 and 0 < height <= 8192:
            if size >= 16 + width * height * (bpp // 8):
                return "bgi"
    return "unknown"


def default_bgi_path(path: str) -> str:
    stem, ext = os.path.splitext(path)
    return stem if ext else path + ".bgi"


def default_image_path(path: str, ext: str) -> str:
    stem, old = os.path.splitext(path)
    base = stem if old else path
    return base + ext


def pil_from_pixels(width, height, bpp, pixels):
    try:
        from PIL import Image
    except ImportError:
        return None
    rgba = to_rgba(width, height, bpp, pixels)
    raw = bytearray(len(rgba))
    raw[0::4] = rgba[2::4]
    raw[1::4] = rgba[1::4]
    raw[2::4] = rgba[0::4]
    raw[3::4] = rgba[3::4]
    return Image.frombytes("RGBA", (width, height), bytes(raw))


class App:
    def __init__(self, root):
        self.root = root
        root.title("BMP / PNG ↔ BGI / CompressedBG")
        root.geometry("1120x760")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="auto")
        self.image_fmt_var = tk.StringVar(value="png")
        self.keep24_var = tk.BooleanVar(value=False)
        self.converting = False
        self.preview_token = 0

        top = ttk.Frame(root, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="輸入 (檔案/資料夾):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.input_var, width=60).grid(row=0, column=1, padx=5, sticky=tk.EW)
        ttk.Button(top, text="選檔案", command=self.browse_file).grid(row=0, column=2, padx=2)
        ttk.Button(top, text="選資料夾", command=self.browse_dir).grid(row=0, column=3, padx=2)
        ttk.Label(top, text="輸出 (可留空自動):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(top, textvariable=self.output_var, width=60).grid(row=1, column=1, padx=5, sticky=tk.EW)
        ttk.Button(top, text="選檔案", command=self.browse_out_file).grid(row=1, column=2, padx=2)
        ttk.Button(top, text="選資料夾", command=self.browse_out_dir).grid(row=1, column=3, padx=2)
        top.columnconfigure(1, weight=1)

        mode_frame = ttk.LabelFrame(root, text="轉換模式", padding=10)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Radiobutton(mode_frame, text="自動 (依檔頭)", variable=self.mode_var, value="auto", command=self.update_preview).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(mode_frame, text="BMP/PNG → BGI raw", variable=self.mode_var, value="to_bgi", command=self.update_preview).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(mode_frame, text="→ CompressedBG", variable=self.mode_var, value="to_cbg", command=self.update_preview).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(mode_frame, text="BGI → BMP", variable=self.mode_var, value="to_bmp", command=self.update_preview).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(mode_frame, text="BGI/BMP → PNG", variable=self.mode_var, value="to_png", command=self.update_preview).pack(side=tk.LEFT, padx=8)
        opt = ttk.Frame(root, padding=(10, 0))
        opt.pack(fill=tk.X)
        ttk.Label(opt, text="自動模式圖像輸出:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(opt, text="PNG（PhotoCraft 可開 Alpha）", variable=self.image_fmt_var, value="png").pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(opt, text="V4 Alpha BMP", variable=self.image_fmt_var, value="bmp").pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(opt, text="保留 24-bit (不補Alpha)", variable=self.keep24_var).pack(side=tk.LEFT, padx=16)
        btn_frame = ttk.Frame(mode_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="HELP", command=self.show_help).pack(side=tk.LEFT, padx=5)
        self.convert_btn = ttk.Button(btn_frame, text="開始轉換", command=self.start_convert)
        self.convert_btn.pack(side=tk.LEFT, padx=5)

        paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        preview_frame = ttk.LabelFrame(paned, text="圖片預覽", padding=10)
        paned.add(preview_frame, weight=1)
        self.preview_label = ttk.Label(preview_frame, text="選擇單個檔案後自動預覽\n支援 BMP / PNG / BGI raw / CompressedBG", anchor=tk.CENTER, justify=tk.CENTER)
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        self.pillow_tip_frame = ttk.Frame(preview_frame)
        self.pillow_tip_frame.pack(fill=tk.X, pady=5)
        self.pillow_tip_var = tk.StringVar(value="")
        ttk.Label(self.pillow_tip_frame, textvariable=self.pillow_tip_var, foreground="orange").pack(side=tk.LEFT)
        self.install_btn = ttk.Button(self.pillow_tip_frame, text="立即安裝 Pillow", command=self.install_pillow)
        self.info_var = tk.StringVar(value="未選擇檔案")
        ttk.Label(preview_frame, textvariable=self.info_var, anchor=tk.W).pack(fill=tk.X, pady=(5, 0))

        log_frame = ttk.LabelFrame(paned, text="轉換日誌", padding=10)
        paned.add(log_frame, weight=1)
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sb = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=sb.set)

        bottom = ttk.Frame(root, padding=5)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="就緒")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(bottom, mode="indeterminate")
        self.progress.pack(side=tk.RIGHT, padx=10, fill=tk.X, expand=True)

        self.input_var.trace_add("write", lambda *_: self.root.after(300, self.update_preview))
        self.root.after(100, self.check_pillow_on_start)

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("All", "*.*"), ("PNG", "*.png"), ("BMP", "*.bmp")])
        if f:
            self.input_var.set(f)

    def browse_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.input_var.set(d)

    def browse_out_file(self):
        f = filedialog.asksaveasfilename()
        if f:
            self.output_var.set(f)

    def browse_out_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.output_var.set(d)

    def show_help(self):
        messagebox.showinfo("HELP", HELP_TEXT)

    def check_pillow_on_start(self):
        try:
            import PIL
            self.pillow_tip_var.set("")
            self.install_btn.pack_forget()
            self.status_var.set(f"就緒 | Pillow {PIL.__version__} 已安裝，支援預覽")
        except ImportError:
            self.pillow_tip_var.set("需要 Pillow 才能預覽，沒有也可用")
            self.install_btn.pack(side=tk.LEFT, padx=10)
            self.status_var.set("就緒 | 未安裝 Pillow，轉檔可用，預覽不可用")

    def install_pillow(self):
        if not messagebox.askyesno("安裝 Pillow", "預覽需要 Pillow。沒有都一樣可以轉檔。\n\n而家安裝？\npython -m pip install Pillow"):
            return
        self.status_var.set("正在安裝 Pillow...")
        self.install_btn.config(state=tk.DISABLED, text="安裝中...")
        self.log("正在安裝 Pillow...")

        def do_install():
            try:
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
                self.root.after(0, lambda: self.on_pillow_installed(True, ""))
            except Exception as e:
                self.root.after(0, lambda: self.on_pillow_installed(False, str(e)))

        threading.Thread(target=do_install, daemon=True).start()

    def on_pillow_installed(self, success, err_msg):
        self.install_btn.config(state=tk.NORMAL, text="立即安裝 Pillow")
        if success:
            self.log("Pillow 安裝成功")
            self.pillow_tip_var.set("Pillow 已安裝")
            self.install_btn.pack_forget()
            self.status_var.set("Pillow 安裝完成，請重新選擇檔案預覽")
            messagebox.showinfo("完成", "Pillow 安裝成功。請重新選擇檔案。")
            self.update_preview()
        else:
            self.log(f"Pillow 安裝失敗: {err_msg}")
            self.status_var.set("Pillow 安裝失敗")
            messagebox.showerror("安裝失敗", f"請手動執行：\npython -m pip install Pillow\n\n{err_msg}\n\n轉檔功能仍可用。")

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def update_preview(self):
        path_str = self.input_var.get().strip()
        self.preview_token += 1
        token = self.preview_token
        if not path_str or not os.path.isfile(path_str):
            self.info_var.set("未選擇單檔或為資料夾")
            self.preview_label.config(image="", text="選擇單個檔案後自動預覽\n支援 BMP / PNG / BGI raw / CompressedBG")
            self.preview_label.image = None
            return
        kind = sniff_path(path_str)
        self.info_var.set(f"讀取中… {kind}")
        self.status_var.set("讀取預覽…")

        def work():
            try:
                w, h, bpp, pixels, meta = load_image(path_str)
                img = pil_from_pixels(w, h, bpp, pixels)
                self.root.after(0, lambda: self._show_preview(token, path_str, w, h, bpp, meta, img, None))
            except Exception as e:
                self.root.after(0, lambda: self._show_preview(token, path_str, 0, 0, 0, {}, None, e))

        threading.Thread(target=work, daemon=True).start()

    def _show_preview(self, token, path_str, w, h, bpp, meta, img, err):
        if token != self.preview_token:
            return
        if err:
            self.info_var.set(f"預覽失敗: {err}")
            self.preview_label.config(image="", text=f"無法預覽\n{err}")
            self.preview_label.image = None
            self.status_var.set("預覽失敗")
            return
        label = meta.get("format", "?")
        self.info_var.set(f"{label} | {w}x{h} | {bpp}bpp | {os.path.getsize(path_str)} bytes")
        self.status_var.set(f"{label} {w}x{h}")
        if img is None:
            self.preview_label.config(image="", text="未安裝 Pillow，無法預覽\n轉檔功能正常可用")
            self.preview_label.image = None
            self.pillow_tip_var.set("需要 Pillow 才能預覽，沒有也可用")
            self.install_btn.pack(side=tk.LEFT, padx=10)
            return
        self.pillow_tip_var.set("")
        self.install_btn.pack_forget()
        try:
            from PIL import Image, ImageTk
            img = img.copy()
            img.thumbnail((420, 420), Image.LANCZOS)
            board = Image.new("RGBA", img.size)
            tile = 12
            px = board.load()
            for y in range(img.size[1]):
                for x in range(img.size[0]):
                    px[x, y] = (214, 206, 196, 255) if ((x // tile) ^ (y // tile)) & 1 else (236, 231, 224, 255)
            board.alpha_composite(img)
            tk_img = ImageTk.PhotoImage(board)
            self.preview_label.config(image=tk_img, text="")
            self.preview_label.image = tk_img
        except Exception as e:
            self.preview_label.config(image="", text=f"預覽失敗: {e}")

    def start_convert(self):
        if self.converting:
            return
        inp = self.input_var.get().strip()
        out = self.output_var.get().strip() or None
        if not inp or not os.path.exists(inp):
            messagebox.showerror("錯誤", "請先選擇有效的輸入檔案或資料夾")
            return
        self.converting = True
        self.convert_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self.status_var.set("轉換中...")
        self.log_text.delete("1.0", tk.END)
        threading.Thread(target=self.convert_worker, args=(inp, out), daemon=True).start()

    def convert_worker(self, inp, out):
        mode = self.mode_var.get()
        keep24 = self.keep24_var.get()
        image_fmt = self.image_fmt_var.get()
        jobs = []
        if os.path.isdir(inp):
            outdir = out or inp
            os.makedirs(outdir, exist_ok=True)
            for name in sorted(os.listdir(inp)):
                path = os.path.join(inp, name)
                if not os.path.isfile(path):
                    continue
                kind = sniff_path(path)
                job = self._job_for(path, outdir, name, kind, mode, image_fmt)
                if job:
                    jobs.append(job)
        else:
            kind = sniff_path(inp)
            job_type = self._single_job(kind, mode, image_fmt)
            if job_type == "to_bgi":
                dest = out or default_bgi_path(inp)
            elif job_type == "to_cbg":
                dest = out or default_bgi_path(inp)
            elif job_type == "to_png":
                dest = out or default_image_path(inp, ".png")
            elif job_type == "to_bmp":
                dest = out or default_image_path(inp, ".bmp")
            else:
                job_type = None
                dest = None
            if job_type:
                jobs.append((inp, dest, job_type))
        if not jobs:
            self.root.after(0, lambda: self.log("沒有符合的檔案"))
            self.root.after(0, self.finish)
            return
        success = fail = 0
        for src, dst, job_type in jobs:
            try:
                w, h, bpp, pixels, meta = load_image(src)
                if job_type == "to_bgi":
                    out_bpp = bpp
                    blob = pixels
                    if bpp == 24 and not keep24:
                        blob = expand_24_to_32(pixels)
                        out_bpp = 32
                    write_bgi(dst, w, h, out_bpp, blob)
                    msg = f"[{meta.get('format', '?')}→BGI] {os.path.basename(src)} → {os.path.basename(dst)} ({w}x{h}, {out_bpp}bpp, {os.path.getsize(dst)} bytes)"
                elif job_type == "to_cbg":
                    rgba = to_rgba(w, h, bpp, pixels)
                    blob = encode_cbg(w, h, rgba)
                    parent = os.path.dirname(os.path.abspath(dst))
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    with open(dst, "wb") as f:
                        f.write(blob)
                    msg = f"[{meta.get('format', '?')}→CBG] {os.path.basename(src)} → {os.path.basename(dst)} ({w}x{h}, {len(rgba)+16} → {len(blob)} bytes)"
                elif job_type == "to_png":
                    rgba = to_rgba(w, h, bpp, pixels)
                    write_png(dst, w, h, 32, rgba)
                    msg = f"[{meta.get('format', '?')}→PNG] {os.path.basename(src)} → {os.path.basename(dst)} ({w}x{h}, 32bpp alpha)"
                else:
                    rgba = to_rgba(w, h, bpp, pixels)
                    write_bmp_v4(dst, w, h, 32, rgba)
                    msg = f"[{meta.get('format', '?')}→BMP] {os.path.basename(src)} → {os.path.basename(dst)} ({w}x{h}, 32bpp)"
                success += 1
                self.root.after(0, lambda m=msg: self.log(m))
            except Exception as e:
                fail += 1
                self.root.after(0, lambda s=src, e=e: self.log(f"[失敗] {os.path.basename(s)} : {e}"))

        def done():
            self.log(f"\n完成 | 成功 {success} | 失敗 {fail}")
            self.status_var.set(f"完成 | 成功 {success} | 失敗 {fail}")
            self.finish()
            folder = out if out and os.path.isdir(out) else (inp if os.path.isdir(inp) else os.path.dirname(jobs[0][1]))
            if success and folder and os.path.isdir(folder):
                if messagebox.askyesno("完成", f"轉換完成 {success} 個檔案\n要打開輸出資料夾嗎？"):
                    try:
                        if os.name == "nt":
                            os.startfile(folder)
                        else:
                            webbrowser.open(folder)
                    except Exception:
                        pass

        self.root.after(0, done)

    def _single_job(self, kind, mode, image_fmt):
        if mode == "to_cbg":
            return "to_cbg" if kind in ("bmp", "png", "bgi", "cbg") else None
        if mode == "to_bgi":
            return "to_bgi" if kind in ("bmp", "png") else None
        if mode == "to_bmp":
            return "to_bmp" if kind in ("bgi", "cbg", "png", "bmp") else None
        if mode == "to_png":
            return "to_png" if kind in ("bgi", "cbg", "bmp", "png") else None
        if kind in ("bmp", "png"):
            return "to_bgi"
        if kind in ("bgi", "cbg"):
            return "to_png" if image_fmt == "png" else "to_bmp"
        return None

    def _job_for(self, path, outdir, name, kind, mode, image_fmt):
        stem = os.path.splitext(name)[0] if os.path.splitext(name)[1] else name
        job = self._single_job(kind, mode, image_fmt)
        if not job:
            return None
        if job == "to_bgi" or job == "to_cbg":
            return path, os.path.join(outdir, stem), job
        if job == "to_png":
            return path, os.path.join(outdir, stem + ".png"), job
        return path, os.path.join(outdir, stem + ".bmp"), job

    def finish(self):
        self.converting = False
        self.convert_btn.config(state=tk.NORMAL)
        self.progress.stop()


def main():
    if not HAS_TK:
        print("錯誤: 找不到 tkinter。Windows 請用 python.org 的安裝版。")
        return 1
    root = tk.Tk()
    try:
        from tkinter import font
        font.nametofont("TkDefaultFont").configure(size=10)
    except Exception:
        pass
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
