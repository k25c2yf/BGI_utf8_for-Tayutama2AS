import sys

def string_to_hex(input_str, encoding):
    encoded_str = input_str.encode(encoding)
    hex_str = encoded_str.hex().upper()
    return hex_str

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python wordtohex.py <input_string>")
        sys.exit(1)

#Shift-JIS  big5 gbk
    input_str = sys.argv[1]
    utf8_hex = string_to_hex(input_str, "utf-8")
    print(f'UTF8="{utf8_hex}"')
    ansi_hex = string_to_hex(input_str, "Shift-JIS")
    print(f'ANSI="{ansi_hex}"')
    
