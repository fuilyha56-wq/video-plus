"""MoFox tools: original probe/storyboard/zoom plus long-video batch mode."""

from typing import Any

from src.app.plugin_system.base import BaseTool


async def _execute(
    tool: BaseTool, operation: str, input: str, **options: Any
) -> tuple[bool, str | dict]:
    """Execute a bounded tool call and return descriptions plus artifact paths."""
    try:
        result = await tool.plugin.runtime.run(
            operation, input, stream_id=tool.get_current_stream_id(), **options
        )
        # MoFox tool results are text/JSON. The video model sees the actual PNGs;
        # the calling chatter receives grounded descriptions and artifact paths.
        fields = (
            "input",
            "info",
            "window",
            "plan",
            "text",
            "description",
            "images",
            "manifest_path",
            "timeline_path",
        )
        return True, {key: result[key] for key in fields if key in result}
    except Exception as error:
        return False, f"视频处理失败: {error}"


class VideoProbeTool(BaseTool):
    """Expose free container probing to the chatter."""

    name = "video_probe"
    description = "探测本地视频或聊天视频 media_id 的时长、画幅、音轨、字幕和阅读计划，不调用模型。"

    async def execute(self, input: str) -> tuple[bool, str | dict]:
        """读取容器信息。

        Args:
            input: 本地视频绝对路径，或消息 [视频(media_id)] 中的视频 ID。
        """
        return await _execute(self, "probe", input)


class VideoStoryboardTool(BaseTool):
    """Expose configurable storyboard rendering and video-model analysis."""

    name = "video_storyboard"
    description = "按剪辑密度生成带编号和时间线的视频分镜，使用 config/model.toml 的 video 任务解释画面。支持时间窗口、字幕和纯文本索引分页。"

    async def execute(
        self,
        input: str,
        start: float = 0,
        end: float | None = None,
        cells: int = 0,
        sheets: int = 0,
        pick: str = "sharp",
        burn: str = "index",
        min_gap: float = 1.2,
        transcript: str = "auto",
        detail: str = "med",
        cell_range: list[int] | None = None,
        text_only: bool = False,
        analyze: bool = True,
        question: str = "",
    ) -> tuple[bool, str | dict]:
        """生成分镜并识别内容。

        Args:
            input: 本地视频绝对路径或 MoFox 视频 media_id。
            start: 起始秒数，默认0。
            end: 结束秒数，省略读取到结尾。
            cells: 每张格数1到16；0自动。
            sheets: 图片张数1到4；0自动。
            pick: sharp清晰帧、mid中间帧或thumb直方图。
            burn: index编号、index+time编号加时间或none无水印。
            min_gap: 采样最小间隔秒数。
            transcript: auto优先字幕并可选ASR；off关闭台词。
            detail: 每格字幕字符预算low/med/high。
            cell_range: 只返回这些格子的文字索引，[首格,末格]，从1开始。
            text_only: 只读索引，不渲染图片、不调用模型；适合翻页。
            analyze: 是否调用video模型；false只生成分镜文件。
            question: 让视频模型重点关注的问题。
        """
        options: dict[str, Any] = {
            "from": start,
            "cells": cells,
            "sheets": sheets,
            "pick": pick,
            "burn": burn,
            "minGap": min_gap,
            "transcript": transcript,
            "detail": detail,
            "textOnly": text_only,
            "analyze": analyze,
            "question": question,
        }
        if end is not None:
            options["to"] = end
        if cell_range is not None:
            options["cellRange"] = cell_range
        return await _execute(self, "storyboard", input, **options)


class VideoZoomTool(BaseTool):
    """Expose short-window close reading."""

    name = "video_zoom"
    description = "近距离重读视频的短时间窗口，减少格数以看清人物、文字与动作；使用video任务模型。"

    async def execute(
        self,
        input: str,
        start: float,
        end: float,
        cells: int = 6,
        pick: str = "sharp",
        burn: str = "index",
        min_gap: float = 1.2,
        transcript: str = "auto",
        analyze: bool = True,
        question: str = "",
    ) -> tuple[bool, str | dict]:
        """生成细节分镜。

        Args:
            input: 本地视频绝对路径或 MoFox 视频 media_id。
            start: 窗口起始秒数，不小于0。
            end: 窗口结束秒数，必须大于start。
            cells: 格数1到9，默认6，格数越少细节越大。
            pick: sharp、mid或thumb取帧。
            burn: index、index+time或none。
            min_gap: 采样最小间隔；快切镜头可设0.3到0.5秒。
            transcript: auto读取台词，off关闭。
            analyze: 是否调用video任务模型。
            question: 关注的问题或要辨认的屏幕文字。
        """
        return await _execute(
            self,
            "zoom",
            input,
            **{
                "from": start,
                "to": end,
                "cells": cells,
                "pick": pick,
                "burn": burn,
                "minGap": min_gap,
                "transcript": transcript,
                "analyze": analyze,
                "question": question,
            },
        )


class VideoBatchTool(BaseTool):
    """Expose sequential long-video processing and a timeline artifact."""

    name = "video_batch"
    description = "长视频按时间窗口批量生成分镜和时间线，完整覆盖全片；可逐窗调用video任务模型，耗时取决于片长。"

    async def execute(
        self,
        input: str,
        step: float = 300,
        snap: bool = True,
        analyze: bool = False,
        question: str = "",
    ) -> tuple[bool, str | dict]:
        """批量处理长视频。

        Args:
            input: 本地视频绝对路径或 MoFox 视频 media_id。
            step: 每个窗口的目标秒数，至少10秒，默认300秒。
            snap: 将窗口边界吸附到真实剪辑点，并复用整片扫描。
            analyze: 是否逐窗调用video模型，默认只生成文件和时间线。
            question: 各窗口识别时关注的问题。
        """
        return await _execute(
            self,
            "batch",
            input,
            step=step,
            snap=snap,
            analyze=analyze,
            question=question,
        )


ALL_TOOLS = [VideoProbeTool, VideoStoryboardTool, VideoZoomTool, VideoBatchTool]
