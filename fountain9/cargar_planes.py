"""
cargar_planes.py — sirve los filtrado_secos y filtrado_ryc más recientes
en un servidor local y abre el dashboard para que los descargue automáticamente.

Uso:
    python fountain9/cargar_planes.py

El servidor corre en http://localhost:9747/ y se apaga solo después de que
el dashboard descargó los archivos (o tras 5 minutos de inactividad).
"""

import pathlib, sys, threading, time, json, urllib.parse
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DESCARGAS     = pathlib.Path(__file__).parent.parent / "descargas"
DASHBOARD_URL = "https://ososuarez.github.io/cd47-volumen/"
PORT          = 9747
TIMEOUT_S     = 300   # apagar el servidor tras 5 min si no descargó
GRACIA_S      = 30    # espera corta a la confirmación del dashboard ya entregados los archivos

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

    downloads_done = threading.Event()   # el dashboard confirmó con /done
    todo_entregado = threading.Event()   # ya se enviaron todos los archivos
    entregados     = set()
    lock           = threading.Lock()

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
                with lock:
                    entregados.add(key)
                    if entregados >= set(files_map):
                        todo_entregado.set()

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

    server = ThreadingHTTPServer(("localhost", PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"🌐  Servidor local en http://localhost:{PORT}/  (se apaga solo al terminar)")

    print(f"▶️   Abrí el dashboard y hacé clic en 'Cargar últimos planes': {DASHBOARD_URL}")
    print("⏳  Esperando que el dashboard descargue los archivos…")
    # El trabajo del servidor termina cuando entregó los archivos. El /done del
    # dashboard llega recién después de parsear y dibujar, así que se espera un
    # rato corto por la confirmación y no se trata su ausencia como un error.
    entregado = todo_entregado.wait(timeout=TIMEOUT_S)
    confirmado = downloads_done.wait(timeout=GRACIA_S) if entregado else False
    server.shutdown()
    if confirmado:
        print(f"\n🎉  ¡Listo! Planes cargados en el dashboard. Timestamp: {ts_now}")
    elif entregado:
        print(f"\n🎉  Archivos entregados. El dashboard los está procesando. Timestamp: {ts_now}")
    else:
        print("\n⚠️  Tiempo de espera agotado. Verificá que el dashboard esté abierto")
        print("    y que hayas hecho clic en 'Cargar últimos planes'.")

if __name__ == "__main__":
    main()
