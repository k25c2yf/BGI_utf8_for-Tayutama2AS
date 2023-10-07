import os
import opencc

# 指定繁体转简体的配置文件路径
# 你可以根据需要选择不同的配置文件，比如s2t.json表示繁体转简体
config_file = 't2s'

# 源目录和目标目录
source_dir = './big5'
target_dir = './gbk'

# 创建转换器对象
converter = opencc.OpenCC(config_file)

# 遍历源目录中的所有.txt文件
for filename in os.listdir(source_dir):
    if filename.endswith('.txt'):
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(target_dir, filename)

        # 打开源文件和目标文件
        with open(source_path, 'r', encoding='utf-8') as source_file:
            source_text = source_file.read()
        
        # 使用转换器将繁体文本转换为简体
        simplified_text = converter.convert(source_text)

        # 将简体文本写入目标文件
        with open(target_path, 'w', encoding='utf-8') as target_file:
            target_file.write(simplified_text)

        print(f'转换完成：{source_path} -> {target_path}')

print('全部转换完成！')
