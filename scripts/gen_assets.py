#!/usr/bin/env python3
"""
muse-image — AI 图像生成器
用法:
  python3 scripts/gen_assets.py --help
  python3 scripts/gen_assets.py --batch                          # 生成全部预设素材
  python3 scripts/gen_assets.py --style 01 --prompt "a rabbit"  # 按风格自由生成
  python3 scripts/gen_assets.py --style 19 --out out.png --prompt "cyberpunk alley"
"""
import os, sys, time, argparse, datetime, requests

_DEFAULT_BASE_URL = "https://your-provider.example.com/gpt-image/v1"
API_KEY  = None   # loaded by load_config() at startup
BASE_URL = _DEFAULT_BASE_URL

def find_project_root():
    env_root = os.environ.get("GPT_IMAGE_GEN_PROJECT_ROOT") or os.environ.get("CODEX_PROJECT_ROOT")
    candidates = []
    if env_root:
        candidates.append(os.path.abspath(env_root))

    cwd = os.path.abspath(os.getcwd())
    probe = cwd
    while True:
        candidates.append(probe)
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent

    script_dir = os.path.dirname(os.path.abspath(__file__))
    probe = script_dir
    while True:
        candidates.append(probe)
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent

    seen = set()
    for root in candidates:
        if root in seen:
            continue
        seen.add(root)
        if os.path.exists(os.path.join(root, "shared", "cards", "abilityCards.json")) and os.path.isdir(os.path.join(root, "client", "public", "assets")):
            return root

    return cwd

PROJ_ROOT = find_project_root()

AUTH_HDR = {}  # populated by load_config()
JSON_HDR = {}  # populated by load_config()


# ── 配置加载 ──────────────────────────────────────────────────────────────────

def _read_env_file(path):
    """Parse a key=value config file, ignore blank lines and # comments."""
    result = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return result


def load_config(api_key_arg=None, base_url_arg=None):
    """
    Load API credentials with priority (high → low):
      1. CLI args  (--api-key / --base-url)
      2. Env vars  (GPT_IMAGE_API_KEY / GPT_IMAGE_BASE_URL)
      3. Config files:
           a. <repo_root>/config.env          (project-local)
           b. ~/.config/muse-image/config.env  (user-global)
    Run `python3 setup.py` to create a config file interactively.
    """
    global API_KEY, BASE_URL, AUTH_HDR, JSON_HDR

    api_key  = None
    base_url = _DEFAULT_BASE_URL

    # 3. Config files (lowest priority — checked first so higher sources can override)
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    config_paths = [
        os.path.join(script_dir, "..", "config.env"),
        os.path.expanduser("~/.config/muse-image/config.env"),
    ]
    for p in config_paths:
        cfg = _read_env_file(p)
        if cfg.get("GPT_IMAGE_API_KEY"):
            api_key = cfg["GPT_IMAGE_API_KEY"]
        if cfg.get("GPT_IMAGE_BASE_URL"):
            base_url = cfg["GPT_IMAGE_BASE_URL"]

    # 2. Environment variables
    if os.environ.get("GPT_IMAGE_API_KEY"):
        api_key = os.environ["GPT_IMAGE_API_KEY"]
    if os.environ.get("GPT_IMAGE_BASE_URL"):
        base_url = os.environ["GPT_IMAGE_BASE_URL"]

    # 1. CLI args (highest priority)
    if api_key_arg:
        api_key = api_key_arg
    if base_url_arg:
        base_url = base_url_arg

    if not api_key:
        print(
            "错误: 未找到 API Key。\n"
            "  方法一: 运行 python3 setup.py 创建配置文件\n"
            "  方法二: 设置环境变量  export GPT_IMAGE_API_KEY=your_key\n"
            "  方法三: 传参  --api-key your_key",
            file=sys.stderr,
        )
        sys.exit(1)

    API_KEY  = api_key
    BASE_URL = base_url.rstrip("/")
    AUTH_HDR.clear()
    AUTH_HDR.update({"Authorization": f"Bearer {API_KEY}"})
    JSON_HDR.clear()
    JSON_HDR.update({**AUTH_HDR, "Content-Type": "application/json"})


