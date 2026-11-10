# HyperFrames：HTML / GSAP 路线

适合已有HTML/CSS/GSAP短片迁移。依据2026-11-10官方资料及本机HyperFrames 0.9.28实测。先查安装版本、帮助和官方原生模板，不将单次验证推广为所有版本均兼容。

已有工程读取package.json与锁文件；新工程从官方结构开始。有网络且确实需要初始化新项目时可运行：

```sh
npx hyperframes init my-video
```

进入已安装依赖的工程目录后，以下本地命令不会通过npx补装工具；先确认对应文件存在，不存在就报告依赖缺失。也可沿用package.json中已有的本地脚本：

```sh
node node_modules/hyperframes/bin/hyperframes.mjs preview
node node_modules/hyperframes/bin/hyperframes.mjs render -o outputs/final.mp4
```

若工程位于工具的project/子目录，按项目README把输出改为../outputs/。离线时不要执行初始化或依赖安装。

初始化可能安装技能，查看当前帮助中的只初始化选项，避免覆盖自定义技能。本技能不要求自动安装其他技能。当前官方契约还提供check与snapshot检查路径，其具体参数按锁定版本核对。

## 必要映射

- 根声明尺寸、fps、片长；镜头按原生子composition组织，timed clip的起点/持续秒数从共享帧表换算。
- 每个composition注册暂停的GSAP时间轴；根、模板和静态片段结构按当前原生契约制作。
- 引擎控制片段生存期，动画子层控制透明度和位移，不能争抢clip显隐。
- Canvas接入可seek帧接口或纯时间代理，不用requestAnimationFrame累计状态；先用3—6秒片段验证接入。
- 有稳定ID的音频元素明确范围，混合母带仅声明一次，媒体播放交给引擎。
- 可编辑文案/素材用原生HTML与变量暴露，不把所有timed元素隐藏在运行后创建的DOM中。

素材、字体、CSS排版思路、GSAP参数与粒子算法可保留；动态场景、OM接口、om.js与旧音轨管理需改造。短片段检查字体、直接seek、倒退和所需音轨；目标是视频文件时再验证编码输出，用户只要交互预览时不强制额外编码。随后扩展整片。

## 编辑预览交付

`preview`用于编辑器，轻量`play`只有播放界面；按锁定版本核对命令及项目URL。启动后实际打开可见项目页面并说明可改项，不只交端口或源码路径。变量默认值、预览覆盖值、渲染覆盖值要统一；点选上下文、保存和反馈能力按[编辑看板指南](editing-dashboard.md)验证，不把huashu的OM属性直接移植进来。

## 官方资料

- 仓库：https://github.com/heygen-com/hyperframes
- CLI：https://github.com/heygen-com/hyperframes/blob/main/packages/cli/README.md
- 契约：https://github.com/heygen-com/hyperframes/blob/main/skills/hyperframes/SKILL.md
- 帧适配器：https://github.com/heygen-com/hyperframes/blob/main/packages/core/README.md
- 文档：https://hyperframes.heygen.com/introduction

该项目当前Apache-2.0许可不改变摄影、音乐、字体等独立素材的许可；本地制作不等同于必须订阅其在线生成服务。

## 本机迁移实测：深圳APEC v6

2026-11-10，Windows、Node 24.15、HyperFrames 0.9.28、Chrome 156，已完成6秒带声音验证片和45秒完整原生渲染：1920×1080、30fps、1350帧、16个子composition，一条母带音轨。未调用huashu-motion。

- Windows系统Chrome的BeginFrame能力探测出现回退；本工程验证截图路径可用，使用`PRODUCER_FORCE_SCREENSHOT=true`避免反复探测。仅在相同问题和环境中采用，不强制其他系统使用。
- 渲染临时目录必须在工程外；放在工程内会让区间渲染复制工程到自身子目录，直接失败。工程缓存和配置可分别用`HYPERFRAMES_CACHE_DIR`、`HYPERFRAMES_CONFIG_DIR`指定。
- 对设置`immediateRender:false`的延后入场文字，CSS默认opacity为0，避免日期/主题在动画开始前就可见。
- 叠化只延长照片层生存期，旧标题/署名文字在原切点结束，避免叠字和布局遮挡报告。
- 原生lint、runtime、layout及针对页眉/高潮小字的对比度复核通过；最终文件规格、字幕、响度、帧候选异常和ZIP检查通过。编码音轨与母带相关系数约0.9996。
- 并发渲染时启动浏览器检查会资源争用，可能耗尽检查预算；先导出再独立复核，不把超时报表当作布局失败。

这项记录只证明此HTML/GSAP/Canvas/音频组合已在上述环境跑通；Remotion迁移仍未实测。
