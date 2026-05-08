---
name: gpt-image-gen
description: Generate images using 50 curated art styles via the gpt-image-2 API. Supports --help to list styles and free-form prompt generation with optional --style flag. Saves output locally.
---

# gpt-image-gen — Art Style Image Generator

Generate images using the bundled gpt-image-2 API script across 50 curated art styles.

## Usage

```
/gpt-image-gen --help
/gpt-image-gen [prompt]
/gpt-image-gen --style <id_or_name> [prompt]
/gpt-image-gen --style <id> --out <path> [prompt]
```

## Workflow

When the user invokes `/gpt-image-gen`, follow these steps:

### `--help` mode

Run:
```bash
python3 /home/rison/.codex/skills/gpt-image-gen/scripts/gen_assets.py --help
```
Display the output as-is. It lists all 50 styles with their IDs, English names, and descriptions.

### Generation mode

1. **Parse arguments** from the user's invocation:
   - `--style <id>` — optional, 1–50; defaults to 01 (Pixel Art) if omitted
   - `--out <path>` — optional output file path; defaults to `client/public/assets/generated/<timestamp>_<style>.png`
   - remaining text = the image prompt

2. **Run the generator**:
```bash
python3 /home/rison/.codex/skills/gpt-image-gen/scripts/gen_assets.py \
  --style "<style_id>" \
  --out "<output_path>" \
  --prompt "<user_prompt>"
```

3. **Report** the saved file path and style used. If the API call fails, show the error verbatim.

## Style IDs (quick reference)

| ID | 风格 | Keyword |
|----|------|---------|
| 01 | 像素艺术 | Pixel Art |
| 02 | 8位风 | 8-Bit |
| 03 | 动漫风 | Anime |
| 04 | 水彩 | Watercolor |
| 05 | 油画 | Oil Painting |
| 06 | 蓝图 | Blueprint |
| 07 | 等距视角 | Isometric |
| 08 | 低多边形 | Low Poly |
| 09 | 霓虹光效 | Neon Glow |
| 10 | 写实摄影 | Photoreal |
| 11 | 电影感 | Cinematic |
| 12 | 抽象艺术 | Abstract |
| 13 | 墨线画 | Ink Drawing |
| 14 | 蚀刻版画 | Etching |
| 15 | 炭笔画 | Charcoal |
| 16 | 粉彩/色粉 | Pastel |
| 17 | 合成波 | Synthwave |
| 18 | 蒸汽朋克 | Steampunk |
| 19 | 赛博朋克 | Cyberpunk |
| 20 | 浮世绘 | Ukiyo-e |
| 21 | 极简线条 | Minimal Line |
| 22 | 金箔 | Gold Foil |
| 23 | 全息 | Holographic |
| 24 | 技术剖面图 | Technical Cutaway |
| 25 | 吉卜力风 | Ghibli Style |
| 26 | 波普艺术 | Pop Art |
| 27 | 印象派 | Impressionism |
| 28 | 超现实主义 | Surrealism |
| 29 | 装饰艺术 | Art Deco |
| 30 | 新艺术运动 | Art Nouveau |
| 31 | 蒸汽波 | Vaporwave |
| 32 | 故障艺术 | Glitch Art |
| 33 | 涂鸦/街画 | Graffiti |
| 34 | 3D 渲染 | 3D Render |
| 35 | 黏土/定格 | Claymation |
| 36 | 剪纸风 | Paper Cut |
| 37 | 拼贴画 | Collage |
| 38 | 铅笔素描 | Pencil Sketch |
| 39 | 美漫风 | Comic Book |
| 40 | 赛璐璐上色 | Cel Shading |
| 41 | 体素风 | Voxel |
| 42 | 水粉画 | Gouache |
| 43 | 孔版印刷 | Risograph |
| 44 | 中国水墨 | Chinese Ink Wash |
| 45 | 彩色玻璃 | Stained Glass |
| 46 | 木刻版画 | Woodcut |
| 47 | 黑色电影 | Film Noir |
| 48 | 双重曝光 | Double Exposure |
| 49 | 扁平设计 | Flat Design |
| 50 | 乐高风 | LEGO Style |

## Example session

```
User: /gpt-image-gen --style 19 a cyberpunk alley at night with rain
→ runs: python3 /home/rison/.codex/skills/gpt-image-gen/scripts/gen_assets.py --style 19 --prompt "a cyberpunk alley at night with rain"
→ saves: client/public/assets/generated/20260506_143022_19_cyberpunk.png
→ reports path + style used
```
