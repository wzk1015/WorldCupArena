# WorldCupBench — Logo Prompt (Nano Banana Pro)

Paste the prompt below directly into **Gemini 3 Pro Image / Nano Banana Pro**. Aspect ratio 1:1. Request four variants, pick the strongest, then ask for a "clean vector-style cleanup, no photographic artifacts" as a follow-up turn.

---

## Primary prompt (EN)

```
Flat vector logo for an AI research benchmark named "WorldCupBench".

Central composition:
- A clean geometric soccer ball (hexagon + pentagon pattern) fused with a
  stylized bar-chart / leaderboard ascending from the lower-right, three
  bars of increasing height emerging from the ball as if the ball is
  being "measured."
- A subtle globe longitude/latitude arc wrapping the ball to suggest "World
  Cup" without being literal — no trophies, no flags.
- Minimal monoline style, 2px stroke equivalent, one accent color.

Color palette:
- Deep navy background (#0B1E3C) OR transparent; provide both.
- Primary line: pure white (#FFFFFF).
- Single accent on the tallest bar and one pentagon of the ball:
  electric green (#00E676) — evokes the pitch + "correct prediction."

Typography (optional wordmark version):
- "WorldCupBench" in a geometric sans-serif (Inter / Space Grotesk feel),
  tight letter-spacing, positioned to the right of the mark, baseline
  aligned with the ball center.
- Subtitle micro-text: "LLM · Agent · Football" in 30% opacity white,
  all-caps, tracked out.

Style constraints:
- No gradients, no drop shadows, no photorealistic textures.
- No human figures, no national flags, no actual UEFA/FIFA imagery.
- Optically centered, generous negative space — it must read at 32px
  favicon size.
- Thin-line geometric, reminiscent of the OpenAI / Anthropic / Hugging
  Face identity family (clean, research-y, not sports-marketing).

Deliverables in one image set:
1. Icon only, square, transparent background.
2. Icon only, square, navy background.
3. Horizontal wordmark (icon + "WorldCupBench"), navy background.
4. Monochrome white version (for dark surfaces).

Avoid: trophies, confetti, stadium silhouettes, overly bright rainbows,
emoji-like cartoon style, AI face mascots.
```

---

## Secondary prompt (concept B — if A feels too busy)

Swap the "soccer ball + leaderboard" mark for this instead:

```
A single stylized hexagon (one face of a soccer ball), with a thin
data-line (line-graph) piercing diagonally through it from bottom-left
to top-right, the line terminating in a small filled circle at the
upper tip. The hexagon is outlined in white monoline; the diagonal
line is the accent green; the terminal dot has a faint green glow
ring (at most 15% opacity). Everything else the same as concept A.
```

This reads more as "measurement" and less as "dashboard," which some
reviewers prefer.

---

## Secondary prompt (concept C — playful but restrained)

```
Concept C: a minimalist "ball as pie chart." Split a soccer-ball
silhouette into three probability wedges (home/draw/away) at
60%/25%/15%, the 60% wedge in electric green, the other two in
light gray. A tiny inline caption "P(home) = 0.60" set in monospace
below. Everything else as concept A.
```

This one is most on-brand for a probability-scoring benchmark but is
harder to read at favicon size — use only for hero images.

---

## Prompt (中文，直接喂给 nano banana pro)

```
为一个名叫 "WorldCupBench" 的 AI 研究基准项目设计扁平矢量 logo。

核心图形：
- 一个几何风足球（六边形+五边形拼接），在球体的右下方长出三根
  递增高度的柱状图，如同足球正在被"测量"。
- 一条细细的经纬线弧线包裹足球，暗示"世界杯"概念，但不出现奖杯、
  国旗等具体符号。
- 极简单线条风格，2px 粗细，仅一个强调色。

色彩：
- 深藏青背景 (#0B1E3C)；同时生成透明背景版本。
- 主线条纯白 (#FFFFFF)。
- 强调色仅用在最高的那根柱子和球上的一个五边形：电光绿 (#00E676)
  ——既代表草坪，又代表"预测正确"。

字体（如需文字版）：
- "WorldCupBench" 使用几何无衬线体（接近 Inter / Space Grotesk），
  字距紧凑，置于图形右侧，基线与球心对齐。
- 下方小字副标题 "LLM · Agent · Football"，白色 30% 透明度，全大写，
  字距拉宽。

风格约束：
- 不使用渐变、阴影、写实纹理。
- 不出现人物、国旗、UEFA/FIFA 等真实赛事图形。
- 视觉居中，留白充足，必须能在 32px favicon 尺寸下清晰识别。
- 整体气质向 OpenAI / Anthropic / Hugging Face 的学术科技品牌靠齐，
  而不是体育营销风格。

请一次性输出 4 个版本：
1. 仅图形，正方形，透明背景。
2. 仅图形，正方形，藏青背景。
3. 横版（图形+文字），藏青背景。
4. 单色白版（用于深色背景）。

避免：奖杯、彩带、球场剪影、过饱和彩虹色、卡通 AI 吉祥物。
```

---

## Iteration tips

- If the first generation looks too "dashboard-app," add `"more editorial, magazine-cover restraint"` to the prompt.
- If the green is too neon, swap `#00E676` for `#2ECC71` (LaLiga-style green).
- If you want an alternate palette: replace green with `#FFB347` (amber — more Premier-League feel) or `#E4003A` (red — Bundesliga).
- For the favicon, ask Nano Banana Pro for a `"16×16 pixel-grid simplification of concept A, only the hexagon + single accent pixel"`.

---

## Where to drop the final assets

```
docs/leaderboard/assets/logo/
  logo.svg            # primary horizontal wordmark
  logo_icon.svg       # icon only, transparent
  logo_mono.svg       # white monochrome
  favicon.png         # 32×32
  og.png              # 1200×630 social card
```

Reference them from the static leaderboard's HTML head and the README
banner.
