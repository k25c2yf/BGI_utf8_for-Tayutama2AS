import sys

def hex_to_text(hex_string, encoding='ANSI'):
    try:
        byte_string = bytes.fromhex(hex_string)
        return byte_string.decode(encoding)
    except ValueError:
        return "無效的16進制字串。"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("請使用正確的命令行指令：python hextoword.py HEX_STRING")
        sys.exit(1)
    
    hex_string = sys.argv[1]

    # 假設命令行參數中包含了指定的編碼，例如：ANSI="..." 或 UTF8="..."
    if hex_string.startswith("ANSI="):
        hex_string = hex_string[5:]
        encoding = 'ANSI'
    elif hex_string.startswith("UTF8="):
        hex_string = hex_string[5:]
        encoding = 'UTF-8'
    else:
        print("請使用正確的命令行指令：python hextoword.py ANSI=HEX_STRING 或 python hextoword.py UTF8=HEX_STRING")
        sys.exit(1)

    result = hex_to_text(hex_string, encoding)
    print(f"{encoding}=\"{result}\"")
