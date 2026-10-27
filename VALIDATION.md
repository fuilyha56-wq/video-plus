# Validation — 2026-10-28

Environment: Neo-MoFox 1.3.0-alpha.2, Python 3.11.9, Node.js 24.16.0, ffmpeg 9.0.1 (Windows).

Completed:

- Upstream suite: **189 passed**. Local fake-ASR connections require permission to access 127.0.0.1 in the test environment.
- MoFox integration checks: **26 passed** (24 full-suite checks plus the unload/inference cancellation and received-video SQL/context regressions).
- Received-video integration: real MessageConverter, Node/ffmpeg rendering, media-file persistence, `Videos` and `VideoDescriptions` SQL writes, media-ID lookup and cached repeated conversion passed against an isolated SQLite database. Only the external provider response was stubbed; the existing video-task payload and stream attribution were inspected.
- Modified upstream pipeline/ASR modules: targeted regression suite passed after the subtitle fix.
- Ruff checks, Python compilation, JavaScript syntax check and Git whitespace check passed.
- Native PluginManager folder loading: all seven components registered under plugin ID `video-plus`, real event dispatch committed the description, unload removed the event handler.
- Native PluginManager `.mfp` loading: public service lookup, container probing, bundled Node engine, actual PNG generation and unload passed.
- Synthetic four-second video: first two seconds red, next two seconds blue; scene boundary detected and four-cell PNG visually verified.
- Current OneBot adapter configuration already enables video processing (adapter input limit: 100 MiB).
- Live provider smoke test: `config/model.toml` selected `gemini-3.8-flash` from `[model_tasks.video]` and routed the synthetic video storyboard through the new `ikun-gemini` provider. The model returned a usable description; the complete smoke test exited successfully. No chat content was used. The report is `data/video_storyboard/smoke/report.json`.

The source folder remains `plugins/video_storyboard`; its plugin ID is `video-plus` and WebUI display name is “视频识别加强”. Configuration is stored at `config/plugins/video-plus/config.toml`. Activation in an existing bot process requires restarting MoFox or loading the renamed plugin through an appropriate plugin manager; validation above ran in isolated processes.
