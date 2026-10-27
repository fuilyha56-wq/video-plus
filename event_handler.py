"""Take ownership of MoFox's video media event and preserve its cache contract."""

from typing import Any

from src.app.plugin_system.base import BaseEventHandler
from src.app.plugin_system.types import EventType
from src.kernel.event import EventDecision
from src.kernel.logger import get_logger

logger = get_logger("video_storyboard")


class VideoRecognizeHandler(BaseEventHandler):
    """Recognize unhandled video events before the framework placeholder."""

    name = "video_recognize"
    description = "通过分镜和 video 模型任务接管视频识别"
    weight = 100
    timeout = 0  # The runtime bounds the whole operation, including inference.
    init_subscribe = [EventType.ON_MEDIA_RECOGNIZE]

    async def execute(
        self, event_name: str, params: dict[str, Any]
    ) -> tuple[EventDecision, dict[str, Any]]:
        """Commit only successful video descriptions using existing event keys."""
        if (
            event_name != EventType.ON_MEDIA_RECOGNIZE.value
            or params.get("media_type") != "video"
            or params.get("engine") != "video"
            or params.get("skip_engine")
            or params.get("engine_processed")
            or params.get("description")
            or not self.plugin.config.plugin.auto_recognize
        ):
            return EventDecision.PASS, params
        try:
            description = await self.plugin.runtime.recognize_base64(
                params.get("base64_data", ""),
                str(params.get("stream_id") or ""),
            )
        except Exception as error:
            logger.warning(f"视频分镜识别失败（保留未识别状态，可重试）: {error}")
            return EventDecision.PASS, params
        if not description:
            return EventDecision.PASS, params
        # EventBus requires an identical key set. MoFox persists the returned
        # description to Videos + VideoDescriptions and replaces [视频(id)].
        params["description"] = description
        params["engine_processed"] = True
        params["skip_engine"] = True
        return EventDecision.STOP, params
