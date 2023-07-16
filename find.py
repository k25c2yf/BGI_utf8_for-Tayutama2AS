import os

search_string = "」東武海斗」"
folder_path = "./big5"

# 設置文件編碼為utf-16 LE,utf-16-le,Shift-JIS
encoding = "utf-8"

# 遍歷資料夾中的所有檔案
for file_name in os.listdir(folder_path):
    # 確認檔案是否以.txt結尾
#    if file_name.endswith(".txt"):
        # 用utf-16 LE編碼打開檔案
        with open(os.path.join(folder_path, file_name), encoding=encoding,errors='ignore') as f:
            # 遍歷每一行檢查字串是否存在
            for line in f:
                if search_string in line:
                    # 如果存在，則打印檔案名稱並退出遍歷
                    print(file_name)
                    break
