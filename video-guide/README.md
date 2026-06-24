# Repo quickstart guide video

A ~4.5 minute walkthrough that takes a viewer from `git clone` to a working
deployment of this repo, following the path
**clone → local mock → test → deploy → verify → cleanup**. Korean on-screen
captions, chapter labels, and zoom-crop callouts explain every command, file,
and input value. Built entirely from outputs that were actually run against
this repo (offline mock, local validation gate, dry-run, generated deployment
summary).

## Play it

```bash
open video-guide/repo-quickstart-guide.mp4        # the one file to watch
```

`repo-quickstart-guide.mp4` is the merged final video (1920×1080, 30 fps).
Per-chapter source clips live in `clips/`:

| Clip | Chapter | Covers |
| --- | --- | --- |
| `clips/01-intro.mp4` | Overview | What the repo does, the 6 modules, why use it |
| `clips/02-clone.mp4` | Clone & structure | Where to clone, folder tree, README / `.env.sample`, files to read |
| `clips/03-local.mp4` | Local mock | `python3` only, offline `inspect_retrieve_response.py`, reading the trace |
| `clips/04-test.mp4` | Tests | `validate-local.sh` (13/13), `unittest`, `py_compile`, `bash -n` |
| `clips/05-deploy.mp4` | Deploy | `deploy.sh --help`, input values, dry-run, 8-step run (guide), cleanup |
| `clips/06-verify.mp4` | Verify | `deployment-summary.md`, API routes, `/api/status`, live `retrieve` trace |
| `clips/07-summary.mp4` | Summary | 30-second recap + deliverable paths and playback |

## Rebuild it

Requirements: `python3` with [Pillow](https://pypi.org/project/pillow/),
`ffmpeg`, and the macOS fonts Menlo + Apple SD Gothic Neo (for Korean).

```bash
cd video-guide
python3 build_guide_video.py                 # rebuild every clip + the final
python3 build_guide_video.py --only m5       # rebuild one chapter (m1..m7)
python3 build_guide_video.py --no-final      # skip the merge step
```

## How it is built

- `engine.py` — rendering primitives and the ffmpeg pipeline. Each scene is a
  list of `(PIL.Image, hold_seconds)` slides; per chapter they are encoded to an
  MP4 via the ffmpeg concat demuxer, then the chapters are concatenated into the
  final video.
- `scenes.py` — high-level scene builders (title cards, typed-terminal scenes
  with output reveal and explanatory caption walks, zoom callouts, file views,
  trees, key/value cards, pipeline and note cards).
- `build_guide_video.py` — the storyboard: real command output, JSON
  colorizing, and the Korean captions for each chapter.

Terminal text is real command output; captions are Korean. Anything that would
create live Azure resources (`azd up`) is shown in **guide** mode — the exact
command and inputs are on screen, but no billable resources are created.
