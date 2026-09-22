import threading
import time

import uvicorn
import webview

from main import app


def run_server():
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    time.sleep(2)

    webview.create_window(
        title="Aroogula",
        url="http://127.0.0.1:8000",
        width=1450,
        height=900,
        resizable=True,
    )

    webview.start()