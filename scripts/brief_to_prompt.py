#!/usr/bin/env python3
"""
brief → markdown prompt 文件合成器。

输入：session.json 路径 + 输出路径
输出：写入 prompts/<sid>/v<N>.prompt.md，包含 YAML 头（brief 全文）+ 正文（prompt body + Avoid 段）。

Claude 后续可在合成基础上做"AI 动态补充抑制"——脚本本身只做 L1 + L2 的确定性叠加。
L3 动态抑制由 SKILL.md 指示 Claude 编辑 .prompt.md 文件的 Avoid 段补入。
"""
import argparse, json, os, sys, datetime

# 简化的 STYLES 视图（从 gen_assets.py 摘出 prefix + 元数据）。
# 为了避免运行时 import 大文件，这里只放 prefix 表；新增/改风格需同步两处。
STYLES_PREFIX = {
    "01": "Pixel art style, 16-bit retro game aesthetic, thick black pixel outlines, no anti-aliasing, clean pixel art,",
    "02": "8-bit style, classic NES/Game Boy console aesthetic, extremely limited color palette, chunky square pixels, dithering,",
    "03": "Anime illustration style, clean line art, vibrant flat colors, cel-shaded, manga-inspired, expressive characters,",
    "04": "Watercolor painting style, wet-on-wet technique, soft organic edges, translucent washes of color, visible paper texture,",
    "05": "Oil painting style, rich impasto brushwork, textured canvas, deep saturated colors, classical painting technique,",
    "06": "Technical blueprint style, white fine lines on deep blue background, architectural drafting, precise measurements and labels, engineering diagram,",
    "07": "Isometric 3D illustration style, 45-degree angled top-down view, clean geometric shapes, flat shading, game isometric art,",
    "08": "Low poly 3D art style, triangulated geometric facets, flat-shaded polygons, minimal color gradient, abstract geometric,",
    "09": "Neon glow art style, electric neon light tubes, glowing bloom effect on dark background, vivid neon colors, night city aesthetic,",
    "10": "Photorealistic style, ultra-detailed, studio lighting, sharp focus, high-resolution photography, realistic textures,",
    "11": "Cinematic film style, dramatic atmospheric lighting, anamorphic lens flare, moody color grading, cinematic wide shot, film grain,",
    "12": "Abstract expressionist art style, non-representational, bold geometric or organic shapes, emotional color palette, interpretive composition,",
    "13": "Ink drawing style, bold black ink lines, expressive brushwork, high-contrast black and white, pen and ink illustration,",
    "14": "Etching printmaking style, fine crosshatched lines, intaglio texture, aged paper tone, detailed engraved illustration,",
    "15": "Charcoal drawing style, raw textured strokes, smudged shadows, gritty graphite texture, dramatic tonal contrast, artist sketch,",
    "16": "Pastel art style, soft delicate colors, chalky texture, dreamy muted tones, gentle light, soft-focus illustration,",
    "17": "Synthwave retro-futurism style, 1980s neon grid, sunset gradient purple and pink sky, chrome outlines, retrowave aesthetic,",
    "18": "Steampunk art style, Victorian-era mechanical gears and cogs, brass and copper tones, steam pipes, intricate clockwork details,",
    "19": "Cyberpunk art style, dystopian mega-city, neon signs in rain, high-tech low-life aesthetic, holographic displays, dark futuristic,",
    "20": "Ukiyo-e woodblock print style, traditional Japanese art, flat bold outlines, limited color woodblock printing, Edo-period aesthetic,",
    "21": "Minimal line art style, single continuous line drawing, clean white background, ultra-minimal, elegant sparse composition,",
    "22": "Gold foil art style, metallic gold leaf texture, luxurious gilded illustration on dark background, refined ornate details,",
    "23": "Holographic iridescent art style, rainbow prismatic shimmer, chrome holographic foil effect, color-shifting metallic surface,",
    "24": "Technical cutaway illustration style, cross-section diagram, exploded view engineering drawing, labeled internal components, instructional illustration,",
    "25": "Studio Ghibli animation style, hand-painted warm fantasy, lush painterly backgrounds, soft natural lighting, whimsical storybook feel,",
    "26": "Pop art style, bold halftone dots, primary colors, comic book pop aesthetic, Lichtenstein-inspired,",
    "27": "Impressionist painting style, visible brushstrokes, light and color study, plein air, Monet-inspired soft palette,",
    "28": "Surrealist art style, dreamlike juxtaposition, impossible geometries, Dali-inspired, symbolic imagery,",
    "29": "Art Deco style, geometric symmetry, gold and black palette, 1920s elegance, streamlined ornament,",
    "30": "Art Nouveau style, flowing organic curves, floral motifs, Mucha-inspired, decorative ornament,",
    "31": "Vaporwave aesthetic, pastel pink and cyan, glitch artifacts, Greek statues, retro digital nostalgia,",
    "32": "Glitch art style, digital corruption, RGB channel split, datamoshing artifacts, broken pixel sorting,",
    "33": "Graffiti street art style, spray paint texture, urban wall, bold tags and throw-ups, hip-hop visual,",
    "34": "3D render style, physically based rendering, soft global illumination, octane render, glossy materials,",
    "35": "Claymation stop-motion style, handmade clay figures, fingerprint texture, soft studio light,",
    "36": "Paper cut craft style, layered cardstock, sharp clean edges, depth from stacked silhouettes,",
    "37": "Mixed-media collage style, torn paper, magazine cutouts, layered textures, hand-pasted feel,",
    "38": "Pencil sketch style, graphite shading, hatching and crosshatching, sketchbook paper texture,",
    "39": "American comic book style, dynamic action, halftone shading, bold ink outlines, four-color print feel,",
    "40": "Cel-shaded animation style, clean flat colors with hard shadow boundaries, modern anime production,",
    "41": "Voxel art style, 3D cube building blocks, Minecraft-like, blocky volumetric forms,",
    "42": "Gouache painting style, opaque matte colors, illustrator-friendly palette, slight paper grain,",
    "43": "Risograph print style, two-color overlay, slight misregistration, fluorescent ink texture,",
    "44": "Chinese ink wash painting style, sumi-e, expressive minimal strokes, rice paper texture, monochrome tonal depth,",
    "45": "Stained glass window style, lead-lined color panels, jewel-tone backlit feel, gothic geometry,",
    "46": "Woodcut print style, bold black carving, high-contrast relief print, traditional folk-art texture,",
    "47": "Film noir style, high-contrast black and white, harsh shadow, venetian blinds light, 1940s detective mood,",
    "48": "Double exposure photography style, blended silhouettes and landscapes, ethereal layered composition,",
    "49": "Flat design style, geometric simplicity, bold solid colors, no gradients or shadows,",
    "50": "LEGO brick style, plastic studded blocks, clean primary colors, minifig proportions,",
}

