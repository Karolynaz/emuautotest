import enum
import random
import socket
import struct
from typing import Any, Dict, Optional, Tuple

CURRENT_REQUEST_VERSION = 2
MAX_REQUEST_DATA_SIZE = 32 * 1024
HEADER_SIZE = 0x10
MAX_PACKET_SIZE = MAX_REQUEST_DATA_SIZE + HEADER_SIZE


class RequestType(enum.IntEnum):
    ReadMemory = 1
    WriteMemory = 2
    ProcessList = 3
    SetGetProcess = 4
    TakeScreenshot = 5
    ReadScreenshot = 6
    GetPerfStats = 7


class ScreenshotResult(enum.IntEnum):
    Success = 0
    Unsupported = 1
    Busy = 2
    Timeout = 3
    EncodeFailed = 4
    InvalidArgument = 5


SCREENSHOT_FLAG_SECONDARY_WINDOW = 1 << 0
SCREENSHOT_FLAG_RAW_RGB = 1 << 1

PERF_STATS_FIELDS = (
    "system_fps",
    "game_fps",
    "time_vblank_interval",
    "time_hle_svc",
    "time_hle_ipc",
    "time_gpu",
    "time_swap",
    "time_remaining",
    "emulation_speed",
    "artic_transmitted",
    "artic_events",
)


