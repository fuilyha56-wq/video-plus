# Upstream provenance

- Project: https://github.com/SAOS-3624/dsh-video-storyboard
- Version: 0.2.1
- Commit: `fa543a3603685d906c87a021f61c2dfe60215a34`
- Retrieved: 2026-10-27
- License: MIT, Copyright (c) 2026 SAOS-3624. Original license and credits retained in `vendor/`.

`vendor/` contains the upstream engine, CLI, documentation and original tests. The MoFox adapter uses the engine directly over a local JSON subprocess protocol and does not load the DSH host entry point or install its optional peer dependency.

Local engine changes:

1. Hide ffmpeg/ffprobe subprocess windows on Windows.
2. In MoFox isolation mode, ignore DSH home configuration. Only explicitly enabled ASR configuration is passed by the adapter; term maps are supplied through the child environment.
3. Include ASR language in the transcript cache key.
4. Extract subtitle tracks even when the video has no audio track.

MoFox adapter additions: native manifest/config/service/tools/event handler; video-task inference; bounded concurrency, cancellation and input/artifact retention; local media-ID resolution; batch and JSON bridge; integration tests, smoke test and packaging script.

The upstream README describes a strip-layout option, but this pinned upstream engine does not implement that option. The port preserves the implemented grid layouts and all implemented tool/CLI features.
