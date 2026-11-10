# Remotion：React / 帧驱动路线

适合React工程、镜头组件和参数化批量制作。依据2026-11-10官方资料；不表示本地已完成迁移。锁定remotion与各@remotion包版本，按匹配文档实施。

| 制作数据 | 实现 |
| --- | --- |
| 尺寸、fps、总帧数 | Composition注册配置 |
| 起点与持续帧 | Sequence的from/durationInFrames |
| 文案、色彩、署名、素材 | composition props，按需加编辑schema |
| 推拉和透明度 | useCurrentFrame、interpolate等帧函数 |
| 原GSAP DOM动画 | 可选@remotion/gsap的useGsapTimeline |
| Canvas粒子 | 当前帧计算时间，完整重绘当前状态 |
| 音轨 | 原生音频组件或一条混合母带 |

Sequence内帧通常为局部帧，先明确字幕与效果用局部还是全局时间。共享帧表作为单一来源。

## GSAP与Canvas的差别

官方GSAP hook已同步暂停时间轴与当前帧。将DOM/SVG动画附到hook提供的timeline，不手动播放或seek，不依赖回调更新状态。

旧Canvas对象代理不能直接套入hook；粒子与光斑改为由frame/fps计算并在帧切换时重绘。图片与字体就绪前不释放渲染。不要让正放、倒退、并行渲染依赖不同的累计粒子状态。

## 预览与输出

已有工程沿用入口与package.json已有脚本；新工程用官方脚手架并锁依赖。离线先确认本地CLI存在，不用npx补装。Windows PowerShell本地命令形状如下，入口与ID按项目修改：

```sh
.\node_modules\.bin\remotion.cmd studio
.\node_modules\.bin\remotion.cmd still src/index.ts Promo outputs/keyframe.png --frame=90
.\node_modules\.bin\remotion.cmd render src/index.ts Promo outputs/final.mp4
```

macOS/Linux使用./node_modules/.bin/remotion；若项目在工具的project/目录内，按README把产物写到../outputs/，临时静帧可放../.tmp/。本地CLI不存在时，离线任务说明该缺项并完成可做的配置工作，不偷偷下载。

用户只要预览时交付预览；用户要成片、导出或MP4时完成最终文件。浏览器与编码成片分别检查。

Studio不是只启动后台进程：在样片关打开可见项目入口，给出地址与当前可改项。Props控件预览和保存回源码分别验证；defaultProps不可被静态解析时，按匹配版本的官方说明修复或保存到显式项目配置。逐项能力与步骤见[编辑看板](editing-dashboard.md)，不默认承诺huashu式画布改字/评论闭环。

## 官方资料

- 理念：https://www.remotion.dev/docs/idea
- 镜头：https://www.remotion.dev/docs/sequence
- GSAP：https://www.remotion.dev/docs/gsap
- hook规则：https://www.remotion.dev/docs/gsap/use-gsap-timeline
- 静帧：https://www.remotion.dev/docs/cli/still
- 导出：https://www.remotion.dev/docs/cli/render
- 许可：https://www.remotion.dev/license

商业部署核对当时适用许可，不将其说成与HyperFrames相同的Apache-2.0许可，也不预设购买或云部署。