# ── 50 种风格定义 ──────────────────────────────────────────────────────────────
STYLES = {
    "01": {
        "name": "像素艺术", "en": "Pixel Art",
        "desc": "Retro game aesthetic",
        "prefix": "Pixel art style, 16-bit retro game aesthetic, thick black pixel outlines, no anti-aliasing, clean pixel art,"
    },
    "02": {
        "name": "8位风", "en": "8-Bit",
        "desc": "Classic console vibes",
        "prefix": "8-bit style, classic NES/Game Boy console aesthetic, extremely limited color palette, chunky square pixels, dithering,"
    },
    "03": {
        "name": "动漫风", "en": "Anime",
        "desc": "Clean lines, vibrant",
        "prefix": "Anime illustration style, clean line art, vibrant flat colors, cel-shaded, manga-inspired, expressive characters,"
    },
    "04": {
        "name": "水彩", "en": "Watercolor",
        "desc": "Organic & expressive",
        "prefix": "Watercolor painting style, wet-on-wet technique, soft organic edges, translucent washes of color, visible paper texture,"
    },
    "05": {
        "name": "油画", "en": "Oil Painting",
        "desc": "Rich brush strokes",
        "prefix": "Oil painting style, rich impasto brushwork, textured canvas, deep saturated colors, classical painting technique,"
    },
    "06": {
        "name": "蓝图", "en": "Blueprint",
        "desc": "Technical & precise",
        "prefix": "Technical blueprint style, white fine lines on deep blue background, architectural drafting, precise measurements and labels, engineering diagram,"
    },
    "07": {
        "name": "等距视角", "en": "Isometric",
        "desc": "3D angled perspective",
        "prefix": "Isometric 3D illustration style, 45-degree angled top-down view, clean geometric shapes, flat shading, game isometric art,"
    },
    "08": {
        "name": "低多边形", "en": "Low Poly",
        "desc": "Geometric & minimal",
        "prefix": "Low poly 3D art style, triangulated geometric facets, flat-shaded polygons, minimal color gradient, abstract geometric,"
    },
    "09": {
        "name": "霓虹光效", "en": "Neon Glow",
        "desc": "Electric & bold",
        "prefix": "Neon glow art style, electric neon light tubes, glowing bloom effect on dark background, vivid neon colors, night city aesthetic,"
    },
    "10": {
        "name": "写实摄影", "en": "Photoreal",
        "desc": "Realistic & detailed",
        "prefix": "Photorealistic style, ultra-detailed, studio lighting, sharp focus, high-resolution photography, realistic textures,"
    },
    "11": {
        "name": "电影感", "en": "Cinematic",
        "desc": "Atmospheric & dramatic",
        "prefix": "Cinematic film style, dramatic atmospheric lighting, anamorphic lens flare, moody color grading, cinematic wide shot, film grain,"
    },
    "12": {
        "name": "抽象艺术", "en": "Abstract",
        "desc": "Interpretive & bold",
        "prefix": "Abstract expressionist art style, non-representational, bold geometric or organic shapes, emotional color palette, interpretive composition,"
    },
    "13": {
        "name": "墨线画", "en": "Ink Drawing",
        "desc": "Bold & expressive",
        "prefix": "Ink drawing style, bold black ink lines, expressive brushwork, high-contrast black and white, pen and ink illustration,"
    },
    "14": {
        "name": "蚀刻版画", "en": "Etching",
        "desc": "Fine lines & texture",
        "prefix": "Etching printmaking style, fine crosshatched lines, intaglio texture, aged paper tone, detailed engraved illustration,"
    },
    "15": {
        "name": "炭笔画", "en": "Charcoal",
        "desc": "Raw & textured",
        "prefix": "Charcoal drawing style, raw textured strokes, smudged shadows, gritty graphite texture, dramatic tonal contrast, artist sketch,"
    },
    "16": {
        "name": "粉彩/色粉", "en": "Pastel",
        "desc": "Soft & delicate",
        "prefix": "Pastel art style, soft delicate colors, chalky texture, dreamy muted tones, gentle light, soft-focus illustration,"
    },
    "17": {
        "name": "合成波", "en": "Synthwave",
        "desc": "Retro futurism",
        "prefix": "Synthwave retro-futurism style, 1980s neon grid, sunset gradient purple and pink sky, chrome outlines, retrowave aesthetic,"
    },
    "18": {
        "name": "蒸汽朋克", "en": "Steampunk",
        "desc": "Vintage & intricate",
        "prefix": "Steampunk art style, Victorian-era mechanical gears and cogs, brass and copper tones, steam pipes, intricate clockwork details,"
    },
    "19": {
        "name": "赛博朋克", "en": "Cyberpunk",
        "desc": "High tech & neon",
        "prefix": "Cyberpunk art style, dystopian mega-city, neon signs in rain, high-tech low-life aesthetic, holographic displays, dark futuristic,"
    },
    "20": {
        "name": "浮世绘", "en": "Ukiyo-e",
        "desc": "Traditional & timeless",
        "prefix": "Ukiyo-e woodblock print style, traditional Japanese art, flat bold outlines, limited color woodblock printing, Edo-period aesthetic,"
    },
    "21": {
        "name": "极简线条", "en": "Minimal Line",
        "desc": "Clean & minimal",
        "prefix": "Minimal line art style, single continuous line drawing, clean white background, ultra-minimal, elegant sparse composition,"
    },
    "22": {
        "name": "金箔", "en": "Gold Foil",
        "desc": "Luxurious & refined",
        "prefix": "Gold foil art style, metallic gold leaf texture, luxurious gilded illustration on dark background, refined ornate details,"
    },
    "23": {
        "name": "全息", "en": "Holographic",
        "desc": "Shimmer & shine",
        "prefix": "Holographic iridescent art style, rainbow prismatic shimmer, chrome holographic foil effect, color-shifting metallic surface,"
    },
    "24": {
        "name": "技术剖面图", "en": "Technical Cutaway",
        "desc": "Detailed & informative",
        "prefix": "Technical cutaway illustration style, cross-section diagram, exploded view engineering drawing, labeled internal components, instructional illustration,"
    },
    "25": {
        "name": "吉卜力风", "en": "Ghibli Style",
        "desc": "Warm hand-painted fantasy",
        "prefix": "Studio Ghibli animation style, hand-painted warm fantasy, lush painterly backgrounds, soft natural lighting, whimsical storybook feel,"
    },
    "26": {
        "name": "波普艺术", "en": "Pop Art",
        "desc": "Bold colors, halftone dots",
        "prefix": "Pop Art style, bold flat colors, halftone dot pattern, comic book inspired, Roy Lichtenstein aesthetic, graphic and punchy,"
    },
    "27": {
        "name": "印象派", "en": "Impressionism",
        "desc": "Light & color, visible strokes",
        "prefix": "Impressionist painting style, visible loose brushstrokes, captured fleeting light, dappled color, Monet-inspired painterly aesthetic,"
    },
    "28": {
        "name": "超现实主义", "en": "Surrealism",
        "desc": "Dreamlike & irrational",
        "prefix": "Surrealist art style, dreamlike impossible scenario, Dalí-inspired, hyper-realistic rendering of irrational scenes, uncanny dreamscape,"
    },
    "29": {
        "name": "装饰艺术", "en": "Art Deco",
        "desc": "Geometric elegance, 1920s",
        "prefix": "Art Deco style, 1920s geometric elegance, symmetrical bold shapes, gold and black palette, ornate decorative borders, Jazz Age glamour,"
    },
    "30": {
        "name": "新艺术运动", "en": "Art Nouveau",
        "desc": "Organic curves, floral motifs",
        "prefix": "Art Nouveau style, flowing organic curves, floral and botanical motifs, Mucha-inspired decorative borders, sinuous natural lines,"
    },
    "31": {
        "name": "蒸汽波", "en": "Vaporwave",
        "desc": "Retro 80s/90s, pastel neons",
        "prefix": "Vaporwave aesthetic, pastel neon colors, retro 80s/90s nostalgia, glitch effects, Greek statues and palm trees, lo-fi surreal,"
    },
    "32": {
        "name": "故障艺术", "en": "Glitch Art",
        "desc": "Digital corruption aesthetic",
        "prefix": "Glitch art style, digital signal corruption, RGB channel offset, scanline artifacts, pixelated data moshing, distorted digital aesthetic,"
    },
    "33": {
        "name": "涂鸦/街画", "en": "Graffiti",
        "desc": "Street art, spray-paint feel",
        "prefix": "Graffiti street art style, spray-painted on urban wall, bold bubble letters, drips and tags, urban street culture aesthetic,"
    },
    "34": {
        "name": "3D渲染", "en": "3D Render",
        "desc": "Smooth CG, studio lighting",
        "prefix": "3D CGI render style, smooth surfaces, physically-based rendering, studio HDRI lighting, octane or Blender render aesthetic, high-quality CG,"
    },
    "35": {
        "name": "黏土/定格", "en": "Claymation",
        "desc": "Handcrafted clay characters",
        "prefix": "Claymation stop-motion style, handcrafted clay figures, tactile material texture, fingerprint marks, Aardman animation aesthetic,"
    },
    "36": {
        "name": "剪纸风", "en": "Paper Cut",
        "desc": "Layered paper, shadow depth",
        "prefix": "Paper cut art style, layered paper silhouettes, subtle cast shadows between layers, clean geometric paper forms, craft paper texture,"
    },
    "37": {
        "name": "拼贴画", "en": "Collage",
        "desc": "Mixed media, editorial",
        "prefix": "Collage mixed-media art style, cut magazine photos combined, editorial surrealism, vintage texture overlay, layered composition,"
    },
    "38": {
        "name": "铅笔素描", "en": "Pencil Sketch",
        "desc": "Graphite, light & shadow",
        "prefix": "Pencil sketch drawing style, graphite on white paper, visible pencil strokes, hatching and shading, sketchbook aesthetic,"
    },
    "39": {
        "name": "美漫风", "en": "Comic Book",
        "desc": "Bold outlines, halftone",
        "prefix": "American comic book style, bold black ink outlines, halftone shading, speech bubble framing, superhero comic aesthetic, flat vibrant colors,"
    },
    "40": {
        "name": "赛璐璐上色", "en": "Cel Shading",
        "desc": "Flat shadow, toon render",
        "prefix": "Cel-shaded toon rendering style, flat shadow bands, anime-style 3D, strong outline on 3D model, cartoon render aesthetic,"
    },
    "41": {
        "name": "体素风", "en": "Voxel",
        "desc": "3D pixel blocks",
        "prefix": "Voxel art style, 3D pixel cubes, MagicaVoxel aesthetic, colorful block construction, game isometric voxel scene,"
    },
    "42": {
        "name": "水粉画", "en": "Gouache",
        "desc": "Opaque, matte painterly",
        "prefix": "Gouache painting style, opaque matte paint, flat areas of color, mid-century illustration aesthetic, crisp painterly edges,"
    },
    "43": {
        "name": "孔版印刷", "en": "Risograph",
        "desc": "Grainy, limited-color print",
        "prefix": "Risograph print style, limited two or three color CMYK misregistration, grainy ink texture, indie zine aesthetic, slightly off-register print,"
    },
    "44": {
        "name": "中国水墨", "en": "Chinese Ink Wash",
        "desc": "Flowing ink, poetic",
        "prefix": "Chinese ink wash painting style, sumi-e brushwork, flowing black ink on rice paper, poetic negative space, traditional East Asian aesthetic,"
    },
    "45": {
        "name": "彩色玻璃", "en": "Stained Glass",
        "desc": "Leaded outlines, luminous",
        "prefix": "Stained glass window style, thick black lead lines between colored glass segments, luminous backlit colors, mosaic tessellation, cathedral window aesthetic,"
    },
    "46": {
        "name": "木刻版画", "en": "Woodcut",
        "desc": "Carved lines, high contrast",
        "prefix": "Woodcut print style, carved wood grain texture, bold black and white high contrast, rough chiseled edges, relief print aesthetic,"
    },
    "47": {
        "name": "黑色电影", "en": "Film Noir",
        "desc": "High contrast B&W, moody",
        "prefix": "Film noir style, high contrast black and white, dramatic chiaroscuro lighting, venetian blind shadow patterns, moody 1940s crime aesthetic,"
    },
    "48": {
        "name": "双重曝光", "en": "Double Exposure",
        "desc": "Overlaid images, ghostly",
        "prefix": "Double exposure photography style, two images blended together, silhouette filled with landscape, ghostly transparent overlay, dreamlike composite,"
    },
    "49": {
        "name": "扁平设计", "en": "Flat Design",
        "desc": "No shadow, vector-clean",
        "prefix": "Flat design illustration style, no shadows or gradients, clean vector shapes, bold solid colors, modern minimal UI icon aesthetic,"
    },
    "50": {
        "name": "乐高风", "en": "LEGO Style",
        "desc": "Brick-built, playful",
        "prefix": "LEGO brick art style, everything built from colorful plastic bricks, stud texture on top surfaces, cheerful primary colors, toy construction aesthetic,"
    },
}

