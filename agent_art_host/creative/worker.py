"""One warm browser owned by one local worker process; binary pixel transport."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
import traceback

import numpy as np
from playwright.sync_api import sync_playwright


def main():
    state = {}
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            prefix = "/transfer/input/"
            if self.path.startswith(prefix):
                key = self.path[len(prefix):]
                if key not in state.get("inputs", {}):
                    self.send_error(404)
                    return
                data = np.load(state["inputs"][key], allow_pickle=False).astype('<f4').tobytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                super().do_GET()

        def do_POST(self):
            index = self.path.removeprefix("/transfer/output/")
            if not self.path.startswith("/transfer/output/") or not index.isdigit():
                self.send_error(404)
                return
            expected = state["width"] * state["height"] * 16
            if int(self.headers.get("Content-Length", 0)) != expected:
                self.send_error(400)
                return
            data = self.rfile.read(expected)
            values = np.frombuffer(data, '<f4').reshape(state["height"], state["width"], 4)
            np.save(Path(state["directory"]) / f"frame-{int(index):04}.npy", values, allow_pickle=False)
            self.send_response(200)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(Path(__file__).resolve().parents[1])))
    Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True,
            args=["--enable-unsafe-webgpu", "--disable-background-timer-throttling"])
        page = browser.new_page()
        diagnostics = []
        page.on("console", lambda message: diagnostics.append(message.text) if message.type == "error" else None)
        page.goto(f"http://127.0.0.1:{server.server_port}/creative/worker.html")
        page.wait_for_function("typeof window.runArtProgram === 'function'")
        print(json.dumps({"ready": True}), flush=True)
        for line in sys.stdin:
            try:
                request = json.loads(line)
                diagnostics.clear()
                state.clear()
                state.update(request)
                job = {**request, "inputs": list(request["inputs"])}
                result = page.evaluate("async job => {try {return await window.runArtProgram(job)} catch(e) {throw new Error(e?.stack || JSON.stringify(e))}}", job)
                if diagnostics:
                    raise RuntimeError("\n".join(diagnostics))
                print(json.dumps({"result": result}), flush=True)
            except Exception:
                print(json.dumps({"error": traceback.format_exc()+"\n"+"\n".join(diagnostics)}), flush=True)
        browser.close()
    server.shutdown()


if __name__ == "__main__":
    main()
