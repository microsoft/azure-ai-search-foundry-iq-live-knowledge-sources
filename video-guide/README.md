# Repo quickstart guide video

A ~4.8 minute walkthrough that takes a viewer from `git clone` to a working
deployment of this repo, following the path
**clone → local mock → test → deploy → verify → cleanup**. On-screen captions,
chapter labels, and zoom-crop callouts explain every command, file, and input
value. Built entirely from outputs that were actually run against this repo
(offline mock, local validation gate, dry-run, generated deployment summary).

The video ships in two languages with identical scene order and timing
(8648 frames / 288 s each); only the captions, callouts, and labels differ:

| Language | Final video | Per-chapter clips |
| --- | --- | --- |
| 🇰🇷 Korean  | `repo-quickstart-guide.mp4` | `clips/NN-*.mp4` |
| 🇬🇧 English | `repo-quickstart-guide-en.mp4` | `clips/en/NN-*.mp4` |

## Play it

```bash
open video-guide/repo-quickstart-guide.mp4        # Korean
open video-guide/repo-quickstart-guide-en.mp4     # English
```

Each final is the merged video (1920×1080, 30 fps). The per-chapter source
clips cover:

| Clip | Chapter | Covers |
| --- | --- | --- |
| `01-intro.mp4` | Overview | What the repo does, the 6 modules, why use it |
| `02-clone.mp4` | Clone & structure | Where to clone, folder tree, README / `.env.sample`, files to read |
| `03-local.mp4` | Local mock | `python3` only, offline `inspect_retrieve_response.py`, reading the trace, the two `.ipynb` notebooks, and how the three modes differ at retrieve time |
| `04-test.mp4` | Tests | `validate-local.sh` (13/13), `unittest`, `py_compile`, `bash -n` |
| `05-deploy.mp4` | Deploy | `deploy.sh --help`, the three modes (mcp-only / byo-fabric / full) and what each uses, input values, dry-run, 8-step run (guide), cleanup |
| `06-verify.mp4` | Verify | `deployment-summary.md`, the static web app showcase (query → KB → live sources → trace, no keys in the browser), API routes, `/api/status`, live `retrieve` trace |
| `07-summary.mp4` | Summary | 30-second recap + deliverable paths and playback |

(Korean clips live in `clips/`; English clips live in `clips/en/`.)

## Rebuild it

Requirements: `python3` with [Pillow](https://pypi.org/project/pillow/),
`ffmpeg`, and the macOS fonts Menlo + Apple SD Gothic Neo (for Korean).

```bash
cd video-guide
python3 build_guide_video.py                 # Korean: every clip + the final
python3 build_guide_video.py --lang en       # English: every clip + the final
python3 build_guide_video.py --lang en --only m5   # one chapter (m1..m7)
python3 build_guide_video.py --no-final      # skip the merge step
```

`--lang` only switches the caption/label language. The terminal text, JSON, and
file content shown on screen are real command output and stay identical across
both builds, so the two videos line up frame-for-frame.

## How it is built

- `engine.py` — rendering primitives and the ffmpeg pipeline. Each scene is a
  list of `(PIL.Image, hold_seconds)` slides; per chapter they are encoded to an
  MP4 via the ffmpeg concat demuxer, then the chapters are concatenated into the
  final video. Terminal boxes auto-size to their content, and a small
  `tr(ko, en)` helper plus `draw_mixed` (Menlo for ASCII, Apple SD Gothic Neo
  for Hangul) drive the bilingual captions.
- `scenes.py` — high-level scene builders (title cards, typed-terminal scenes
  with output reveal and explanatory caption walks, zoom callouts, file views,
  trees, key/value cards, pipeline and note cards, and a browser-chrome web-app
  showcase).
- `build_guide_video.py` — the bilingual storyboard: real command output, JSON
  colorizing, and the Korean/English captions for each chapter.

Anything that would create live Azure resources (`azd up`) is shown in
**guide** mode — the exact command and inputs are on screen, but no billable
resources are created.
