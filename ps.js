// 1. 讀取所有文字圖層內容
var textLayers = [];
var doc = app.activeDocument;

function getTextLayers(layerSet) {
    for (var i = 0; i < layerSet.layers.length; i++) {
        var layer = layerSet.layers[i];
        if (layer.typename == "ArtLayer" && layer.kind == LayerKind.TEXT) {
            textLayers.push(layer);
        } else if (layer.typename == "LayerSet") {
            getTextLayers(layer);
        }
    }
}
getTextLayers(doc);

// 2. 把文字內容輸出到TXT文件中（UTF-8編碼）
var outputFile = File.saveDialog("保存文本到…");
outputFile.encoding = "UTF-8";
outputFile.open("w");
for (var i = 0; i < textLayers.length; i++) {
    outputFile.writeln(textLayers[i].textItem.contents);
}
outputFile.close();

// 3. 等待手動轉換TXT文件中的文字
alert("請轉換TXT文件中的文字，轉換完成後再次執行腳本");

// 接下來的部分應該在您完成手動轉換後再次執行腳本時執行

// 4. 讀取UTF-8編碼的TXT文件
var inputFile = File.openDialog("選擇已轉換的UTF-8編碼TXT文件");
inputFile.encoding = "UTF-8";
inputFile.open("r");
var lines = [];
while (!inputFile.eof) {
    lines.push(inputFile.readln());
}
inputFile.close();

// 5. 將轉換後的文字回填到Photoshop的相應文字框中
for (var i = 0; i < textLayers.length && i < lines.length; i++) {
    textLayers[i].textItem.contents = lines[i];
}
