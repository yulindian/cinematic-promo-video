# 可见、可编辑的预览看板

用于关键画面与样片关、用户要求在画面上修改时。优先沿用项目引擎原生编辑器；附带启动器和本地留言栏按[看板执行步骤](editor-runtime.md)运行，不为每条视频重新开发一套应用，不依赖huashu的私有运行时或邻近工具内部文件。

## huashu为何会出现看板

根据其公开项目契约和本地Skill说明：`om studio <dir> --no-open`启动本地编辑器。项目`index.html`仍是源文件，CLI提供编辑器界面，Skill负责把视频写成编辑器能识别的结构并启动它。

| 截图能力 | 契约中的实现 |
| --- | --- |
| 右侧参数 | `data-composition-variables`声明变量及类型；`data-var-text`绑定文字，CSS变量绑定配色 |
| 画布点选/改字 | `data-om-id`提供稳定对象ID，`data-om-var`关联脚本构建的文字；Canvas另注册可选区域 |
| 底部场景条与播放头 | 暂停GSAP时间轴注册到`window.__timelines`；`scene:<id>`标签提供场景位置 |
| 保存与撤销 | 修改变量默认值回写源码，版本进入`.om/history`，`om undo`回退 |
| 带位置的留言 | 时间、场景、对象、坐标及变量写入`.om/inbox.jsonl`；Agent读取上下文、改源码、标记完成，界面在原时间点刷新 |
| 导出视频 | 编辑器调用渲染任务；是否成功还要检查实际输出与任务状态 |

“评论后修改”需要Agent执行读取与修改闭环，不能把评论面板说成已经自动接通模型。以上说明来自契约，未据截图推断其前端框架或通信协议；也不把这些属性当成HyperFrames/Remotion通用API。

公开依据：[huashu项目契约](https://github.com/alchaincyf/huashu-motion/blob/main/skills/huashu-motion/references/contract.md)。这是机制参考，不是本Skill运行依赖。

## 两条现有路线

### HyperFrames

依照[HyperFrames执行说明](hyperframes.md)，使用锁定版本的本地`preview`。已核对的0.9.28随包文档支持编辑器预览、项目路由、选择上下文和变量；其他版本先查实际帮助。`play`是轻量播放页面，不能代替编辑看板。

- 文案/色彩/可换媒体用原生变量绑定；时间元素写成可识别HTML并保留稳定ID。不要把全部内容变成运行后才创建、编辑器无法定位的DOM。
- 用实际输出的项目URL（通常带`#project/<name>`），保留其编码与真实端口；只给源HTML路径或通用首页可能进不了项目。
- 对“改我选的这个”可用当前版本的`preview --context --json --context-fields selection`取稳定目标；无选择就请用户点选，不凭空指定对象。
- 分清变量默认值、当前预览覆盖值和渲染覆盖值。预览中改过的值可能还需保存或导出变量配置，渲染时显式使用同一配置。变量不自动改变根片长/fps等项目规格。

命令形状需按已安装CLI核对；用本地入口代替会隐式下载的npx。官方资料：[预览与上下文](https://github.com/heygen-com/hyperframes/blob/main/skills/hyperframes-cli/references/preview-render.md)、[变量](https://github.com/heygen-com/hyperframes/blob/main/docs/concepts/variables.mdx)。

### Remotion

沿用[Remotion执行说明](remotion.md)，用本地Studio和composition props暴露文字、色彩、素材等可改项。较新版本可推断基础控件，需要范围/类型约束时用schema。不得为追赶某个控件擅自迁移已可用的引擎或升级全局环境。

右侧Props预览变化与源码持久化分开验证。保存回代码依赖匹配版本可解析的根文件和`defaultProps`结构，不能只看到参数变化就声称已保存。失败时按官方故障说明修复最小根配置，或明确保存为项目配置并让预览/渲染共用。没有实际接通的画布改字、留言回Agent等功能，不承诺与huashu一致。

官方资料：[可视化编辑](https://www.remotion.dev/docs/visual-editing)、[无法保存默认参数](https://www.remotion.dev/docs/troubleshooting/cannot-save-default-props)。本Skill尚未端到端实测Remotion路线。

## 当前关怎样交付

1. 启动或复用本项目的本地服务，核对项目入口、资源可用和服务存活；端口冲突按项目配置处理。用户已停止视频时跳过启动与渲染，只修改获授权的Skill内容。
2. 在可见浏览器/应用面板打开真正的项目页面，确认画面、时间轴及拟提供的控件出现，再给用户访问地址。仅有后台进程、端口或HTTP 200不能证明界面已交付。没有UI控制能力时提供地址和准确限制，状态记“入口可达，界面未验证”，不声称已替用户打开。
3. 用可回退的小修改验证至少一个实际可改项：修改→保存到明确文件/参数配置→刷新或重启后保留→直接seek同一帧仍生效。回退探测值或保留用户明确采用的值，不覆盖用户既有修改。整片未获授权时以代码检查/关键帧验证渲染配置，不为测编辑器提前导出全片。
4. 简短说明实际可用能力：播放/跳帧、参数改动、画布改字、持久保存、定位评论、撤销、导出；逐项只写已实现或已验证的范围。本Skill留言栏可以保存时间/对象及处理回复，Agent用comments/done命令读取与完成；它不会自行调用模型或唤醒已结束的聊天。缺失的原生点选能力用手动时间/对象记录，不假装原生面板已接通Agent。
5. 复核预览、批准记录和最终渲染使用同一组内容与参数。审阅期间保留服务；用户结束或取消时只停止本项目自启服务。附可复用的启动命令，不把localhost链接当成他人电脑可访问的公开网站。

不新增视频创作审批关：以上属于样片关的可用性交付。文件交付、静态设计或环境受限时按实际目标简化。启动器只补自动打开与本地审阅留言；用户要求完整自建编辑器、多人协作或云端分享时，另行界定应用开发任务和数据归属。
