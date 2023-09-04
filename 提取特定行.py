import os
import codecs

def extract_specific_lines(input_file, output_file):
    with codecs.open(input_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    extracted_lines = []
    for line in lines:
        line = line.strip()
        if len(line) <= 22 and not any(word in line for word in ['『' , '（' ,'─' ,  '！' , '―' , '「', '」', '、', '…', '°' , '。']):
            extracted_lines.append(line)

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write('\n'.join(extracted_lines))

# 指定文件夹路径
folder_path = './jp'

# 遍历文件夹中的所有文件
for filename in os.listdir(folder_path):
    if filename.endswith('.txt'):
        input_file = os.path.join(folder_path, filename)
        output_file = os.path.join(folder_path, f'jp_{filename}')
        
        # 调用函数进行抽取
        extract_specific_lines(input_file, output_file)
