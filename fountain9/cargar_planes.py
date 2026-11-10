"""
cargar_planes.py — sirve los filtrado_secos y filtrado_ryc más recientes
en un servidor local y abre el dashboard para que los descargue automáticamente.

Uso:
    python fountain9/cargar_planes.py

El servidor corre en http://localhost:9747/ y se apaga solo después de que
el dashboard descargó los archivos (o tras 5 minutos de inactividad).
"""

import pathlib, sys, threading, time, subprocess, json, urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

DESCARGAS     = pathlib.Path(__file__).parent.parent / "descargas"
DASHBOARD_URL = "https://ososuarez.github.io/cd47-volumen/"
PORT          = 9747
TIMEOUT_S     = 300   # apagar el servidor tras 5 min si no descargó

def latest(pattern):
    files = sorted(DESCARGAS.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None

def main():
    secos = latest("filtrado_secos_*.csv")
    ryc   = latest("filtrado_ryc_*.csv")

    if not secos or not ryc:
        print("❌  No se encontraron archivos filtrado_secos_*.csv o filtrado_ryc_*.csv")
        print(f"   Buscando en: {DESCARGAS}")
        sys.exit(1)

    print(f"📂  Secos : {secos.name}  ({secos.stat().st_size/1e6:.1f} MB)")
    print(f"📂  RyC   : {ryc.name}  ({ryc.stat().st_size/1e6:.1f} MB)")

    ts_now    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    files_map = {
        "secos": secos,
        "ryc":   ryc,
    }
    manifest = {
        "ts":    ts_now,
        "files": [
            {"key": "secos", "name": secos.name, "url": f"http://localhost:{PORT}/file/secos"},
            {"key": "ryc",   "name": ryc.name,   "url": f"http://localhost:{PORT}/file/ryc"},
        ]
    }

    downloads_done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silenciar logs HTTP

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path

            # CORS para que el dashboard (github.io) pueda leer
            if path == "/manifest":
                body = json.dumps(manifest).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            elif path.startswith("/file/"):
                key = path.split("/file/")[-1]
                f   = files_map.get(key)
                if not f or not f.exists():
                    self.send_response(404); self.end_headers(); return
                size = f.stat().st_size
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Length", str(size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
                self.end_headers()
                with open(f, "rb") as fh:
                    while chunk := fh.read(1 << 20):
                        self.wfile.write(chunk)
                print(f"✅  Enviado: {f.name}")

            elif path == "/done":
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                downloads_done.set()

            else:
                self.send_response(404); self.end_headers()

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.end_headers()

    server = HTTPServer(("localhost", PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"🌐  Servidor local en http://localhost:{PORT}/  (se apaga solo al terminar)")

    # URL del dashboard con parámetro para disparar la carga automática
    dashboard = DASHBOARD_URL + f"?autoload={PORT}&ts={urllib.parse.quote(ts_now)}"

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    chrome = next((p for p in chrome_paths if pathlib.Path(p).exists()), None)
    if chrome:
        subprocess.Popen([chrome, dashboard])
    else:
        import webbrowser
        webbrowser.open(dashboard)

    print("⏳  Esperando que el dashboard descargue los archivos…")
    done = downloads_done.wait(timeout=TIMEOUT_S)
    server.shutdown()
    if done:
        print(f"\n🎉  ¡Listo! Planes cargados en el dashboard. Timestamp: {ts_now}")
    else:
        print("\n⚠️  Tiempo de espera agotado. Verificá que el dashboard esté abierto.")

if __name__ == "__main__":
    main()
