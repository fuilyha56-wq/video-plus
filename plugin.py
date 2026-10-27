"""MoFox native entry point."""

from src.app.plugin_system.base import BasePlugin, register_plugin
from src.kernel.logger import get_logger

from .config import VideoStoryboardConfig
from .event_handler import VideoRecognizeHandler
from .runtime import VideoRuntime
from .service import VideoStoryboardService
from .tools import ALL_TOOLS

logger = get_logger("video-plus")


@register_plugin
class VideoStoryboardPlugin(BasePlugin):
    """Register the native MoFox configuration and video components."""

    plugin_name = "video-plus"
    configs = [VideoStoryboardConfig]

    def __init__(self, config: VideoStoryboardConfig | None = None) -> None:
        """Create the shared video runtime from plugin configuration."""
        super().__init__(config or VideoStoryboardConfig())
        self.runtime = VideoRuntime(self.config)

    def get_components(self) -> list[type]:
        """Expose enabled services, event interception and tools."""
        if not self.config.plugin.enabled:
            return []
        components: list[type] = [VideoStoryboardService]
        if self.config.plugin.auto_recognize:
            components.append(VideoRecognizeHandler)
        if self.config.plugin.tools_enabled:
            components.extend(ALL_TOOLS)
        return components

    async def on_plugin_loaded(self) -> None:
        """Validate external runtimes without calling any model."""
        if self.config.plugin.enabled:
            await self.runtime.check_dependencies()
            logger.info(
                "视频识别加强插件已加载：识别模型来自 config/model.toml 的 video 任务"
            )

    async def on_plugin_unloaded(self) -> None:
        """Release owned video processing resources."""
        await self.runtime.close()
