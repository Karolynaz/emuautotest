import json
from pathlib import Path
from typing import List, Union

from mcp.server.mcpserver import MCPServer
import mcp.types as types

from emuautotest.adapters.azahar_3ds import Azahar3DSAdapter
from emuautotest.config import ROMS_DIR

server = MCPServer(
    name="Emuautotest",
    version="1.1.0",
    instructions=(
        "Emuautotest Nintendo 3DS Emulator Testbed for AI agents.\n"
        "Allows automated testing, menu navigation, video recording (MP4/GIF), "
        "RAM inspection, gamepad macros, and automatic startup game list population."
    ),
)

# Active adapter (default to Nintendo 3DS via Azahar / Emuautotest)
adapter = Azahar3DSAdapter()


@server.tool(
    name="emulator_start",
    description=(
        "Start the Nintendo 3DS emulator with a given ROM or open the main menu with recent games. "
        "If rom_path is omitted, loads default ROM. The initial window automatically displays "
        "the 5 most recently played games."
    ),
)
def emulator_start(rom_path: str = "") -> str:
    try:
        success = adapter.launch(rom_path if rom_path.strip() else None)
        status = adapter.get_status()
        if success:
            return (
                f"✅ Emulator started successfully!\n"
                f"PID: {status.pid}\n"
                f"ROM: {status.rom_path or 'Main Menu / Recent Games'}\n"
                f"RPC Connected: {status.rpc_connected}\n"
                f"FPS: {status.game_fps}"
            )
        else:
            return "⚠️ Emulator started, but neither RPC nor window could be confirmed yet."
    except Exception as e:
        return f"❌ Failed to start emulator: {str(e)}"


@server.tool(
    name="emulator_stop",
    description="Stop the running emulator process gracefully.",
)
def emulator_stop() -> str:
    try:
        adapter.stop()
        return "✅ Emulator stopped successfully."
    except Exception as e:
        return f"❌ Error stopping emulator: {str(e)}"


@server.tool(
    name="emulator_get_status",
    description="Get real-time emulator status including running state, FPS, speed, and window geometry.",
)
def emulator_get_status() -> str:
    try:
        status = adapter.get_status()
        bounds_str = "None"
        if status.window_bounds:
            b = status.window_bounds
            bounds_str = f"x={b.x}, y={b.y}, width={b.width}, height={b.height}"

        return (
            f"🎮 Emulator Status:\n"
            f"Running: {status.is_running}\n"
            f"PID: {status.pid}\n"
            f"ROM: {status.rom_path}\n"
            f"RPC Server: {'Connected' if status.rpc_connected else 'Disconnected'}\n"
            f"Game FPS: {status.game_fps}\n"
            f"System FPS: {status.system_fps}\n"
            f"Speed: {status.emulation_speed}%\n"
            f"Window: {bounds_str}"
        )
    except Exception as e:
        return f"❌ Error retrieving status: {str(e)}"


