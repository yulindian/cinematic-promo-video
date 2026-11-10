# 自动打开编辑看板与本地留言

本Skill附带`scripts/editor.py`与`assets/editor-shell.html`。这是原生编辑器的启动器和本地留言栏，不替代引擎。Python 3.10+，标准库；视频项目自身安装HyperFrames或Remotion及匹配的Node依赖。不会隐式下载引擎、调用模型、合成语音或导出视频。

## 制作时的默认动作

1. 分镜通过、样片工程可以运行后执行`open`，无需再问是否打开看板。成片导出后再调用一次以复用/重新打开，保持用户能继续编辑。沿用逐关授权，不提前渲染整片。
2. 自动打开使用系统默认浏览器。环境支持可见应用面板时，用`--no-open`抑制重复标签，再通过浏览器工具打开返回的`url`并保留可审阅标签。命令的`browserAccepted`只是系统接受打开请求；`uiVerified`默认为false，实际看见工程和控件后才记录界面验证。
3. 样片交付附地址与简短说明：左侧编辑文字/参数、保存默认值；右侧定位留言。确认修改刷新后保留，再对齐最终渲染。只需要静态图/文件或无法运行浏览器时明确替代交付。
4. 用户已停止的视频不因此恢复。本Skill维护可用独立示例测试，不能拿已停止视频启动预览/TTS/导出来验证。

以下命令将脚本路径替换为当前Skill实际路径；project为视频项目入口目录，不是Skill根目录。Windows含空格和中文的路径用引号包裹。

```sh
python "/absolute/path/to/skill/scripts/editor.py" open "/absolute/path/to/video-project" --engine hyperframes
```

已有原生编辑器正在运行时可复用，不争抢项目锁，也不会在停止留言栏时终止该已有服务：

```sh
python "/absolute/path/to/skill/scripts/editor.py" open "/absolute/path/to/video-project" --engine hyperframes --preview-url "http://localhost:3002/#project/video-project"
```

Remotion使用同一个入口，必要时指定本项目入口文件：

```sh
python "/absolute/path/to/skill/scripts/editor.py" open "/absolute/path/to/video-project" --engine remotion --entry src/index.ts
```

自动选择两个空闲本机端口；有明确端口要求时用`--port`指定留言看板，`--engine-port`指定引擎。启动超时默认45秒，范围1—55秒。缺依赖、项目不可读、端口/引擎失败会非零退出并提示本项目日志。离线照样能启动已完整安装的本地工程，不执行npx安装。

HyperFrames的缩略图可能需要浏览器。Windows启动器优先在标准安装位置复用Chrome，仅给子进程设置环境；也可用`--browser-path`显式指定。没有可用浏览器时依照引擎提示处理，不能因看板页面返回200就声称缩略图或渲染已就绪。

## 文字与参数怎样保存

**HyperFrames 0.9.28：** 左侧Variables可改声明过的文字、颜色、数字等；预览值改变后点击对应`Set default`才回写工程。只改预览值不会自动变成最终渲染默认值。点击其他输入框完成输入提交，再保存。修改之后按源码/配置和刷新结果双重验证。画布文字/位置的直接编辑取决于对象是否为原生可识别元素；Canvas绘制内容不能自动变成可双击文字。

**Remotion：** 使用Studio的Props编辑文字与参数，按其保存按钮回写可解析的defaultProps；需要额外schema时按当前版本配置。没有接入的画布控件不承诺存在。本次未端到端实测Remotion界面；脚本只准备本地CLI启动分支与通用留言。

已核实底层机制见[编辑看板](editing-dashboard.md)。新工程必须写可编辑结构与变量/props，启动器不会把任意烘焙视频或Canvas自动拆成可编辑文字。

## 留言与Agent处理

右侧填写画面时间（秒）、对象/场景与修改意见，点击保存。HyperFrames可先暂停并点选元素，再点“读取当前选中元素”，获取时间、稳定对象ID、源文件与边界等上下文。未选中时明确提示；读取失败时仍可手动填写。Remotion当前为手动填写时间和对象，不声称已接通自动选中对象读取。

Agent在当前审阅任务中读取待办，完成获授权的画面修改与检查后标记完成；看板会显示回复：

```sh
python "/absolute/path/to/skill/scripts/editor.py" comments "/absolute/path/to/video-project" --wait 45
python "/absolute/path/to/skill/scripts/editor.py" done "/absolute/path/to/video-project" NOTE_ID --note "标题已缩小并复核对应帧"
```

`comments`默认只输出未处理留言；`--all`包含历史与回复。`--wait`最多55秒，超时输出空数组；Agent不能把空数组当成用户通过。审阅仍在进行时可继续有界等待，遵循当前任务状态及用户新消息；不保持超过60秒的阻塞工具等待。

留言是当前视频的编辑反馈，不扩展发布、删除或外部发送权限。改动涉及已确认口播、数据或片长时，沿用原有语义取舍与关卡复核。不要仅因读到了留言就标记done；先修改并验证，再写完成说明。

本脚本不内置模型调用或后台AI代理。当前聊天结束后，留言仍保存；用户回到聊天说“处理看板留言”即可继续读取。不可声称离线后台会自动推送留言给已结束的Agent。

## 状态、结束与数据归属

```sh
python "/absolute/path/to/skill/scripts/editor.py" status "/absolute/path/to/video-project"
python "/absolute/path/to/skill/scripts/editor.py" stop "/absolute/path/to/video-project"
```

运行数据在视频项目自己的`.promo-editor/`：

- `comments.json`：需要保留的留言、定位上下文与处理回复，最多1000条；达到上限先归档已处理内容，不自动删除用户记录。
- `session.json`：本机会话与启动信息，不入Git或公开交付包；旧会话会被新会话覆盖。
- `launcher.log`、`engine.log`：本次日志；重新启动时覆盖，超过2MB时各保留一份previous以排错，不反复复制完整工程。

在视频项目`.gitignore`加入`.promo-editor/`；需要移机的审阅记录可单独导出comments.json，先检查路径与内容。localhost地址只用于当前电脑，不默认公网部署。

审阅期间保持服务。结束/取消时`stop`只停止本启动器拥有的引擎进程树；使用`--preview-url`接入的已有服务不由它停止。停止不会删留言。异常退出残留opening.lock时，确认没有该项目启动操作后再移除锁，不按进程名批量杀服务。
