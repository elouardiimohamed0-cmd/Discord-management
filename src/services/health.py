from future import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from src.core.logging import get_logger
logger = get_logger(name)
class HealthHandler(BaseHTTPRequestHandler):
def do_GET(self) -> None:
self.send_response(200)
self.send_header("Content-Type", "text/plain")
self.end_headers()
self.wfile.write(b"OK")
def log_message(self, format: str, *args: object) -> None:
return
def start_health_server(port: int) -> None:
server = HTTPServer(("0.0.0.0", port), HealthHandler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
logger.info("Health server started on port %s", port)
