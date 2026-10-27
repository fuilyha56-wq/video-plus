"""Integration checks for the MoFox boundary and real ffmpeg/Node pipeline."""

import asyncio
import base64
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image as PILImage

from ..config import VideoStoryboardConfig
from ..event_handler import VideoRecognizeHandler
from ..plugin import VideoStoryboardPlugin
from ..runtime import EngineBridge, VideoRuntime
from .. import runtime as runtime_module
from src.core.components.loader import load_manifest
from src.core.components.types import EventType
from src.core.managers.media_manager.recognition import MediaRecognition
from src.kernel.event import EventBus, EventDecision
from src.kernel.llm import Image


@pytest.fixture
def config(tmp_path):
    result = VideoStoryboardConfig()
    result.runtime.data_dir = str(tmp_path / "plugin-data")
    result.storyboard.pixel_budget = 160_000
    return result


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    folder = tmp_path_factory.mktemp("video-storyboard")
    path = folder / "测试 video with spaces.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=160x90:r=5:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=160x90:r=5:d=2",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return path


def params(**overrides):
    return {
        "media_hash": "a" * 32,
        "media_type": "video",
        "engine": "video",
        "base64_data": "test-video",
        "stream_id": "test-stream",
        "description": None,
        "engine_processed": False,
        "skip_engine": False,
        **overrides,
    }


@pytest.mark.asyncio
async def test_manifest_and_components_match(config):
    manifest = await load_manifest(str(Path(__file__).parents[1]))
    plugin = VideoStoryboardPlugin(config)
    components = {(c.component_type, c.name) for c in plugin.get_components()}
    included = {
        (c.component_type, c.component_name)
        for c in manifest.include
        if c.component_type != "config"
    }
    assert manifest.name == plugin.plugin_name
    assert components == included
    config.plugin.enabled = False
    assert plugin.get_components() == []


@pytest.mark.asyncio
async def test_handler_commits_existing_keys_and_stops_second_engine(config):
    plugin = VideoStoryboardPlugin(config)
    plugin.runtime.recognize_base64 = AsyncMock(return_value="先红色画面，后蓝色画面。")
    handler = VideoRecognizeHandler(plugin)
    bus = EventBus("video-test")
    downstream = AsyncMock(return_value=(EventDecision.SUCCESS, {}))
    bus.subscribe(
        EventType.ON_MEDIA_RECOGNIZE.value, handler.execute, priority=100, timeout=0
    )
    bus.subscribe(EventType.ON_MEDIA_RECOGNIZE.value, downstream, priority=0)
    original = params()
    decision, result = await bus.publish(EventType.ON_MEDIA_RECOGNIZE.value, original)
    assert set(result) == set(original)
    assert result["description"] == "先红色画面，后蓝色画面。"
    assert result["engine_processed"] and result["skip_engine"]
    assert decision == EventDecision.STOP
    downstream.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"media_type": "image", "engine": "vlm"},
        {"media_type": "voice", "engine": "asr"},
        {"skip_engine": True},
        {"engine_processed": True},
        {"description": "已识别"},
    ],
)
async def test_handler_respects_other_media_and_previous_decisions(config, overrides):
    plugin = VideoStoryboardPlugin(config)
    plugin.runtime.recognize_base64 = AsyncMock()
    decision, result = await VideoRecognizeHandler(plugin).execute(
        EventType.ON_MEDIA_RECOGNIZE.value, params(**overrides)
    )
    assert decision == EventDecision.PASS
    plugin.runtime.recognize_base64.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_is_not_marked_processed(config):
    plugin = VideoStoryboardPlugin(config)
    plugin.runtime.recognize_base64 = AsyncMock(
        side_effect=RuntimeError("provider failed")
    )
    original = params()
    decision, result = await VideoRecognizeHandler(plugin).execute(
        EventType.ON_MEDIA_RECOGNIZE.value, original
    )
    assert decision == EventDecision.PASS
    assert (
        result == original
        and not result["engine_processed"]
        and result["description"] is None
    )


