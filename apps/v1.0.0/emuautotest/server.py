import json
from pathlib import Path
from typing import List, Union

from mcp.server.mcpserver import MCPServer
import mcp.types as types

from emuautotest.adapters.azahar_3ds import Azahar3DSAdapter
from emuautotest.config import ROMS_DIR

server = MCPServer(
    name="Emuautotest",
    version="1.0.0",
    instructions=(
        "Emuautotest Nintendo 3DS Emulator Testbed for AI agents.\n"
        "Allows testing games, navigating menus, inspecting performance and RAM, "
        "and sending controller/touch inputs."
    ),
)

# Active adapter (default to Nintendo 3DS via Azahar)
adapter = Azahar3DSAdapter()


@server.tool(
    name="emulator_start",
    description="Start the Nintendo 3DS emulator with a given ROM. If rom_path is omitted, loads default 2048-3D homebrew.",
)
def emulator_start(rom_path: str = "") -> str:
    try:
        success = adapter.launch(rom_path if rom_path.strip() else None)
        status = adapter.get_status()
        if success:
            return (
                f"✅ Emulator started successfully!\n"
                f"PID: {status.pid}\n"
                f"ROM: {status.rom_path}\n"
                f"RPC Connected: {status.rpc_connected}\n"
                f"FPS: {status.game_fps}"
            )
        else:
            return "⚠️ Emulator started, but neither RPC nor window could be confirmed yet."
    except Exception as e:
        return f"❌ Failed to start emulator: {str(e)}"


@server.tool(
    name="emulator_stop",
    description="Stop the running emulator process.",
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
        if not ROMMS_DIR_EXISTS := ROMS_DIR.exists():
            return "No roms directory found."
        rom_files = [f.name for f in ROMS_DIR.iterdir() if f.suffix.lower() in [".3ds", ".3dsx", ".cia", ".cxi"]]
        if not rom_files:
            return f"No ROM files found in {ROMS_DIR}."
        return "Available ROMs:\n" + "\n".join(f"- {name} ({ROMS_DIR / name})" for name in rom_files)
    except Exception as e:
        return f"❌ Error listing ROMs: {str(e)}"
