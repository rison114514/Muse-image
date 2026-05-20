# Muse-image

> 发掘用户想象的对话式文生图工具。

## 这是什么

**Muse-image** 是一个 Claude Code skill。当你说"想画一个 xxx"，它不会接着问你"你想要什么风格 / 什么颜色 / 什么构图"——它会**扮演一位艺术家**，直接替你扩写出一份完整的画面方案：主体、外貌、姿态、气场、构图、背景、光影……每一段都是 100–200 字的、有画面感的具体描述。

然后它一段一段问你：

- ✅ 就这样，继续
- ✏️ 微调当前方向（你补一句修改意见，它重写）
- 🎨 换方向 A：**xxx**（AI 现编的另一种构思）
- 🎨 换方向 B：**xxx**（AI 现编的又一种构思）

当你没灵感时，它替你想方向；当你有想法时，你随时可以补一句改它。最终输出一份 example.txt 级密度的 prompt 文件。

## 核心思路

不是"AI 帮你画图"，而是"AI 帮你把心里那张图说清楚"。

传统文生图工具问你"想要什么"——你回答"嗯……不知道，就有意境一点的"。Muse-image 反过来：**它先给你看一个具体的画面**，让你做主编。你不需要从零想象，你只需要点头、摇头、或精准指出"把咖啡杯改成抹茶碗"。

## 功能

- 📐 **8 轴 brief 收集**：用途 / 受众 / 内容 / 效果 / 风格 / 抑制 / 参考图 / 比例
- 🎨 **艺术家扩写**（§3.3 核心）：一次性生成 4–7 段详细描述，每段轮询
- 💡 **备选方向启发**：每段过审时 AI 额外给 2 个差异化方向标题，没灵感时直接选
- 🛡️ **三级负面词**：L1 默认 + L2 风格反义 + L3 AI 基于本次 brief 现编
- 🖼️ **双模式输出**：
  - 直连 gpt-image API 出图
  - 仅导出 prompt 文件，拿去 Midjourney / SD / 其他平台使用
- 🔄 **多轮微调**：基于反馈重提任意 brief 轴，版本化保存

## 安装与使用

1. 复制本仓库到 `~/.claude/skills/gpt-image-gen/`（注意 skill 内部 slug 仍为 `gpt-image-gen`，Muse-image 是项目品牌名）
2. 复制 `.env.example` 为 `config.env`，填入你的 API key 和 base URL（任何 gpt-image-2 兼容端点均可）
3. 在 Claude Code 中输入 `/gpt-image-gen` 启动

只想要 prompt 不想出图？dry-run 阶段选 **📝 只要 prompt** 即可。

## 文件布局

```
prompts/<sid>/v<N>.prompt.md   # 每个版本的提示词
prompts/<sid>/final.prompt.md  # 接受后的最终版
prompts/latest.prompt.md       # 顶层快捷副本（每次合成覆盖）
outputs/<sid>/v<N>.png         # 各版本图像
outputs/<sid>/final.png        # 接受后的最终图（prompt-only 模式不生成）
.gpt-image-gen/sessions/*.json # 会话状态
```

## License

MIT
