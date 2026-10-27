"""Public component boundary for other plugins."""

from typing import Any

from src.app.plugin_system.base import BaseService


class VideoStoryboardService(BaseService):
    """Offer video processing through the public service component boundary."""

    name = "video_storyboard"
    description = "视频元数据、分镜、局部放大、批处理与 video 任务识别"

    async def probe(self, input: str) -> dict[str, Any]:
        """Read container metadata without invoking a model."""
        return await self.plugin.runtime.run("probe", input)

    async def storyboard(self, input: str, **options: Any) -> dict[str, Any]:
        """Render and optionally analyze an overview or time window."""
        return await self.plugin.runtime.run("storyboard", input, **options)

    async def zoom(
        self, input: str, start: float, end: float, **options: Any
    ) -> dict[str, Any]:
        """Read a short window with larger individual cells."""
        return await self.plugin.runtime.run(
            "zoom", input, **{"from": start, "to": end, "cells": 6, **options}
        )

    async def batch(
        self, input: str, step: float = 300, **options: Any
    ) -> dict[str, Any]:
        """Cover a whole video with consecutive storyboard windows."""
        return await self.plugin.runtime.run("batch", input, step=step, **options)

    async def recognize_base64(self, base64_data: str, stream_id: str = "") -> str:
        """Return a video description from encoded incoming media."""
        return await self.plugin.runtime.recognize_base64(base64_data, stream_id)
