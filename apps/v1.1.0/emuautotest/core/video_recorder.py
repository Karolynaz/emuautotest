import datetime
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

from emuautotest.config import RECORDINGS_DIR


def find_ffmpeg() -> str:
    """Find system ffmpeg executable path."""
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path

    common_paths = [
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p

    raise RuntimeError(
        "FFmpeg is not installed or not found in PATH. "
        "Please install it using 'brew install ffmpeg' on macOS."
    )


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


class VideoRecorder:
    """
    Manages high-performance real-time video and GIF recordings of gameplay.
    Streams native in-engine or window frames directly into FFmpeg.
    """

    def __init__(self, frame_provider: Callable[[], bytes]):
        self.frame_provider = frame_provider
        self.ffmpeg_bin = find_ffmpeg()

        self._active_session: Optional[Dict[str, Any]] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def is_recording(self) -> bool:
        with self._lock:
            return self._active_session is not None and not self._stop_event.is_set()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            if not self._active_session:
                return {"is_recording": False}

            elapsed = time.monotonic() - self._active_session["start_monotonic"]
            return {
                "is_recording": True,
                "file_path": str(self._active_session["output_path"]),
                "file_name": self._active_session["output_path"].name,
                "target": self._active_session["target"],
                "fps": self._active_session["fps"],
                "scale": self._active_session["scale"],
                "format": self._active_session["format"],
                "elapsed_seconds": round(elapsed, 2),
                "frame_count": self._active_session["frame_count"],
            }

    def start(
        self,
        target: str = "both",
        fps: int = 30,
        format: str = "mp4",
        scale: int = 1,
        output_path: Optional[Union[str, Path]] = None,
        max_duration: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Start recording in a background thread.
        - target: 'both' (400x480 dual-screen), 'top' (400x240 gameplay), 'bottom' (320x240 touchscreen)
        - fps: frame rate (15, 30, 60)
        - format: 'mp4' (H.264 standard video) or 'gif' (high-quality animated GIF)
        - scale: pixel-perfect upscale factor (e.g. 1, 2 for 2x nearest-neighbor)
        - output_path: optional path. Defaults to recordings/gameplay_YYYYMMDD_HHMMSS.<fmt>
        - max_duration: optional auto-stop duration in seconds
        """
        with self._lock:
            if self._active_session is not None and not self._stop_event.is_set():
                raise RuntimeError("A recording session is already active. Call stop() first.")

            # Prepare output destination
            fmt = format.lower().strip()
            if fmt not in ["mp4", "gif", "mkv", "mov", "webm"]:
                fmt = "mp4"

            if output_path:
                out_path = Path(output_path).resolve()
            else:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = RECORDINGS_DIR / f"gameplay_{target}_{timestamp}.{fmt}"

            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Build FFmpeg command & filter chain
            vf_filters: List[str] = []
            target_clean = target.lower().strip()
            if target_clean == "top":
                vf_filters.append("crop=400:240:0:0")
            elif target_clean == "bottom":
                vf_filters.append("crop=320:240:40:240")

            if scale > 1:
                vf_filters.append(f"scale=iw*{scale}:ih*{scale}:flags=neighbor")

            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-f", "image2pipe",
                "-vcodec", "png",
                "-r", str(fps),
                "-i", "-",
            ]

            if fmt == "gif":
                # High-fidelity palette generation for pixel art
                filter_chain = ",".join(vf_filters) if vf_filters else "fps=" + str(fps)
                gif_vf = f"{filter_chain},split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3"
                cmd.extend(["-vf", gif_vf])
            else:
                # MP4 / H.264
                if vf_filters:
                    cmd.extend(["-vf", ",".join(vf_filters)])
                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                ])

            cmd.append(str(out_path))

            # Spawn FFmpeg process
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except Exception as e:
                raise RuntimeError(f"Failed to spawn FFmpeg process: {e}")

            self._stop_event.clear()
            self._active_session = {
                "process": proc,
                "output_path": out_path,
                "target": target_clean,
                "fps": fps,
                "scale": scale,
                "format": fmt,
                "max_duration": max_duration,
                "start_monotonic": time.monotonic(),
                "frame_count": 0,
                "error": None,
            }

            self._thread = threading.Thread(
                target=self._record_worker,
                daemon=True,
                name="Emuautotest-VideoRecorder",
            )
            self._thread.start()

            return {
                "status": "recording_started",
                "file_path": str(out_path),
                "file_name": out_path.name,
                "target": target_clean,
                "fps": fps,
                "format": fmt,
                "scale": scale,
                "max_duration": max_duration,
            }

    def _record_worker(self) -> None:
        """Background worker thread feeding PNG frames to FFmpeg."""
        session = self._active_session
        if not session:
            return

        proc: subprocess.Popen = session["process"]
        fps = session["fps"]
        frame_interval = 1.0 / fps
        max_dur = session["max_duration"]
        start_mono = session["start_monotonic"]
        frame_idx = 0

        while not self._stop_event.is_set():
            now = time.monotonic()
            elapsed = now - start_mono

            if max_dur and elapsed >= max_dur:
                break

            if proc.poll() is not None:
                # Process terminated unexpectedly
                _, err = proc.communicate()
                session["error"] = err.decode(errors="replace") if err else "FFmpeg exited unexpectedly"
                break

            # Fetch frame
            try:
                png_bytes = self.frame_provider()
                if png_bytes and proc.stdin:
                    proc.stdin.write(png_bytes)
                    proc.stdin.flush()
                    frame_idx += 1
                    session["frame_count"] = frame_idx
            except Exception as e:
                # Tolerate occasional RPC jitter
                time.sleep(0.01)

            # Compute next frame deadline to prevent framerate drift
            next_deadline = start_mono + (frame_idx + 1) * frame_interval
            sleep_time = next_deadline - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self) -> Dict[str, Any]:
        """Stop current recording session, finalize file, and return metadata."""
        with self._lock:
            if not self._active_session:
                raise RuntimeError("No active recording session to stop.")

            session = self._active_session
            proc: subprocess.Popen = session["process"]
            out_path: Path = session["output_path"]

            self._stop_event.set()

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        # Close stdin to allow FFmpeg to finish encoding
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass

        duration = time.monotonic() - session["start_monotonic"]
        frame_count = session["frame_count"]
        size_bytes = out_path.stat().st_size if out_path.exists() else 0

        result = {
            "status": "recording_stopped",
            "file_path": str(out_path),
            "file_name": out_path.name,
            "target": session["target"],
            "format": session["format"],
            "fps": session["fps"],
            "scale": session["scale"],
            "duration_seconds": round(duration, 2),
            "frame_count": frame_count,
            "file_size_bytes": size_bytes,
            "file_size_human": format_bytes(size_bytes),
            "error": session.get("error"),
        }

        with self._lock:
            self._active_session = None

        return result

    def record_clip(
        self,
        duration_seconds: float = 5.0,
        target: str = "both",
        fps: int = 30,
        format: str = "mp4",
        scale: int = 1,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Synchronously record a clip for a fixed duration."""
        self.start(
            target=target,
            fps=fps,
            format=format,
            scale=scale,
            output_path=output_path,
            max_duration=duration_seconds,
        )

        time.sleep(duration_seconds)
        return self.stop()

    @staticmethod
    def list_saved_recordings() -> List[Dict[str, Any]]:
        """List all video and GIF recordings saved in RECORDINGS_DIR."""
        if not RECORDINGS_DIR.exists():
            return []

        extensions = {".mp4", ".gif", ".mov", ".mkv", ".webm"}
        recordings = []

        for p in RECORDINGS_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in extensions:
                stat = p.stat()
                recordings.append({
                    "file_name": p.name,
                    "file_path": str(p),
                    "format": p.suffix.lower().lstrip("."),
                    "size_bytes": stat.st_size,
                    "size_human": format_bytes(stat.st_size),
                    "created_at": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        # Sort newest first
        recordings.sort(key=lambda x: x["modified_at"], reverse=True)
        return recordings
