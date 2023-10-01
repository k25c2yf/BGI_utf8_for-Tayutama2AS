import os
import opencc

# 設定轉換器
converter = opencc.OpenCC('t2s')  # 繁體中文轉簡體中文

# 設定原始資料夾和目標資料夾路徑
src_dir = './big5'
dst_dir = './gbk'

# 檢查目標資料夾是否存在，如果不存在則建立目標資料夾
if not os.path.exists(dst_dir):
    os.makedirs(dst_dir)

# 處理所有的*.txt檔案
for file_name in os.listdir(src_dir):
    if file_name.endswith('.txt'):
        # 讀取原始檔案內容
        src_path = os.path.join(src_dir, file_name)
        with open(src_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 執行繁簡轉換
        content = converter.convert(content)

        # 寫入轉換後的檔案到目標資料夾
        dst_path = os.path.join(dst_dir, file_name)
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write(content)