DEFAULT_SUPPRESSION = (
    "ugly AI-generated look, plastic skin, deformed hands, extra fingers, "
    "watermark, signature, text artifacts, logo, frame border, "
    "oversaturated banding, jpeg artifacts, low resolution, blurry, "
    "generic stock photo feel"
)

# 风格反义（L2）按 ID 段映射
STYLE_ANTI = {
    "photoreal": ("cartoonish faces, low-poly geometry, flat shading without depth, anime cel-shading", {"10", "11", "47", "48"}),
    "pixel":     ("photoreal noise, smooth anti-aliasing, gradient blur, soft focus", {"01", "02", "41"}),
    "anime":     ("photorealistic skin pores, harsh studio shadows, gritty realism", {"03", "25", "39", "40"}),
    "minimal":   ("dense detail, heavy shading, photoreal textures, complex gradients", {"21", "49"}),
    "painting":  ("digital airbrush smoothness, vector clean edges, neon glow", {"04", "05", "13", "14", "15", "16", "27", "42"}),
    "cyber":     ("dull muted colors, dusty earth tones, hand-drawn imperfection", {"09", "17", "19", "23", "31"}),
    "asian":     ("western perspective realism, photoreal lighting, glossy 3D render", {"20", "44"}),
    "3d":        ("painterly brushstrokes, hand-drawn lines, paper texture", {"07", "08", "34", "35", "50"}),
}


