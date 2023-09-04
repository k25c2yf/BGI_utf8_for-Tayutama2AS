import os

directory = './'  # 設定目錄路徑

for filename in os.listdir(directory):
    if filename.endswith("temp.txt"):
        file_path = os.path.join(directory, filename)
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        content = content.replace('"', "」")
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)