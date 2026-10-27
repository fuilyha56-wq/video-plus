# 视频识别加强（video-plus）插件

将 [SAOS-3624/dsh-video-storyboard](https://github.com/SAOS-3624/dsh-video-storyboard) 移植为当前 Neo-MoFox 的原生插件。分镜引擎随插件分发，不需要安装 DeepSeek Harness 或 npm 依赖。

## 安装与模型

插件名称为 `video-plus`，WebUI 显示名为“视频识别加强”。当前源码目录放在 `plugins/video_storyboard`。安装 Node.js 20+、ffmpeg、ffprobe，并确保它们在启动 MoFox 的进程 PATH 中；也可以在插件配置中填写绝对路径。此实例已具有这些运行时。

重启 MoFox 或使用插件管理器加载 `video-plus` 后生效。插件配置位于 `config/plugins/video-plus/config.toml`，默认启用并接管视频识别；WebUI 中的插件分组名、配置标签和说明均为中文。

**所有视觉识别请求均调用 MoFox 的 `llm_api.get_model_set_by_task("video")`**，读取 `config/model.toml` 的 `[model_tasks.video]`。模型列表、供应商、密钥、温度、输出 token、并发策略和回退逻辑由 MoFox 管理。插件没有另设视觉模型，也不会使用 `vlm` 或 `utils` 任务。每次请求重新解析任务模型集。

默认提示词按以下顺序选取：插件 `storyboard.prompt` → 核心配置 `chat.video_recognition_prompt` → 插件内置中文提示词。

## 自动接管

收到视频 → MoFox 落盘并查缓存 → `ON_MEDIA_RECOGNIZE`（`engine=video`）→ 插件生成分镜及时间索引 → `video` 任务模型读取实际 PNG → 回写 `description`、`engine_processed`、`skip_engine` 并停止后续识别器。

MoFox 原有流程负责 `Videos`、`VideoDescriptions` 缓存和 `[视频(media_id):描述]` 上下文替换。插件只处理视频，尊重原有描述、跳过识别和已处理标志。失败时保留未识别状态，可重试；不会把异常文字缓存成视频描述。已有视频缓存由框架管理，不会自动强制重算。

## 保留的能力

- HSV 场景切换检测、按剪辑/语音/音频事件密度分配格位、自动选择格数和张数。
- 每段选最清晰帧，也支持中间帧和直方图取帧；支持编号和时间水印、横竖屏及旋转。
- 分镜内嵌音量、静音、剪辑点时间轴；优先提取内嵌字幕。
- 可选带时间戳 ASR：静音边界分块、疑似非语音过滤、术语纠错与缓存。
- 时间窗口、1–9 格局部放大、1–16 格 × 1–4 张总览、纯文本索引分页。
- 长片批处理、窗口边界吸附剪辑点、整片扫描结果复用、尾部短窗口合并、Markdown 时间线。
- 本地扫描/ASR 缓存、并发限制、完整调用超时、取消时终止 Node/ffmpeg 进程树。

分镜是稀疏采样，不能保证呈现所有动作或读清每个文字；需要细节时调用 `video_zoom`。整片总览最多64格，长片详细阅读可调用批处理或分段工具。上游的“384 tokens/图”是原宿主的计费口径，MoFox 中实际 token 和费用取决于 `video` 模型及供应商。

## 工具

`input` 接受本地绝对路径，也接受聊天中 `[视频(media_id)]` 的视频 ID（由 MoFox 媒体库解析）。不直接下载 URL。

| 工具 | 作用 | 模型调用 |
| --- | --- | --- |
| `video_probe(input)` | 容器元数据及阅读计划 | 无 |
| `video_storyboard(input, start=0, end=None, question="")` | 全片/窗口分镜及描述 | 默认调用 video |
| `video_zoom(input, start, end, cells=6, question="")` | 短时间窗细节重读 | 默认调用 video |
| `video_batch(input, step=300, snap=True, analyze=False)` | 批量分镜和时间线 | analyze=true 时逐窗调用 video |

分镜工具支持 `cells`、`sheets`（0自动）、`pick=sharp/mid/thumb`、`burn=index/index+time/none`、`min_gap`、`transcript=auto/off`、`detail=low/med/high`、`cell_range=[首格,末格]` 和 `text_only`。`text_only=True` 不生成图片、不调用模型；`analyze=False` 只生成文件和索引。分页时保持原有窗口、格数、张数和台词选项一致。

MoFox 工具返回文本/JSON，因此工具结果包含 **video 模型读取实际 PNG 后的描述**、可寻址时间索引和图片/manifest 文件路径。纯文本分页只返回索引，不产生新的视觉结论。

其他插件可通过公开服务签名 `video-plus:service:video_storyboard` 使用 `probe`、`storyboard`、`zoom`、`batch`、`recognize_base64`，无需导入本插件模块。服务的分镜选项使用上游命名，例如 `textOnly`、`cellRange`、`minGap`；时间窗口可用 `**{"from": 10, "to": 20}`。

## 配置

```toml
[plugin]
enabled = true
auto_recognize = true
tools_enabled = true

[runtime]
node_path = "node"
ffmpeg_path = "ffmpeg"
ffprobe_path = "ffprobe"
data_dir = "data/video_storyboard"
timeout_seconds = 900
concurrency = 2
max_input_mb = 256
retention_hours = 24

[storyboard]
cells = 0
sheets = 0
pick = "sharp"
burn = "index"
min_gap = 1.2
pixel_budget = 1440000
audio_strip = true
cache = true
transcript = "auto"
prompt = ""

[asr]
enabled = false
base_url = ""
model = ""
key_env = "MOFOX_VIDEO_ASR_KEY"
language = "zh"
max_chunk = 45
```

ASR 默认关闭网络转写，内嵌字幕仍可读取。确有需求时设置兼容 `/audio/transcriptions` 的服务、转写模型以及密钥环境变量，再启用 `asr.enabled`。这是可选台词层，视觉理解仍使用 MoFox `video` 任务。不会读取 `~/.dsh/asr.json` 或继承 DSH 的 ASR 密钥。术语表可在 `[asr.terms]` 中设置。

生成文件位于 `data/video_storyboard/inputs` 和 `outputs`，按保留时间在后续调用时清理；不会清理 MoFox 的原始媒体文件。扫描缓存位于该目录的 `cache` 子目录，上游 LRU 上限50MiB。任务超时需要结合片长调整，批量分析每个窗口都会产生模型费用。

## 验证与打包

在项目根目录运行：

```powershell
.venv/Scripts/python.exe -m pytest plugins/video_storyboard/tests -o addopts= -p no:randomly -p no:cacheprovider -q
node --test plugins/video_storyboard/vendor/test
.venv/Scripts/python.exe plugins/video_storyboard/scripts/smoke_test.py --live-model
.venv/Scripts/python.exe plugins/video_storyboard/scripts/package_plugin.py
```

Windows 的 asyncio 使用本机 socketpair，ASR 测试使用127.0.0.1假服务，执行测试的环境需允许本机网络。`--live-model` 会对合成视频调用一次当前配置的 video 模型，不发送聊天记录。

上游 CLI 保留在 `vendor/bin`。许可及上游版本、适配差异见 `LICENSE`、`UPSTREAM.md`。