def _style_prefix(style_id):
    if not style_id:
        return ""
    # 支持 "25+18" 之类的复合
    if "+" in style_id:
        parts = [p.strip() for p in style_id.split("+")]
        prefixes = [STYLES_PREFIX.get(p, "").rstrip(",") for p in parts if STYLES_PREFIX.get(p)]
        if not prefixes:
            return ""
        return prefixes[0] + ", with influences of " + " and ".join(prefixes[1:]) + ","
    return STYLES_PREFIX.get(style_id, "")


def _style_anti(style_id):
    if not style_id:
        return ""
    ids = set(style_id.split("+")) if "+" in style_id else {style_id}
    out = []
    for label, (anti, members) in STYLE_ANTI.items():
        if ids & members:
            out.append(anti)
    return ", ".join(out)


# content_sections 的 section 顺序(只输出非空段)。中文标题来自 example.txt。
SECTION_ORDER = [
    ("main_description", "主体描述"),
    ("subject_detail",   "主体细节"),
    ("appearance",       "外貌设定"),
    ("costume",          "服饰道具"),
    ("weapon",           "核心武器"),
    ("pose",             "角色姿态"),
    ("composition",      "画面构图"),
    ("aura",             "气场与能力可视化"),
    ("background",       "背景环境"),
    ("color",            "色彩取向"),
    ("lighting",         "光影与细节"),
    ("text_overlay",     "文字与排版"),
    ("extra",            "其他要求"),
]


def _sectioned_body(sections: dict, style_id: str, brief: dict) -> str:
    """example.txt 风格的中文分节正文 + 末尾英文风格提示锚定 API 风格关键词。"""
    out_lines = []
    for key, label in SECTION_ORDER:
        val = sections.get(key)
        if not val:
            continue
        val = val.strip()
        if not val:
            continue
        out_lines.append(f"{label}:\n{val}\n")
    # 末尾追加英文风格 prefix 作为画风锚定(API 对英文风格关键词更稳)
    prefix = _style_prefix(style_id).rstrip(", ").strip()
    if prefix:
        out_lines.append(f"画面风格(style anchor):\n{prefix}.\n")
    # 受众/用途/情绪做尾部短注
    tail_bits = []
    effect = brief.get("effect") or []
    if isinstance(effect, list) and effect:
        tail_bits.append("情绪: " + "、".join(effect))
    elif isinstance(effect, str) and effect:
        tail_bits.append("情绪: " + effect)
    if brief.get("audience"):
        tail_bits.append("受众: " + brief["audience"])
    if brief.get("use_case"):
        tail_bits.append("用途: " + brief["use_case"])
    if tail_bits:
        out_lines.append("元信息:\n" + " / ".join(tail_bits))
    return "\n".join(out_lines).strip()


