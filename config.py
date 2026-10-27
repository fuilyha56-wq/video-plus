"""视频识别加强插件配置；视觉模型始终读取 MoFox 的 video 任务。"""

from typing import ClassVar, Literal

from src.app.plugin_system.base import BaseConfig, Field, SectionBase, config_section


class VideoStoryboardConfig(BaseConfig):
    """声明带中文 WebUI 标签的插件配置，不重复声明模型设置。"""

    name: ClassVar[str] = "config"
    description: ClassVar[str] = "视频识别加强插件配置"

    @config_section(
        "plugin",
        title="插件设置",
        description="控制视频识别接管和插件工具。",
        tag="plugin",
    )
    class PluginSection(SectionBase):
        """插件启用与识别接管选项。"""

        enabled: bool = Field(
            default=True,
            label="启用插件",
            description="启用视频识别加强插件及其服务。",
            tag="plugin",
        )
        auto_recognize: bool = Field(
            default=True,
            label="自动接管视频识别",
            description="接管 MoFox 的视频媒体识别事件，并使用 video 任务模型生成描述。",
            tag="plugin",
        )
        tools_enabled: bool = Field(
            default=True,
            label="启用视频工具",
            description="注册视频探测、分镜、局部放大和批量处理工具。",
            tag="plugin",
        )

    @config_section(
        "runtime",
        title="运行环境",
        description="设置外部程序和处理资源限制。",
        tag="general",
    )
    class RuntimeSection(SectionBase):
        """外部程序位置和本地处理限制。"""

        node_path: str = Field(
            default="node",
            label="Node.js 程序路径",
            description="Node.js 20 或更高版本的可执行文件路径；默认从 PATH 查找。",
            placeholder="node 或绝对路径",
            tag="file",
        )
        ffmpeg_path: str = Field(
            default="ffmpeg",
            label="FFmpeg 程序路径",
            description="FFmpeg 可执行文件路径；默认从 PATH 查找。",
            placeholder="ffmpeg 或绝对路径",
            tag="file",
        )
        ffprobe_path: str = Field(
            default="ffprobe",
            label="FFprobe 程序路径",
            description="FFprobe 可执行文件路径；默认从 PATH 查找。",
            placeholder="ffprobe 或绝对路径",
            tag="file",
        )
        data_dir: str = Field(
            default="data/video_storyboard",
            label="数据保存目录",
            description="插件生成的临时视频输入、分镜图片和扫描缓存目录。",
            tag="file",
        )
        timeout_seconds: int = Field(
            default=900,
            ge=10,
            le=7200,
            label="任务超时（秒）",
            description="单次完整视频识别或工具调用的最长运行时间。",
            tag="performance",
        )
        concurrency: int = Field(
            default=2,
            ge=1,
            le=16,
            label="最大并发任务数",
            description="同时处理的视频任务数量上限。",
            tag="performance",
        )
        max_input_mb: int = Field(
            default=256,
            ge=1,
            le=4096,
            label="视频大小上限（MiB）",
            description="插件接受的单个视频文件最大体积。",
            tag="performance",
        )
        retention_hours: int = Field(
            default=24,
            ge=1,
            label="文件保留时间（小时）",
            description="插件生成的输入和分镜文件保留时长；后续调用时清理过期文件。",
            tag="performance",
        )

    @config_section(
        "storyboard",
        title="分镜与识别",
        description="配置取帧、分镜和识别提示词。",
        tag="ai",
    )
    class StoryboardSection(SectionBase):
        """视频场景取帧、分镜生成和模型识别选项。"""

        cells: int = Field(
            default=0,
            ge=0,
            le=16,
            label="每张分镜格数",
            description="每张分镜包含的画面数量；设为 0 时根据视频内容自动选择。",
            tag="performance",
        )
        sheets: int = Field(
            default=0,
            ge=0,
            le=4,
            label="分镜页数",
            description="生成的分镜图片数量；设为 0 时自动选择，最多 4 页。",
            tag="performance",
        )
        pick: Literal["sharp", "mid", "thumb"] = Field(
            default="sharp",
            label="取帧策略",
            description="sharp 为清晰度优先，mid 为场景中间帧，thumb 为缩略图。",
            hint="内部值保留英文：sharp（清晰度优先）、mid（中间帧）、thumb（缩略图）。",
            choices=["sharp", "mid", "thumb"],
            input_type="select",
            tag="ai",
        )
        burn: Literal["index", "index+time", "none"] = Field(
            default="index",
            label="分镜标记",
            description="设置分镜图片中显示的格位编号和时间信息。",
            hint="内部值保留英文：index（编号）、index+time（编号和时间）、none（不显示）。",
            choices=["index", "index+time", "none"],
            input_type="select",
            tag="general",
        )
        min_gap: float = Field(
            default=1.2,
            ge=0,
            le=60,
            label="最小取帧间隔（秒）",
            description="相邻采样画面之间的最短时间间隔。",
            tag="performance",
        )
        pixel_budget: int = Field(
            default=1_440_000,
            ge=160_000,
            le=8_000_000,
            label="每页分镜像素预算",
            description="限制每张分镜图片的总像素数，降低内存和模型请求开销。",
            tag="performance",
        )
        audio_strip: bool = Field(
            default=True,
            label="附加音频时间轴",
            description="在分镜结果中附加响度、静音区间和剪辑点信息。",
            tag="general",
        )
        cache: bool = Field(
            default=True,
            label="启用结果缓存",
            description="缓存视频扫描结果和可选语音转写结果。",
            tag="general",
        )
        transcript: Literal["auto", "off"] = Field(
            default="auto",
            label="字幕处理方式",
            description="auto 为读取内嵌字幕并使用可用转写，off 为不处理字幕。",
            hint="内部值保留英文：auto（自动读取）、off（关闭）。",
            choices=["auto", "off"],
            input_type="select",
            tag="ai",
        )
        prompt: str = Field(
            default="",
            label="视频识别提示词",
            description="留空时读取 MoFox 核心配置；核心配置也为空时使用插件默认提示词。",
            placeholder="可选：自定义视频识别要求",
            input_type="textarea",
            rows=4,
            tag="text",
        )

    @config_section(
        "asr",
        title="可选语音转写",
        description="配置独立的时间戳语音转写服务。",
        tag="ai",
    )
    class AsrSection(SectionBase):
        """可选的语音转写配置；视觉识别模型仍由 video 任务决定。"""

        enabled: bool = Field(
            default=False,
            label="启用语音转写",
            description="启用独立的 OpenAI 兼容时间戳转写服务；画面识别仍使用 video 任务模型。",
            tag="ai",
        )
        base_url: str = Field(
            default="",
            label="转写服务地址",
            description="启用语音转写时必填，填写兼容服务地址并包含 /v1。",
            placeholder="https://服务地址/v1",
            depends_on="enabled",
            depends_value=True,
            tag="network",
        )
        model: str = Field(
            default="",
            label="转写模型 ID",
            description="语音转写服务要求的模型标识。",
            placeholder="例如：whisper-1",
            depends_on="enabled",
            depends_value=True,
            tag="ai",
        )
        key_env: str = Field(
            default="MOFOX_VIDEO_ASR_KEY",
            label="密钥环境变量名",
            description="从此环境变量读取转写服务密钥；插件不会将密钥保存到配置文件。",
            placeholder="MOFOX_VIDEO_ASR_KEY",
            depends_on="enabled",
            depends_value=True,
            tag="security",
        )
        language: str = Field(
            default="zh",
            label="转写语言代码",
            description="语音转写使用的语言代码，例如 zh 或 en。",
            placeholder="zh",
            depends_on="enabled",
            depends_value=True,
            tag="ai",
        )
        max_chunk: int = Field(
            default=45,
            ge=8,
            le=45,
            label="单段最长时间（秒）",
            description="以静音边界切分音频时，每段语音允许的最长时间。",
            depends_on="enabled",
            depends_value=True,
            tag="performance",
        )
        terms: dict[str, str] = Field(
            default_factory=dict,
            label="转写术语纠错表",
            description="可选的术语映射；键填写常见错误写法，值填写正确写法。",
            input_type="json",
            depends_on="enabled",
            depends_value=True,
            tag="text",
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    runtime: RuntimeSection = Field(default_factory=RuntimeSection)
    storyboard: StoryboardSection = Field(default_factory=StoryboardSection)
    asr: AsrSection = Field(default_factory=AsrSection)
