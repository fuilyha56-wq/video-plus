"""Synthetic end-to-end check. --live-model makes one configured video request."""

import argparse
import asyncio
import base64
import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
if not __package__:
    __package__ = "plugins.video_storyboard.scripts"


async def smoke(live: bool) -> None:
    """Generate synthetic media and optionally exercise real video inference."""
    from ..config import VideoStoryboardConfig
    from ..plugin import VideoStoryboardPlugin
    from ..event_handler import VideoRecognizeHandler
    from src.core.config import core_config, model_config
    from src.core.components.types import EventType
    from src.kernel.event import EventBus, EventDecision

    settings = VideoStoryboardConfig.load(
        str(ROOT / "config/plugins/video-plus/config.toml"), auto_update=False
    )
    settings.runtime.timeout_seconds = 180
    settings.storyboard.cells = 4
    settings.storyboard.sheets = 1
    settings.storyboard.pixel_budget = 640_000
    settings.storyboard.prompt = (
        "请简短说明这个视频画面的颜色及其先后变化，不要臆测声音。"
    )
    folder = ROOT / "data/video_storyboard/smoke"
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / "red-then-blue.mp4"
    subprocess.run(
        [
            settings.runtime.ffmpeg_path,
            "-hide_banner",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=320x180:r=10:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=320x180:r=10:d=2",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    plugin = VideoStoryboardPlugin(settings)
    try:
        await plugin.on_plugin_loaded()
        result = await plugin.runtime.run("storyboard", str(video), analyze=False)
        report = {
            "video": str(video),
            "images": result["images"],
            "cuts": result["cuts"],
            "local_pipeline": "passed",
        }
        path = folder / "report.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if live:
            # Read existing configuration without migrating or writing either file.
            model_config._global_model_config = model_config.ModelConfig.model_validate(
                tomllib.loads((ROOT / "config/model.toml").read_text(encoding="utf-8"))
            )
            core_config._global_config = core_config.CoreConfig.model_validate(
                tomllib.loads((ROOT / "config/core.toml").read_text(encoding="utf-8"))
            )
            core_config._inject_kernel_llm_policy(core_config._global_config)
            task = model_config.get_model_config().get_task("video")
            report["video_models"] = [entry["model_identifier"] for entry in task]
            bus = EventBus("video-live-smoke")
            bus.subscribe(
                EventType.ON_MEDIA_RECOGNIZE.value,
                VideoRecognizeHandler(plugin).execute,
                priority=100,
                timeout=0,
            )
            original = {
                "media_hash": "synthetic-test",
                "media_type": "video",
                "engine": "video",
                "base64_data": base64.b64encode(video.read_bytes()).decode("ascii"),
                "stream_id": "video-storyboard-smoke",
                "description": None,
                "engine_processed": False,
                "skip_engine": False,
            }
            decision, recognized = await bus.publish(
                EventType.ON_MEDIA_RECOGNIZE.value, original
            )
            if decision != EventDecision.STOP or not recognized["description"]:
                report["live_model"] = "failed"
                report["error"] = (
                    "Configured video model returned no usable description; inspect video-plus logs."
                )
                path.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                raise RuntimeError("视频事件未获得有效描述；检查模型服务和日志")
            report["description"] = recognized["description"]
            report["live_model"] = "passed"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Report: {path}")
    finally:
        await plugin.on_plugin_unloaded()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-model", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(smoke(arguments.live_model))
