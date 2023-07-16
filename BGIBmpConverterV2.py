import os
import struct
import sys

def main(args):
    if len(args) != 1:
        print("Usage: SysgrpConverter.py <directory>")
        return

    directory = args[0]
    for filename in os.listdir(directory):
        str_filename = os.path.join(directory, filename)
        if os.path.splitext(str_filename)[1] == '':
            begin_build_bmp(str_filename)
        elif os.path.splitext(str_filename)[1].lower() == '.bmp':
            begin_build_resource(str_filename)
        else:
            print(f"ERROR: {str_filename}")

def begin_build_resource(str_bmp_file):
    with open(str_bmp_file, 'rb') as br:
        br.seek(0x12)
        width = struct.unpack('<i', br.read(4))[0]
        height = struct.unpack('<i', br.read(4))[0]
        br.seek(0x1C)
        depth = struct.unpack('<h', br.read(2))[0]

        br.seek(0x36)
        bits = br.read(width * abs(height) * (depth // 8))

    with open(str_bmp_file + ".out", 'wb') as bw:
        bw.write(struct.pack('<h', width))
        bw.write(struct.pack('<h', abs(height)))
        bw.write(struct.pack('<h', depth))
        bw.write(struct.pack('<h', 0))
        bw.write(struct.pack('<i', 0))
        bw.write(struct.pack('<i', 0))
        bw.write(bits)

def begin_build_bmp(str_filename):
    with open(str_filename, 'rb') as br:
        width = struct.unpack('<h', br.read(2))[0]
        height = struct.unpack('<h', br.read(2))[0]
        depth = struct.unpack('<h', br.read(2))[0]

        br.seek(0x10)
        bits = br.read()

    with open(str_filename + ".bmp", 'wb') as bw:
        bw.write(build_bmp(bits, width, -height, depth))

def build_bmp(bits, width, height, depth):
    ms = bytearray()

    # magic
    ms.extend([0x42, 0x4D])
    # filesz
    ms.extend(struct.pack('<i', len(bits) + 0x36))
    # creator1 + creator2
    ms.extend(struct.pack('<i', 0))
    # bmp_offset
    ms.extend(struct.pack('<i', 0x36))

    # header_sz
    ms.extend(struct.pack('<i', 0x28))
    # width
    ms.extend(struct.pack('<i', width))
    # height
    ms.extend(struct.pack('<i', height))
    # nplanes
    ms.extend(struct.pack('<h', 1))
    # bitspp
    ms.extend(struct.pack('<h', depth))
    # set other info to 0
    ms.extend([0]*24)
    # write bits
    ms.extend(bits)

    return bytes(ms)

if __name__ == "__main__":
    main(sys.argv[1:])
