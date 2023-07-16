import os

# 输入目录和输出目录
input_directory = './TXT'
output_directory = './temp'

# 确保输出目录存在
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# 遍历输入目录中的所有文件
for filename in os.listdir(input_directory):
    if filename.endswith('.txt'):
        input_file = os.path.join(input_directory, filename)
        output_file = os.path.join(output_directory, filename)

        with open(input_file, 'r', encoding='utf-8') as file_in, \
                open(output_file, 'w', encoding='utf-8') as file_out:
            for line in file_in:
                # 检查行中是否包含特定字词
                if 'Ｈｅｌｌｏ，ｇｏｏｄ−ｂｙｅ：' not in line:
                    file_out.write(line)