def synthesize(brief: dict, *, version: int, session_id: str):
    style_id = brief.get("style_id") or ""
    anti = _style_anti(style_id)
    user_neg_raw = brief.get("suppression")

    # 兼容两种 suppression 存法:字符串 / 列表
    if isinstance(user_neg_raw, list):
        user_neg = ", ".join(s.strip() for s in user_neg_raw if s and str(s).strip())
    else:
        user_neg = (user_neg_raw or "").strip()

    sections = brief.get("content_sections") or {}

    if isinstance(sections, dict) and any((v or "").strip() for v in sections.values() if isinstance(v, str)):
        # 走分节模式(content_sections 主导)
        body = _sectioned_body(sections, style_id, brief)
    else:
        # 兼容旧版:短句 content + style prefix
        prefix = _style_prefix(style_id)
        parts = []
        if prefix:
            parts.append(prefix.rstrip(", "))
        if brief.get("content"):
            parts.append(brief["content"].strip().rstrip("."))
        effect = brief.get("effect") or []
        effect_str = ", ".join(effect) if isinstance(effect, list) else str(effect)
        if effect_str:
            parts.append(f"mood: {effect_str}")
        if brief.get("audience"):
            parts.append(f"resonates with: {brief['audience']}")
        if brief.get("use_case"):
            parts.append(f"intended for: {brief['use_case']}")
        ref = brief.get("reference_image")
        if isinstance(ref, dict) and ref.get("summary"):
            parts.append(f"visual reference (extracted from {ref.get('path','reference')}): {ref['summary']}")
        elif isinstance(ref, str) and ref.strip():
            parts.append(f"visual reference notes: {ref.strip()}")
        body = ", ".join(p for p in parts if p).rstrip(".") + "."

    # 参考图(分节模式也带上)
    ref = brief.get("reference_image")
    if isinstance(sections, dict) and any((v or "").strip() for v in sections.values() if isinstance(v, str)):
        if isinstance(ref, dict) and ref.get("summary"):
            body += f"\n\n参考图视觉特征(来自 {ref.get('path','reference')}):\n{ref['summary']}"
        elif isinstance(ref, str) and ref.strip():
            body += f"\n\n参考图说明:\n{ref.strip()}"

    negatives = [DEFAULT_SUPPRESSION]
    if anti:
        negatives.append(anti)
    if user_neg:
        negatives.append(user_neg)
    avoid = "Avoid / 负面要求: " + ", ".join(negatives) + "."

    full = body + "\n\n" + avoid

    # YAML 头精简成最少必要字段(可读优先)。完整 brief 存在 .gpt-image-gen/sessions/<sid>.json
    yaml_head = (
        "---\n"
        f"session_id: {session_id}\n"
        f"version: {version}\n"
        f"created_at: {datetime.datetime.now().isoformat(timespec='seconds')}\n"
        f"style_id: {style_id or 'none'}\n"
        f"aspect_ratio: {brief.get('aspect_ratio') or '1:1'}\n"
        "ai_dynamic_suppression: \"<TO BE FILLED BY CLAUDE: 2-4 针对性抑制短语>\"\n"
        "# 完整 brief 见: .gpt-image-gen/sessions/" + session_id + ".json\n"
        "# 这是给最终 API 的提示词,可直接编辑下方正文(YAML 头之外的部分)\n"
        "---\n\n"
    )
    return yaml_head + full + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-file", required=True, help="path to .gpt-image-gen/sessions/<id>.json")
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--out", required=True, help="output .prompt.md path")
    args = ap.parse_args()

    with open(args.session_file, "r", encoding="utf-8") as f:
        state = json.load(f)
    md = synthesize(state["brief"], version=args.version, session_id=state["id"])
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)

    # 顶层快捷入口:prompts/latest.prompt.md 始终指向最近一次合成产物
    prompts_root = os.path.dirname(os.path.dirname(os.path.abspath(args.out)))
    latest = os.path.join(prompts_root, "latest.prompt.md")
    try:
        with open(latest, "w", encoding="utf-8") as f:
            f.write(f"<!-- 这是最近一次合成的 prompt(快捷入口),原始文件: {args.out} -->\n")
            f.write(f"<!-- 编辑请直接改原始文件,latest 会被下一次合成覆盖 -->\n\n")
            f.write(md)
    except Exception as e:
        # latest 写失败不阻塞主流程
        pass

    print(json.dumps({
        "ok": True,
        "out": args.out,
        "latest_shortcut": latest,
        "version": args.version,
        "hint": "可直接用任何文本编辑器打开 out 文件修改正文(YAML 头之外的部分)"
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
