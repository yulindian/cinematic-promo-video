# 可编辑看板示例

独立六秒图形工程，用于检查改字、参数、留言；没有配音、音乐或视频导出，不恢复任何已暂停的影片。

环境：Python 3.10+、Node与HyperFrames 0.9.28兼容；HyperFrames与GSAP版本已固定，依赖只安装在本目录。

在本目录执行：

```sh
npm install --no-audit --no-fund
python ../../scripts/editor.py open . --engine hyperframes
```

左侧Variables改主标题、强调色和标题比例，提交输入后点击Set default保存；刷新验证。右侧填写时间与对象、保存留言。HyperFrames的点选定位需先在画布选中元素；不可选择时可手动标注。

读留言并完成处理：

```sh
python ../../scripts/editor.py comments .
python ../../scripts/editor.py done . NOTE_ID --note "已修改并复核"
python ../../scripts/editor.py stop .
```

核心技能包不包含此示例与node_modules。安装技能不需要安装示例依赖；正式视频工程独立安装其自己的引擎。不要将例子的`.promo-editor`或依赖目录提交到Git。
