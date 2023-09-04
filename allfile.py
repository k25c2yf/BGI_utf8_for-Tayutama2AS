import os

# 指定要處理的資料夾路徑
folder_path = './source'

# 取得資料夾中所有檔案的檔名
file_names = os.listdir(folder_path)

# 將檔案名稱寫入文字檔案
with open('sourcedir1.txt', 'w') as file:
    for name in file_names:
        file.write(name + '\n')
