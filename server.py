import http.server
import os
import socketserver
import threading
import time
import traceback

from fetch import main as run_fetch

PORT = int(os.environ.get("PORT", 8000))
FETCH_INTERVAL_HOURS = float(os.environ.get("FETCH_INTERVAL_HOURS", "12"))


def fetch_loop():
    interval = FETCH_INTERVAL_HOURS * 3600
    while True:
        time.sleep(interval)
        try:
            run_fetch()
        except Exception:
            print("[fetch_loop] fetch failed:")
            traceback.print_exc()


def main():
    try:
        run_fetch()
    except Exception:
        print("[startup] initial fetch failed:")
        traceback.print_exc()

    threading.Thread(target=fetch_loop, daemon=True).start()

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"Serving dashboard on :{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