@pytest.mark.asyncio
async def test_video_model_task_receives_real_images_and_stream_metadata(
    config, tmp_path, monkeypatch
):
    config.storyboard.prompt = "测试提示词"
    png = tmp_path / "sheet.png"
    PILImage.new("RGB", (20, 20), "red").save(png)

    class Response:
        message = "视频描述"

        def __await__(self):
            async def collect():
                return self

            return collect().__await__()

    request = SimpleNamespace(
        add_payload=Mock(), send=AsyncMock(return_value=Response())
    )
    selected = [{"model_identifier": "configured-video-model"}]
    get_task = Mock(return_value=selected)
    create_request = Mock(return_value=request)
    monkeypatch.setattr(runtime_module.llm_api, "get_model_set_by_task", get_task)
    monkeypatch.setattr(runtime_module.llm_api, "create_llm_request", create_request)
    runtime = VideoRuntime(config)
    assert (
        await runtime._analyze(
            {"text": "cell 1 = 0-4s", "images": [str(png)]}, "看什么颜色", "stream-42"
        )
        == "视频描述"
    )
    get_task.assert_called_once_with("video")
    assert create_request.call_args.args[0] is selected
    assert create_request.call_args.kwargs["stream_id"] == "stream-42"
    payload = request.add_payload.call_args.args[0]
    assert any(isinstance(part, Image) for part in payload.content)


@pytest.mark.asyncio
async def test_core_dispatch_and_cache_write_contract(config, monkeypatch):
    plugin = VideoStoryboardPlugin(config)
    plugin.runtime.recognize_base64 = AsyncMock(return_value="分镜识别结果")
    bus = EventBus("core-video-test")
    bus.subscribe(
        EventType.ON_MEDIA_RECOGNIZE.value,
        VideoRecognizeHandler(plugin).execute,
        priority=100,
        timeout=0,
    )
    import src.core.managers.media_manager.recognition as recognition_module

    monkeypatch.setattr(recognition_module, "get_event_bus", lambda: bus)
    files = SimpleNamespace(
        save_to_pending=AsyncMock(return_value=Path("pending/v.mp4")),
        move_to_category_folder=AsyncMock(),
        category_folder_for=Mock(return_value=Path("videos")),
    )
    repository = SimpleNamespace(save_recognized_media=AsyncMock())
    cache = SimpleNamespace(get_cached_video_description=AsyncMock(return_value=None))
    recognition = MediaRecognition(files, repository, cache, Mock(), Mock())
    recognition._save_cache_and_update_media = AsyncMock()
    assert (
        await recognition.recognize_media(
            "base64-video", "video", stream_id="group-123"
        )
        == "分镜识别结果"
    )
    recognition._save_cache_and_update_media.assert_awaited_once()
    assert recognition._save_cache_and_update_media.call_args.args[1:3] == (
        "video",
        "分镜识别结果",
    )
    cache.get_cached_video_description.return_value = "缓存描述"
    assert await recognition.recognize_media("base64-video", "video") == "缓存描述"
    plugin.runtime.recognize_base64.assert_awaited_once()
    cache.get_cached_video_description.return_value = None
    assert (
        await recognition.recognize_media(
            "base64-video", "video", skip_recognition=True
        )
        is None
    )
    plugin.runtime.recognize_base64.assert_awaited_once()


def test_asr_isolation_and_explicit_configuration(config, tmp_path, monkeypatch):
    monkeypatch.setenv("DSH_ASR_KEY", "unrelated-secret")
    monkeypatch.setenv("MOFOX_VIDEO_BRIDGE_ASR_KEY", "also-unrelated")
    bridge = EngineBridge(config, tmp_path)
    env = bridge.environment()
    assert "DSH_ASR_KEY" not in env
    assert env["MOFOX_VIDEO_BRIDGE_ASR_KEY"] == ""
    assert env["MOFOX_VIDEO_ISOLATED"] == "1"
    config.asr.enabled = True
    with pytest.raises(ValueError, match="base_url"):
        bridge.environment()
    config.asr.base_url = "http://localhost:1234/v1"
    config.asr.model = "test-asr"
    monkeypatch.setenv(config.asr.key_env, "explicit-secret")
    assert bridge.environment()["MOFOX_VIDEO_BRIDGE_ASR_KEY"] == "explicit-secret"


@pytest.mark.parametrize("value", ["not-base64!", "", "data:video/mp4,AAAA"])
def test_invalid_media_rejected(config, value):
    with pytest.raises(ValueError):
        VideoRuntime(config)._store_base64(value)


