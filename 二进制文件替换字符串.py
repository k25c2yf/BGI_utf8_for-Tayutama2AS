def replace_string_in_binary_file(file_path, search_string, replace_string):
    with open(file_path, "rb") as file:
        data = file.read()

    search_string = search_string.encode("shift_jis")  # 将中文字符串转换为日文编码
    replace_string = replace_string.encode("shift_jis")  # 将中文字符串转换为日文编码

    if len(replace_string) < len(search_string):
        replace_string += b"\x00" * (len(search_string) - len(replace_string))

    updated_data = data.replace(search_string, replace_string)

    with open(file_path, "wb") as file:
        file.write(updated_data)

# 示例用法
file_path = "LOG._bp"  # 二进制文件路径
search_string = "俺はふと、俺を兄さんと呼んだ少女のことを思い出した。"  # 要替换的中文字符串
replace_string = "我突然間想起了那個稱呼我為「哥哥」的少女。"  # 要替换的日文字符串

replace_string_in_binary_file(file_path, search_string, replace_string)
