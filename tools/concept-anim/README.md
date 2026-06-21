# tools/concept-anim

Dev-only generator for `assets/how-it-works.gif` — the "concept code" animation in the README's **How It Works** section. Not shipped, not imported by the app or samples; it only produces a static asset that is committed to `assets/`.

## What it draws

One `retrieve` call against a single Knowledge Base that composes two **live** Knowledge Sources, then returns an inspectable **trace contract**:

1. a question enters the Knowledge Base (`answerSynthesis`)
2. the KB fans out to an **MCP Server KS** (`kind: mcpServer`) and a **Fabric Ontology KS** (`kind: fabricOntology`)
3. each source assembles from its **real payload fields** (typed line by line)
4. one response returns `activity[].type` + `references[].{knowledgeSourceName, toolName, title, sourceData}`

All field names come from `src/ks_factory/*` and `samples/responses/*` — no invented fields, no fake token streaming (it is progressive disclosure of one response).

## Requirements

- Node 18+
- A Chromium-based browser (auto-detected; override with `CHROME_PATH=/path/to/chrome`)
- `ffmpeg` on `PATH`

## Build

```bash
npm install
npm run build      # = node capture.js && bash build.sh
```

Output: `assets/how-it-works.gif` (~360 KB, 11 s, 15 fps; budget ≤ 1.5 MB, enforced by build.sh).

Steps individually:

```bash
node capture.js    # renders frames/ from scene.html via headless Chrome
bash build.sh      # ffmpeg 2-pass palette -> assets/how-it-works.gif
```

## Files

| file | role |
|---|---|
| `scene.html` | the animated scene; deterministic `window.__seek(ms)` clock so every frame is crisp & reproducible |
| `capture.js`  | drives Chrome, seeks frame-by-frame, writes `frames/*.png` |
| `build.sh`    | ffmpeg palettegen/paletteuse -> `assets/how-it-works.gif` + size gate |

## Editing the animation

Timeline lives entirely in `scene.html`'s `window.__seek(t)` (t in seconds). Adjust beat timings there; colors use the repo tokens (blue `#105fce` = Search, green `#127a5a` = Fabric, amber `#a96100` = MCP) on a dark background to match the architecture hero.

`frames/`, `palette.png`, and `node_modules/` are build artifacts — git-ignore them (see repo `.gitignore`).