@server.tool(
    name="emulator_screenshot",
    description=(
        "Capture current screen from the 3DS emulator. "
        "target options: 'both' (dual-screen 400x480), 'top' (gameplay screen 400x240), or 'bottom' (touch screen 320x240)."
    ),
)
def emulator_screenshot(target: str = "both") -> List[Union[types.TextContent, types.ImageContent]]:
    try:
        _, b64, width, height = adapter.take_screenshot(target=target)
        return [
            types.ImageContent(
                type="image",
                data=b64,
                mimeType="image/png",
            ),
            types.TextContent(
                type="text",
                text=f"Screenshot taken: {width}x{height} px (target: {target})",
            ),
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ Failed to take screenshot: {str(e)}")]


@server.tool(
    name="emulator_press_button",
    description=(
        "Press a 3DS button for duration_ms milliseconds. "
        "Available buttons: 'A', 'B', 'X', 'Y', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'L', 'R', 'START', 'SELECT', 'HOME'."
    ),
)
def emulator_press_button(button: str, duration_ms: int = 100) -> str:
    try:
        adapter.press_button(button, duration_ms=duration_ms)
        return f"✅ Pressed button '{button.upper()}' for {duration_ms}ms"
    except Exception as e:
        return f"❌ Failed to press button '{button}': {str(e)}"


@server.tool(
    name="emulator_touch",
    description=(
        "Touch the 3DS bottom touchscreen. "
        "Coordinates x and y are normalized floats from 0.0 to 1.0 (0.0, 0.0 is top-left; 1.0, 1.0 is bottom-right)."
    ),
)
def emulator_touch(x: float, y: float, duration_ms: int = 100) -> str:
    try:
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return "❌ x and y must be normalized values between 0.0 and 1.0"
        adapter.touch_screen(x, y, duration_ms=duration_ms)
        return f"✅ Touched screen at ({x:.2f}, {y:.2f}) for {duration_ms}ms"
    except Exception as e:
        return f"❌ Touch failed: {str(e)}"


@server.tool(
    name="emulator_circle_pad",
    description=(
        "Move the analog Circle Pad in a direction ('UP', 'DOWN', 'LEFT', 'RIGHT', 'UP_LEFT', 'UP_RIGHT', 'DOWN_LEFT', 'DOWN_RIGHT') "
        "for duration_ms milliseconds."
    ),
)
def emulator_circle_pad(direction: str, duration_ms: int = 200) -> str:
    try:
        adapter.circle_pad(direction, duration_ms=duration_ms)
        return f"✅ Circle Pad moved '{direction.upper()}' for {duration_ms}ms"
    except Exception as e:
        return f"❌ Circle Pad failed: {str(e)}"


@server.tool(
    name="emulator_macro",
    description=(
        "Execute a batch sequence of actions with delays to quickly navigate menus or test workflows. "
        "Input is a JSON array string. Example: "
        "'[{\"action\": \"press\", \"button\": \"DOWN\", \"duration_ms\": 100}, "
        "{\"action\": \"wait\", \"duration_ms\": 200}, "
        "{\"action\": \"press\", \"button\": \"A\"}, "
        "{\"action\": \"screenshot\", \"screen\": \"both\"}]'"
    ),
)
def emulator_macro(actions_json: str) -> List[Union[types.TextContent, types.ImageContent]]:
    try:
        actions = json.loads(actions_json)
        if not isinstance(actions, list):
            return [types.TextContent(type="text", text="❌ actions_json must be a JSON array")]

        results = adapter.execute_macro(actions)

        # Look for any screenshot taken in macro
        out: List[Union[types.TextContent, types.ImageContent]] = []
        for r in results:
            if "screenshot" in r:
                sc = r.pop("screenshot")
                out.append(
                    types.ImageContent(
                        type="image",
                        data=sc["base64"],
                        mimeType="image/png",
                    )
                )

        summary_text = "Macro Results:\n" + json.dumps(results, indent=2)
        out.append(types.TextContent(type="text", text=summary_text))
        return out
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ Macro execution failed: {str(e)}")]


@server.tool(
    name="emulator_read_memory",
    description="Read memory bytes directly from 3DS RAM via RPC. hex_address like '0x100000', size in bytes.",
)
def emulator_read_memory(hex_address: str, size: int = 16) -> str:
    try:
        addr = int(hex_address, 16)
        data = adapter.read_memory(addr, size)
        if data is None:
            return f"❌ Memory read failed at {hex_address}"
        return f"Memory at {hex_address} ({size} bytes): {data.hex()}"
    except Exception as e:
        return f"❌ Memory read error: {str(e)}"


@server.tool(
    name="emulator_list_roms",
    description="List all available 3DS ROM files in the roms directory.",
)
def emulator_list_roms() -> str:
    try:
        if not ROMS_DIR.exists():
            return "No roms directory found."
        rom_files = [f.name for f in ROMS_DIR.iterdir() if f.suffix.lower() in [".3ds", ".3dsx", ".cia", ".cxi"]]
        if not rom_files:
            return f"No ROM files found in {ROMS_DIR}."
        return "Available ROMs:\n" + "\n".join(f"- {name} ({ROMS_DIR / name})" for name in rom_files)
    except Exception as e:
        return f"❌ Error listing ROMs: {str(e)}"


@server.tool(
    name="emulator_sync_recent_games",
    description=(
        "Synchronize the 5 most recently launched games so they appear immediately in the emulator startup window list, "
        "eliminating the need to click 'Failai > Neseniai įkrauti failai'. Optional active_rom parameter."
    ),
)
def emulator_sync_recent_games(active_rom: str = "") -> str:
    try:
        target = Path(active_rom).resolve() if active_rom.strip() else None
        top_roms = adapter.sync_recent_games(active_rom=target)
        lines = [f"✅ Successfully synchronized {len(top_roms)} recent games to startup window:"]
        for idx, r in enumerate(top_roms, 1):
            lines.append(f"{idx}. {Path(r).name} ({r})")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to sync recent games: {str(e)}"


@server.tool(
    name="emulator_record_start",
    description=(
        "Start recording gameplay video in the background. "
        "target: 'both' (dual-screen 400x480), 'top' (gameplay screen 400x240), or 'bottom' (touch screen 320x240). "
        "format: 'mp4' (H.264 standard video) or 'gif' (high quality animated GIF). "
        "fps: framerate (e.g. 15, 30, 60). "
        "scale: integer pixel scaling (1 for native, 2 for 2x crisp upscale). "
        "duration_seconds: optional auto-stop duration in seconds (0 for continuous background recording until stopped). "
        "output_path: optional custom file path. If omitted, saves to recordings/ directory."
    ),
)
def emulator_record_start(
    target: str = "both",
    fps: int = 30,
    format: str = "mp4",
    scale: int = 1,
    duration_seconds: float = 0.0,
    output_path: str = "",
) -> str:
    try:
        max_dur = duration_seconds if duration_seconds > 0 else None
        out = output_path.strip() if output_path.strip() else None
        res = adapter.start_recording(
            target=target,
            fps=fps,
            format=format,
            scale=scale,
            output_path=out,
            max_duration=max_dur,
        )
        return (
            f"🎬 Video recording started in background!\n"
            f"File: {res['file_name']}\n"
            f"Full Path: {res['file_path']}\n"
            f"Target: {res['target']} | Format: {res['format'].upper()} | FPS: {res['fps']} | Scale: {res['scale']}x\n"
            f"Auto-stop: {f'{duration_seconds}s' if max_dur else 'Continuous (call emulator_record_stop to finish)'}"
        )
    except Exception as e:
        return f"❌ Failed to start recording: {str(e)}"


@server.tool(
    name="emulator_record_stop",
    description="Stop the active video recording session and finalize the MP4/GIF file.",
)
def emulator_record_stop() -> str:
    try:
        res = adapter.stop_recording()
        return (
            f"✅ Video recording finalized successfully!\n"
            f"File: {res['file_name']}\n"
            f"Path: {res['file_path']}\n"
            f"Duration: {res['duration_seconds']}s\n"
            f"Frames: {res['frame_count']} ({res['fps']} FPS)\n"
            f"Size: {res['file_size_human']} ({res['file_size_bytes']} bytes)\n"
            f"Format: {res['format'].upper()}"
        )
    except Exception as e:
        return f"❌ Failed to stop recording: {str(e)}"


@server.tool(
    name="emulator_record_status",
    description="Get current status of active gameplay video recording.",
)
def emulator_record_status() -> str:
    try:
        st = adapter.get_recording_status()
        if not st.get("is_recording"):
            return "⏹️ No video recording currently active."
        return (
            f"🔴 Video Recording In Progress:\n"
            f"File: {st['file_name']}\n"
            f"Path: {st['file_path']}\n"
            f"Elapsed: {st['elapsed_seconds']}s\n"
            f"Frames Captured: {st['frame_count']}\n"
            f"Target: {st['target']} | Format: {st['format']} | FPS: {st['fps']} | Scale: {st['scale']}x"
        )
    except Exception as e:
        return f"❌ Failed to get recording status: {str(e)}"


@server.tool(
    name="emulator_record_clip",
    description=(
        "Synchronously record a gameplay clip of specified duration (e.g. 5 seconds) and export it. "
        "Blocks until recording finishes and returns file details."
    ),
)
def emulator_record_clip(
    duration_seconds: float = 5.0,
    target: str = "both",
    fps: int = 30,
    format: str = "mp4",
    scale: int = 1,
    output_path: str = "",
) -> str:
    try:
        out = output_path.strip() if output_path.strip() else None
        res = adapter.record_clip(
            duration_seconds=duration_seconds,
            target=target,
            fps=fps,
            format=format,
            scale=scale,
            output_path=out,
        )
        return (
            f"🎥 Gameplay clip recorded and exported!\n"
            f"File: {res['file_name']}\n"
            f"Path: {res['file_path']}\n"
            f"Duration: {res['duration_seconds']}s\n"
            f"Frames: {res['frame_count']} ({res['fps']} FPS)\n"
            f"Size: {res['file_size_human']}\n"
            f"Format: {res['format'].upper()}"
        )
    except Exception as e:
        return f"❌ Failed to record clip: {str(e)}"


@server.tool(
    name="emulator_list_recordings",
    description="List all recorded gameplay video and GIF files saved in the recordings folder.",
)
def emulator_list_recordings() -> str:
    try:
        recs = adapter.list_recordings()
        if not recs:
            return "No recordings found in recordings/ directory."
        lines = [f"📁 Recorded Gameplay Files ({len(recs)} total):"]
        for r in recs:
            lines.append(
                f"- {r['file_name']} [{r['format'].upper()}, {r['size_human']}, modified: {r['modified_at']}]\n"
                f"  Path: {r['file_path']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to list recordings: {str(e)}"
