import os
import codecs

def convert_directory(directory):
    # 檢查目錄是否存在
    if not os.path.isdir(directory):
        print(f"目錄 '{directory}' 不存在。")
        return

    # 取得目錄下所有的*.txt文件
    file_list = []
    for file in os.listdir(directory):
        if file.endswith(".txt"):
            file_list.append(file)

    if len(file_list) == 0:
        print(f"目錄 '{directory}' 中沒有符合條件的*.txt文件。")
        return

    # 對每個文件進行轉換
    for file in file_list:
        file_path = os.path.join(directory, file)
        convert_file(file_path)

    print("轉換完成。")

def convert_file(file_path):
    # 讀取原始文件
    with codecs.open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # 將半角英文字轉換為全角英文字
    converted_content = content.encode("utf-8").decode("utf-8").translate(str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"))

    # 寫入轉換後的文件
    with codecs.open(file_path, "w", encoding="utf-8") as file:
        file.write(converted_content)

# 執行轉換
convert_directory("./big5")  # 將 "目錄的路徑" 替換為實際的目錄路徑