@pytest.mark.asyncio
async def test_real_probe_storyboard_zoom_and_text_paging(config, video):
    runtime = VideoRuntime(config)
    try:
        await runtime.check_dependencies()
        probe = await runtime.run("probe", str(video))
        assert probe["info"]["duration"] == pytest.approx(4, abs=0.2)
        assert not probe["images"]
        board = await runtime.run(
            "storyboard", str(video), cells=4, sheets=1, analyze=False
        )
        assert len(board["images"]) == 1
        with PILImage.open(board["images"][0]) as image:
            assert image.format == "PNG" and image.width * image.height <= 200_000
        assert board["cells"][0]["t_start"] == 0
        assert board["cells"][-1]["t_end"] == pytest.approx(4, abs=0.2)
        assert any(1.5 < cut["t"] < 2.5 for cut in board["cuts"])
        text = await runtime.run(
            "storyboard",
            str(video),
            cells=4,
            sheets=1,
            textOnly=True,
            cellRange=[2, 3],
            analyze=False,
        )
        assert (
            not text["images"]
            and "cell 2" in text["text"]
            and "cell 1 (" not in text["text"]
        )
        zoom = await runtime.run(
            "zoom", str(video), **{"from": 1, "to": 3, "cells": 2, "analyze": False}
        )
        assert zoom["plan"]["adaptive"] is False
        assert len(zoom["images"]) == 1 and zoom["window"]["from"] == 1
    finally:
        await runtime.close()
    assert not runtime.bridge._processes


@pytest.mark.asyncio
async def test_base64_uses_stable_path_and_batch_covers_tail(config, video):
    runtime = VideoRuntime(config)
    raw = base64.b64encode(video.read_bytes()).decode("ascii")
    first = runtime._store_base64(raw)
    assert runtime._store_base64(f"data:video/mp4;base64,{raw}") == first
    assert runtime._store_base64(f"base64://{raw}") == first
    assert runtime._store_base64(f"base64|{raw}") == first
    result = await runtime.run("batch", str(video), step=10, analyze=False)
    assert result["windows"][0]["window"]["from"] == 0
    assert result["windows"][-1]["window"]["to"] == pytest.approx(4, abs=0.2)
    assert Path(result["timeline_path"]).is_file()
    await runtime.close()


@pytest.mark.asyncio
async def test_embedded_subtitles_without_audio(config, video, tmp_path):
    subtitle = tmp_path / "subtitles.srt"
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:01,900\n第一段红色。\n\n2\n00:00:02,000 --> 00:00:03,900\n第二段蓝色。\n",
        encoding="utf-8",
    )
    container = tmp_path / "subtitled.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-i",
            str(subtitle),
            "-map",
            "0:v",
            "-map",
            "1:s",
            "-c:v",
            "copy",
            "-c:s",
            "srt",
            str(container),
        ],
        check=True,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    runtime = VideoRuntime(config)
    result = await runtime.run(
        "storyboard", str(container), cells=4, sheets=1, textOnly=True, analyze=False
    )
    assert not result["info"]["hasAudio"] and result["info"]["hasSubtitle"]
    assert result["transcript"]["source"] == "subtitle"
    assert "第一段红色" in result["text"] and "第二段蓝色" in result["text"]
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        {"cells": 17},
        {"sheets": 5},
        {"from": 4},
        {"from": 2, "to": 1},
        {"pick": "invalid"},
    ],
)
async def test_bridge_rejects_invalid_options(config, video, options):
    runtime = VideoRuntime(config)
    with pytest.raises(RuntimeError):
        await runtime.run("storyboard", str(video), analyze=False, **options)
    assert not runtime.bridge._processes


@pytest.mark.asyncio
async def test_cancellation_terminates_engine_tree(config, video):
    bridge = EngineBridge(config, Path(config.runtime.data_dir))
    task = asyncio.create_task(
        bridge.call("storyboard", {"input": str(video), "cells": 16, "sheets": 4})
    )
    for _ in range(100):
        if bridge._processes:
            break
        await asyncio.sleep(0.02)
    assert bridge._processes
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not bridge._processes
    await bridge.close()


@pytest.mark.asyncio
async def test_unload_cancels_model_inference_and_queued_jobs(config, video):
    config.runtime.concurrency = 1
    runtime = VideoRuntime(config)
    entered = asyncio.Event()

    async def pending_inference(*args):
        entered.set()
        await asyncio.Event().wait()

    runtime.bridge.call = AsyncMock(
        return_value={"text": "test", "images": ["test.png"]}
    )
    runtime._analyze = pending_inference
    active = asyncio.create_task(runtime.run("storyboard", str(video)))
    await asyncio.wait_for(entered.wait(), 5)
    queued = asyncio.create_task(runtime.run("probe", str(video)))
    await asyncio.sleep(0)
    await runtime.close()
    assert active.cancelled() and queued.cancelled()
    assert runtime.bridge.closed and not runtime._calls


@pytest.mark.asyncio
async def test_resolve_media_id_and_disabled_plugin(config, video, monkeypatch):
    monkeypatch.setattr(
        runtime_module.media_api,
        "get_media_info",
        AsyncMock(return_value={"type": "video", "path": str(video)}),
    )
    runtime = VideoRuntime(config)
    assert await runtime.resolve_input("a" * 32) == video.resolve()
    config.plugin.enabled = False
    with pytest.raises(RuntimeError):
        await runtime.run("probe", str(video))