# ── 预设批量素材（原有功能保留） ────────────────────────────────────────────────
BATCH_ASSETS = [
    {
        "name": "animal_0 兔子",
        "path": "client/public/assets/sprites/animal_0.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon white rabbit, "
            "front-facing sitting pose, big round eyes, long ears, chubby chibi proportions, "
            "bright white and pink color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "suitable for a poker card game character seat icon"
        )
    },
    {
        "name": "animal_1 猫",
        "path": "client/public/assets/sprites/animal_1.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon orange tabby cat, "
            "front-facing sitting pose, pointed ears, striped markings, chubby chibi proportions, "
            "warm orange and cream color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "card game character icon"
        )
    },
    {
        "name": "animal_2 狗",
        "path": "client/public/assets/sprites/animal_2.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon golden retriever dog, "
            "front-facing sitting pose, floppy ears, happy expression, chubby chibi proportions, "
            "golden yellow and cream color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "card game character icon"
        )
    },
    {
        "name": "animal_3 熊",
        "path": "client/public/assets/sprites/animal_3.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon brown bear cub, "
            "front-facing sitting pose, round ears, round belly, chubby chibi proportions, "
            "warm brown and beige color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "card game character icon"
        )
    },
    {
        "name": "animal_4 狐狸",
        "path": "client/public/assets/sprites/animal_4.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon red fox, "
            "front-facing sitting pose, pointed ears with white tips, chubby chibi proportions, "
            "vivid orange-red and white color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "card game character icon"
        )
    },
    {
        "name": "animal_5 猪",
        "path": "client/public/assets/sprites/animal_5.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon pink pig, "
            "front-facing sitting pose, round snout, chubby chibi proportions, "
            "soft pink and rose color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "card game character icon"
        )
    },
    {
        "name": "animal_6 鸡",
        "path": "client/public/assets/sprites/animal_6.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon yellow chick, "
            "front-facing sitting pose, small beak, red comb on head, chubby chibi proportions, "
            "bright yellow and red color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "card game character icon"
        )
    },
    {
        "name": "animal_7 青蛙",
        "path": "client/public/assets/sprites/animal_7.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art character sprite of a cute cartoon green frog, "
            "front-facing sitting pose, big round eyes on top of head, wide smile, chubby chibi proportions, "
            "bright green and lime color palette, thick black pixel outlines, "
            "white plain background, retro 16-bit game style, no anti-aliasing, clean pixel art, "
            "card game character icon"
        )
    },
    {
        "name": "table_bg 牌桌背景",
        "path": "client/public/assets/table/table_bg.png",
        "size": "16:9", "resolution": "1k",
        "prompt": (
            "Pixel art top-down view of a casino poker table, "
            "dark green felt surface with lighter green oval playing area in center, "
            "wooden brown border frame around the table, community card area marked in center, "
            "10 small circular seat positions around the edge, "
            "retro 16-bit pixel art style, warm dim lighting, no anti-aliasing, "
            "game background for a multiplayer card game"
        )
    },
    {
        "name": "card_back 扑克牌背",
        "path": "client/public/assets/table/card_back.png",
        "size": "2:3", "resolution": "1k",
        "prompt": (
            "Pixel art playing card back design, "
            "dark navy blue background, decorative geometric diamond pattern in lighter blue and gold, "
            "thin gold border frame, retro 16-bit pixel art style, clean pixel art, no anti-aliasing, "
            "classic card back pattern for a poker game"
        )
    },
    {
        "name": "frame_common 普通卡框",
        "path": "client/public/assets/cards/frame_common.png",
        "size": "3:4", "resolution": "1k",
        "prompt": (
            "Pixel art card frame border for a trading card game, "
            "grey and white color scheme, simple decorative stone-like border texture, "
            "small corner ornaments, dark grey outer border, light grey inner border, "
            "empty white center area, retro 16-bit pixel art style, no text, no card content, "
            "only the decorative border frame, common rarity card frame"
        )
    },
    {
        "name": "frame_rare 稀有卡框",
        "path": "client/public/assets/cards/frame_rare.png",
        "size": "3:4", "resolution": "1k",
        "prompt": (
            "Pixel art card frame border for a trading card game, "
            "blue and silver color scheme, elegant magical border with blue glow pixel effect, "
            "intricate corner ornaments with small star pixels, shimmering blue gradient border, "
            "empty white center area, retro 16-bit pixel art style, no text, no card content, "
            "only the decorative glowing border frame, rare rarity card frame"
        )
    },
    {
        "name": "frame_epic 史诗卡框",
        "path": "client/public/assets/cards/frame_epic.png",
        "size": "3:4", "resolution": "1k",
        "prompt": (
            "Pixel art card frame border for a trading card game, "
            "gold and purple color scheme, ornate baroque-style border with golden pixels, "
            "purple energy glow effect around the frame, dragon motif corner ornaments, "
            "dramatic gold gradient border, empty white center area, "
            "retro 16-bit pixel art style, no text, no card content, "
            "only the decorative legendary border frame, epic rarity card frame"
        )
    },
    {
        "name": "chip 筹码",
        "path": "client/public/assets/table/chip.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art casino poker chip icon, top-down view, "
            "circular chip with colorful striped edge pattern, bright red center with white star, "
            "stacked chips for depth illusion, vibrant red white and black colors, "
            "thick pixel outlines, white background, retro 16-bit game icon style, clean pixel art"
        )
    },
    {
        "name": "dealer_chip 庄家标识",
        "path": "client/public/assets/table/dealer_chip.png",
        "size": "1:1", "resolution": "1k",
        "prompt": (
            "Pixel art dealer button chip icon, "
            "circular white button with black letter D in bold pixel font in center, "
            "white circle with dark grey border, simple clean design, "
            "white background, retro 16-bit game icon style, clean pixel art, "
            "poker game dealer marker"
        )
    },
    {
        "name": "panel_dark UI面板",
        "path": "client/public/assets/ui/panel_dark.png",
        "size": "4:3", "resolution": "1k",
        "prompt": (
            "Pixel art dark UI panel background for a video game, "
            "dark charcoal and dark green color scheme, "
            "dark overlay with pixel art border frame, subtle inner glow along the edges, "
            "small gold pixel corner ornaments, slightly textured dark surface, "
            "retro 16-bit game UI panel style, suitable as a modal or HUD panel background"
        )
    },
]


