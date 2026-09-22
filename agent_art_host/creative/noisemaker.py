"""Own the external worker lifetime, including cancellation and crash recovery."""
import atexit
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
from threading import Lock, Thread
import time


class Noisemaker:
    def __init__(self):
        self.process = None
        self.lock = Lock()
        self.messages = Queue()
        atexit.register(self.close)

    def close(self):
        process, self.process = self.process, None
        if process and process.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            else:
                import signal
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        if process:
            process.stdin.close()
            process.stdout.close()

    def receive(self, deadline, check):
        while time.monotonic() < deadline:
            check()
            try:
                message = self.messages.get(timeout=0.05)
                if message is None:
                    raise RuntimeError("Noisemaker worker exited; next invocation will restart it")
                return message
            except Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(f"Noisemaker worker exited with {self.process.returncode}")
        raise TimeoutError("Noisemaker operation timed out")

    def run(self, job, check=lambda: None, timeout=120):
        while not self.lock.acquire(timeout=0.05):
            check()
        try:
            deadline = time.monotonic() + timeout
            if not self.process or self.process.poll() is not None:
                self.close()
                self.messages = Queue()
                self.process = subprocess.Popen([sys.executable, "-m", "agent_art_host.creative.worker"],
                    cwd=Path(__file__).resolve().parents[2], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=None, text=True, encoding="utf-8", bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    start_new_session=os.name != "nt")
                process, queue = self.process, self.messages
                def reader():
                    for line in process.stdout:
                        try:
                            queue.put(json.loads(line))
                        except json.JSONDecodeError:
                            queue.put({"error": f"Unexpected worker output: {line[:500]}"})
                    queue.put(None)
                Thread(target=reader, daemon=True).start()
                ready = self.receive(deadline, check)
                if not ready.get("ready"):
                    raise RuntimeError(str(ready))
            self.process.stdin.write(json.dumps(job) + "\n")
            self.process.stdin.flush()
            reply = self.receive(deadline, check)
            if "error" in reply:
                raise RuntimeError(reply["error"])
            return reply["result"]
        except BaseException:
            self.close()
            raise
        finally:
            self.lock.release()


# Owns one process, not cached artwork; requests are serialized and cancellable.
worker = Noisemaker()