@pytest.mark.asyncio
async def test_received_video_reaches_model_database_cache_and_context(
    config, video, tmp_path, monkeypatch
):
    """Exercise real conversion, Node rendering, repositories and SQL caching."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import src.kernel.event as event_module
    import src.kernel.db.core.session as session_module
    from src.core.managers.media_manager import manager as manager_module
    from src.core.models.message import MessageType
    from src.core.models.sql_alchemy import Images, VideoDescriptions, Videos, Voices
    from src.core.transport.message_receive.converter import MessageConverter
    from src.kernel.db import reset_db_cache

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'media.sqlite3'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(session_module, "_session_factory", factory)
    reset_db_cache()
    async with engine.begin() as connection:
        await connection.run_sync(
            Videos.metadata.create_all,
            tables=[
                model.__table__ for model in (Images, Voices, Videos, VideoDescriptions)
            ],
        )

    bus = EventBus("received-video-integration")
    monkeypatch.setattr(event_module, "_event_bus", bus)
    folders = {
        f"{name}_folder": tmp_path / "framework-media" / name
        for name in ("pending", "images", "emojis", "voices", "videos")
    }
    for folder in folders.values():
        folder.mkdir(parents=True)
    media_config = SimpleNamespace(
        **folders, should_skip_recognition=lambda stream_id, media_type: False
    )
    monkeypatch.setattr(manager_module, "MediaConfig", lambda: media_config)
    manager = manager_module.MediaManager()
    monkeypatch.setattr(manager_module, "_media_manager", manager)

    # Stub only the external provider response. Actual PNG creation, LLM payload,
    # framework events, media storage, SQL writes and cached rereads stay real.
    class Response:
        message = "画面先红色，后蓝色。"

        def __await__(self):
            async def collect():
                return self

            return collect().__await__()

    request = SimpleNamespace(
        add_payload=Mock(), send=AsyncMock(return_value=Response())
    )
    selected = [{"model_identifier": "video-task-model"}]
    get_task = Mock(return_value=selected)
    create_request = Mock(return_value=request)
    monkeypatch.setattr(runtime_module.llm_api, "get_model_set_by_task", get_task)
    monkeypatch.setattr(runtime_module.llm_api, "create_llm_request", create_request)
    config.storyboard.prompt = "描述视频的颜色和先后变化。"
    config.storyboard.cells = 4
    config.storyboard.sheets = 1
    plugin = VideoStoryboardPlugin(config)
    bus.subscribe(
        EventType.ON_MEDIA_RECOGNIZE.value,
        VideoRecognizeHandler(plugin).execute,
        priority=100,
        timeout=0,
    )
    encoded = base64.b64encode(video.read_bytes()).decode("ascii")
    envelope = {
        "message_info": {
            "message_id": "synthetic-video-message",
            "platform": "qq",
            "user_info": {"user_id": "synthetic-user", "user_nickname": "test"},
        },
        "message_segment": {"type": "video", "data": encoded},
    }
    try:
        message = await MessageConverter().envelope_to_message(envelope)
        assert message.message_type == MessageType.VIDEO
        media_hash = manager.compute_media_hash(encoded)
        assert (
            message.processed_plain_text == f"[视频({media_hash}):{Response.message}]"
        )
        get_task.assert_called_once_with("video")
        assert create_request.call_args.args[0] is selected
        assert create_request.call_args.kwargs["stream_id"] == message.stream_id
        image_parts = [
            part
            for part in request.add_payload.call_args.args[0].content
            if isinstance(part, Image)
        ]
        assert len(image_parts) == 1
        async with factory() as session:
            stored = (await session.execute(select(Videos))).scalars().one()
            cached = (await session.execute(select(VideoDescriptions))).scalars().one()
        assert stored.video_id == media_hash
        assert stored.description == cached.description == Response.message
        assert stored.video_processed
        assert cached.video_description_hash == media_hash
        assert Path(stored.path).read_bytes() == video.read_bytes()
        assert (
            await plugin.runtime.resolve_input(media_hash)
            == Path(stored.path).resolve()
        )
        repeated = await MessageConverter().envelope_to_message(envelope)
        assert repeated.processed_plain_text == message.processed_plain_text
        request.send.assert_awaited_once()
        create_request.assert_called_once()
    finally:
        await plugin.runtime.close()
        await engine.dispose()
        reset_db_cache()