class AzaharRPCClient:
    def __init__(self, address: str = "127.0.0.1", port: int = 45987, timeout: float = 2.0, retries: int = 3):
        self.address = address
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.max_data_size = MAX_REQUEST_DATA_SIZE
        self.socket: Optional[socket.socket] = None
        self._init_socket()

    def _init_socket(self) -> None:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for option in (socket.SO_SNDBUF, socket.SO_RCVBUF):
                if self.socket.getsockopt(socket.SOL_SOCKET, option) < MAX_PACKET_SIZE * 2:
                    self.socket.setsockopt(socket.SOL_SOCKET, option, MAX_PACKET_SIZE * 2)
        except Exception:
            self.socket = None

    def is_connected(self) -> bool:
        return self.socket is not None

    def _generate_header(self, request_type: int, data_size: int) -> Tuple[bytes, int]:
        request_id = random.getrandbits(32)
        header = struct.pack("IIII", CURRENT_REQUEST_VERSION, request_id, request_type, data_size)
        return header, request_id

    def _read_and_validate_header(self, raw_reply: bytes, expected_id: int, expected_type: int) -> Optional[bytes]:
        if len(raw_reply) < HEADER_SIZE:
            return None
        reply_version, reply_id, reply_type, reply_data_size = struct.unpack("IIII", raw_reply[:HEADER_SIZE])
        if (
            reply_version == CURRENT_REQUEST_VERSION
            and reply_id == expected_id
            and reply_type == expected_type
            and reply_data_size == len(raw_reply[HEADER_SIZE:])
        ):
            return raw_reply[HEADER_SIZE:]
        return None

    def _request(self, request_type: int, request_data: bytes, timeout: Optional[float] = None, resend: bool = True) -> bytes:
        if not self.socket:
            self._init_socket()
            if not self.socket:
                raise ConnectionError("Socket not initialized")

        effective_timeout = self.timeout if timeout is None else timeout
        attempts = self.retries + 1 if (effective_timeout is not None and resend) else 1
        request, request_id = self._generate_header(request_type, len(request_data))
        self.socket.settimeout(effective_timeout)

        for _ in range(attempts):
            self.socket.sendto(request + request_data, (self.address, self.port))
            try:
                while True:
                    raw_reply = self.socket.recv(MAX_PACKET_SIZE)
                    reply_data = self._read_and_validate_header(raw_reply, request_id, request_type)
                    if reply_data is not None:
                        return reply_data
            except socket.timeout:
                continue

        raise TimeoutError(f"No reply from Azahar RPC at {self.address}:{self.port} after {attempts} attempts")

    def ping(self) -> bool:
        """Check if emulator RPC server is reachable."""
        try:
            return self.perf_stats() is not None
        except Exception:
            return False

    def perf_stats(self, reset: bool = False) -> Optional[Dict[str, float]]:
        """Return emulator performance statistics."""
        try:
            reply_data = self._request(RequestType.GetPerfStats, struct.pack("II", 1 if reset else 0, 0))
            if len(reply_data) < 0x54:
                return None
            return dict(zip(PERF_STATS_FIELDS, struct.unpack("<10dI", reply_data[:0x54])))
        except Exception:
            return None

    def process_list(self) -> Dict[int, Tuple[int, str]]:
        """List active processes running in the emulator."""
        processes = {}
        read_processes = 0
        while True:
            reply_data = self._request(
                RequestType.ProcessList, struct.pack("II", read_processes, 0x7FFFFFFF)
            )
            if not reply_data:
                break
            read_count = struct.unpack("I", reply_data[0:4])[0]
            reply_data = reply_data[4:]
            if read_count == 0:
                break
            read_processes += read_count
            for i in range(read_count):
                proc_data = reply_data[i * 0x14 : (i + 1) * 0x14]
                proc_id, title_id, proc_name = struct.unpack("<IQ8s", proc_data)
                proc_name_str = proc_name.rstrip(b"\x00").decode("ascii", errors="replace")
                processes[proc_id] = (title_id, proc_name_str)
        return processes

    def _take_screenshot(self, res_scale: int, flags: int) -> Optional[Tuple[int, int, bytes]]:
        reply_timeout = max(self.timeout, 5.0) if self.timeout else 5.0
        reply_data = self._request(
            RequestType.TakeScreenshot,
            struct.pack("II", res_scale, flags),
            timeout=reply_timeout,
            resend=False,
        )
        if not reply_data:
            return None

        result, width, height, data_size = struct.unpack("IIII", reply_data[:16])
        if result != ScreenshotResult.Success:
            raise RuntimeError(f"Screenshot failed: {ScreenshotResult(result).name}")

        chunks = []
        received = 0
        while received < data_size:
            temp_read_size = min(data_size - received, self.max_data_size)
            reply_data = self._request(
                RequestType.ReadScreenshot,
                struct.pack("II", received, temp_read_size),
                timeout=reply_timeout,
            )
            if not reply_data:
                return None
            chunks.append(reply_data)
            received += len(reply_data)

        return width, height, b"".join(chunks)

    def screenshot_png(self, res_scale: int = 0, secondary_window: bool = False) -> bytes:
        """Capture the next frame directly from emulator rendering engine as PNG bytes."""
        flags = SCREENSHOT_FLAG_SECONDARY_WINDOW if secondary_window else 0
        result = self._take_screenshot(res_scale, flags)
        if result is None:
            raise RuntimeError("Screenshot request failed")
        return result[2]

    def read_memory(self, read_address: int, read_size: int) -> Optional[bytes]:
        """Read bytes from emulated 3DS memory."""
        result = bytearray()
        while read_size > 0:
            temp_read_size = min(read_size, self.max_data_size)
            reply_data = self._request(
                RequestType.ReadMemory, struct.pack("II", read_address, temp_read_size)
            )
            if reply_data:
                result += reply_data
                read_size -= len(reply_data)
                read_address += len(reply_data)
            else:
                return None
        return bytes(result)

    def write_memory(self, write_address: int, write_contents: bytes) -> bool:
        """Write bytes directly into emulated 3DS memory."""
        write_size = len(write_contents)
        while write_size > 0:
            temp_write_size = min(write_size, self.max_data_size - 8)
            request_data = struct.pack("II", write_address, temp_write_size) + write_contents[:temp_write_size]
            reply_data = self._request(RequestType.WriteMemory, request_data)
            if reply_data is not None:
                write_address += temp_write_size
                write_size -= temp_write_size
                write_contents = write_contents[temp_write_size:]
            else:
                return False
        return True

    def close(self) -> None:
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
