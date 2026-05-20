# 风格抑制（Negative）规则

gpt-image-2 API 不接受原生 negative prompt 参数。抑制以英文短语形式拼接到主 prompt 末尾的 `Avoid: ...` 段，按经验对模型有显著影响。

抑制由三层叠加构成。**顺序：默认 → 风格反义 → AI 动态补充 → 用户输入**，去重后按英文逗号拼接。

---

## L1 默认全局抑制（无条件加）

```
ugly AI-generated look, plastic skin, deformed hands, extra fingers,
watermark, signature, text artifacts, logo, frame border,
oversaturated banding, jpeg artifacts, low resolution, blurry,
busy cluttered background unless specified, generic stock photo feel
```

## L2 风格反义（按所选风格 ID 自动叠加）

| 风格关键词 / ID 范围 | 反义抑制 |
|---|---|
| 写实摄影 / 电影 (10, 11, 47, 48) | `cartoonish faces, low-poly geometry, flat shading without depth, anime cel-shading` |
| 像素 / 8 位 / 体素 (01, 02, 41) | `photoreal noise, smooth anti-aliasing, gradient blur, soft focus` |
| 动漫 / 吉卜力 / 美漫 (03, 25, 39, 40) | `photorealistic skin pores, harsh studio shadows, gritty realism` |
| 极简线条 / 扁平 (21, 49) | `dense detail, heavy shading, photoreal textures, complex gradients` |
| 油画 / 印象派 / 墨线 (05, 13, 14, 15, 27) | `digital airbrush smoothness, vector clean edges, neon glow` |
| 赛博 / 合成波 / 霓虹 / 全息 (09, 17, 19, 23, 31) | `dull muted colors, dusty earth tones, hand-drawn imperfection` |
| 中国水墨 / 浮世绘 (20, 44) | `western perspective realism, photoreal lighting, glossy 3D render` |
| 3D 渲染 / 等距 / 低多边形 (07, 08, 34, 35, 50) | `painterly brushstrokes, hand-drawn lines, paper texture` |

## L3 AI 动态补充

合成 prompt 时，Claude 必须基于「使用场景 × 目标用户 × 展示效果」组合，**额外生成 2–4 条针对性抑制**。规则：

- 选了「沉稳专业」→ 加 `avoid neon glow, avoid playful cartoon mascots, avoid excessive decoration`
- 选了「高端奢华」→ 加 `avoid plastic textures, avoid low chroma flatness, avoid budget design clichés`
- 选了「活泼亲切」→ 加 `avoid grim atmosphere, avoid harsh contrast, avoid corporate stiffness`
- 选了「神秘有张力」→ 加 `avoid cheerful bright palette, avoid generic stock smile`
- 目标用户是「投资人/决策者」→ 加 `avoid teenage aesthetic, avoid kawaii cuteness`
- 使用场景是「PPT 插图」→ 加 `avoid full-bleed dense composition, avoid illegible small text`
- 使用场景是「社交配图」→ 加 `avoid corporate dryness, avoid editorial newspaper look`

不要照搬上表；按当前 brief **实际矛盾点**生成。

## L4 用户输入抑制

用户在第 6 轴自由文本里写的，原样英文化（必要时翻译成简短英文短语）后拼入。

## 拼接示例

brief：场景=社交配图，用户=普通消费者，效果=活泼亲切，风格=04 水彩，用户抑制="不要太萌"

最终 `Avoid:` 段：

```
Avoid: ugly AI-generated look, plastic skin, deformed hands, extra fingers,
watermark, signature, text artifacts, logo, frame border,
oversaturated banding, jpeg artifacts, low resolution, blurry,
photorealistic skin pores, harsh studio shadows, gritty realism,
grim atmosphere, harsh contrast, corporate stiffness, corporate dryness,
overly cute kawaii face.
```

去重 + 同义合并（如 "blurry" 不和 "soft focus" 同时出现，按所选风格决定取舍）。