# ── API helpers ────────────────────────────────────────────────────────────────

def submit_task(prompt, size="1:1", resolution="1k"):
    resp = requests.post(
        f"{BASE_URL}/images/generations",
        headers=JSON_HDR,
        json={"model": "gpt-image-2", "prompt": prompt, "n": 1,
              "size": size, "resolution": resolution},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["task_id"]


def poll_task(task_id, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=AUTH_HDR, timeout=15)
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["status"]
        if status == "completed":
            return data["result"]["images"][0]["url"][0]
        if status == "failed":
            raise RuntimeError(f"Task {task_id} failed: {data.get('error')}")
        print(f"  [{task_id}] {status} {data.get('progress', 0)}%", flush=True)
        time.sleep(6)
    raise TimeoutError(f"Task {task_id} timed out")


def download(url, dest_path):
    full = os.path.join(PROJ_ROOT, dest_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(full, "wb") as f:
        f.write(resp.content)
    print(f"  保存: {dest_path} ({len(resp.content) // 1024} KB)", flush=True)
    return full


def generate_one(prompt, style_id=None, out_path=None, size="1:1", resolution="1k"):
    style = STYLES.get(style_id)
    full_prompt = f"{style['prefix']} {prompt}" if style else prompt
    style_label = f"{style_id}_{style['en'].replace(' ', '_').lower()}" if style else "custom"

    if not out_path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"client/public/assets/generated/{ts}_{style_label}.png"

    print(f"风格: {style['name']} ({style['en']})" if style else "风格: 自定义")
    print(f"提示词: {full_prompt[:120]}...")
    print("提交任务...", flush=True)

    task_id = submit_task(full_prompt, size, resolution)
    print(f"task_id={task_id}, 轮询中...", flush=True)
    url = poll_task(task_id)
    saved = download(url, out_path)
    print(f"\n✓ 完成  →  {saved}")
    return saved


# ── CLI ────────────────────────────────────────────────────────────────────────

def print_help():
    # 4 大类高亮风格 + 通俗"适合做什么"标签
    CATEGORIES = [
        ("📷 写实 / 电影感  —— 像真照片、有镜头感,适合主视觉、产品图、宣发", [
            ("10", "做产品照、人物照,需要真实质感"),
            ("11", "海报、宣发图,要有大片氛围"),
            ("47", "黑白冷峻,适合悬疑、文艺"),
            ("48", "人像剪影叠风景,文艺概念图"),
        ]),
        ("🎨 插画 / 动漫 / 手绘  —— 线条+色彩,亲和好看,适合社交配图、故事化场景", [
            ("03", "二次元角色,头像、社交配图"),
            ("04", "温柔治愈,生活类、母婴、文创"),
            ("25", "吉卜力童话感,故事、奇幻、童年"),
            ("39", "美漫力量感,IP 形象、英雄题材"),
        ]),
        ("🕹 数字 / 复古 / 赛博  —— 像素、霓虹、未来感,适合游戏、科技、潮流", [
            ("01", "复古游戏画风,游戏 ICON、Q 版角色"),
            ("19", "赛博朋克霓虹夜城,科技、未来"),
            ("17", "80年代合成波,潮流海报、致敬复古"),
            ("34", "干净 3D 渲染,产品 mockup、电商图"),
        ]),
        ("🖼 传统 / 抽象 / 工艺  —— 油画、水墨、版画,适合人文、艺术、品质叙事", [
            ("05", "古典油画,人物、肖像、艺术氛围"),
            ("44", "中国水墨,东方意境、留白诗意"),
            ("27", "印象派光影,氛围、自然、咖啡馆感"),
            ("21", "极简线条,编辑设计、品牌、性冷淡"),
        ]),
    ]
    highlighted = {sid for _, items in CATEGORIES for sid, _ in items}

    print("muse-image — 对话式 AI 出图工具")
    print("=" * 70)
    print()
    print('👋 第一次用?直接说"我想画一张 xxx"就行——我会用 8 道选择题')
    print("   帮你把需求落成提示词,确认后再出图,不满意还能微调。")
    print()
    print("下面是 50 种画风。先看 4 大类的推荐风格(够 90% 场景用),")
    print('找不到合适的再翻最下方的"全部 50 种"完整列表。')
    print()

    # 4 大类推荐
    for title, items in CATEGORIES:
        print(title)
        for sid, tag in items:
            s = STYLES[sid]
            print(f"  [{sid}] {s['name']:<8}  适合: {tag}")
        print()

    # 其余风格,精简列出
    print("─" * 70)
    print("📚 其他 34 种风格(场景更专、用得较少,需要时按 ID 选):")
    print()
    cols = []
    for sid, s in STYLES.items():
        if sid in highlighted:
            continue
        cols.append(f"[{sid}] {s['name']}")
    # 三列排版
    for i in range(0, len(cols), 3):
        row = cols[i:i+3]
        print("  " + "".join(f"{c:<22}" for c in row))
    print()

    print("=" * 70)
    print("🚀 怎么用")
    print("=" * 70)
    print()
    print("【推荐】对话式出图(适合新手 / 想要好结果)")
    print("  直接告诉我你要画什么,我会问 8 个问题(用途、人群、内容、")
    print("  风格、比例…),全程不用记命令。例如:")
    print("    > 我想画一张公众号文章的封面,主题是程序员的猫")
    print()
    print("【快速】一行命令直接出图(适合知道自己要什么)")
    print("  /muse-image --style 19 一只猫在霓虹小巷")
    print("    └─ --style 后面填上面表里的两位 ID")
    print()
    print("【进阶】组合 + 微调")
    print("  • 风格混搭:   --style 25+18   (吉卜力 × 蒸汽朋克)")
    print('  • 加抑制词:   --negative "卡通,儿童画"   (告诉 AI 不要什么)')
    print("  • 改比例:     --size 16:9   (常用: 1:1 / 16:9 / 9:16 / 2:3 / 3:2 / 3:4 / 4:3,也可自定义 W:H)")
    print("  • 改清晰度:   --resolution 2k   (默认 1k,要大图就 2k/4k)")
    print()
    print("【其他指令】")
    print("  /muse-image show     —— 看当前出图进度和历史版本")
    print("  /muse-image refine   —— 对刚才那张图做微调")
    print("  /muse-image accept   —— 把当前版本定稿、归档")
    print("  /muse-image list     —— 列出所有历史 session")
    print()
    print('💡 不知道选什么风格?直接说"帮我画 xxx",剩下交给我。')


def batch_main():
    print(f"开始批量生成 {len(BATCH_ASSETS)} 个素材...\n")
    tasks = []
    for asset in BATCH_ASSETS:
        print(f"提交: {asset['name']} ...", end=" ", flush=True)
        try:
            tid = submit_task(asset["prompt"], asset["size"], asset["resolution"])
            tasks.append((tid, asset))
            print(f"task_id={tid}")
        except Exception as e:
            print(f"失败: {e}")
            tasks.append((None, asset))

    print(f"\n已提交 {sum(1 for t,_ in tasks if t)} / {len(tasks)}，开始轮询...\n")
    success = failed = 0
    for task_id, asset in tasks:
        if task_id is None:
            failed += 1
            continue
        print(f"⏳ {asset['name']} ({task_id})")
        try:
            url = poll_task(task_id)
            download(url, asset["path"])
            print(f"✓  {asset['name']} 完成")
            success += 1
        except Exception as e:
            print(f"✗  {asset['name']} 失败: {e}")
            failed += 1
    print(f"\n完成: {success} 成功，{failed} 失败")


def _read_prompt_file(path):
    """读取 .prompt.md：剥掉 --- YAML 头，正文（含 Avoid 段）作为最终 prompt。"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            content = content[end + 5:]
    return content.strip()


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help", "-h", action="store_true")
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--style", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--prompt-file", default=None,
                        help="从 .prompt.md 文件读 prompt（剥 YAML 头），与 --prompt 互斥")
    parser.add_argument("--negative", default=None,
                        help="追加抑制词，会拼成 ' Avoid: <text>.' 接到 prompt 末尾")
    parser.add_argument("--out", default=None)
    parser.add_argument("--size", default="1:1")
    parser.add_argument("--resolution", default="1k")
    parser.add_argument("--api-key",  default=None, help="API Key（优先于配置文件和环境变量）")
    parser.add_argument("--base-url", default=None, help="API Base URL（优先于配置文件和环境变量）")
    args = parser.parse_args()

    if args.help or (not args.batch and not args.prompt and not args.prompt_file):
        print_help()
        return

    load_config(api_key_arg=args.api_key, base_url_arg=args.base_url)

    if args.batch:
        batch_main()
        return

    if args.style and args.style not in STYLES:
        print(f"错误: 风格ID '{args.style}' 不存在，有效范围 01–50。用 --help 查看列表。")
        sys.exit(1)

    prompt = args.prompt
    if args.prompt_file:
        prompt = _read_prompt_file(args.prompt_file)
    if args.negative:
        prompt = (prompt or "") + f"\n\nAvoid: {args.negative.strip()}."

    # --prompt-file 已包含完整 prompt（含风格 prefix）；不再叠加 --style 的 prefix
    style_for_gen = None if args.prompt_file else args.style
    generate_one(prompt, style_for_gen, args.out, args.size, args.resolution)


if __name__ == "__main__":
    main()
