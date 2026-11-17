"""
Servidor local para el boton "Ejecutar bot" del tablero.
Escucha solo en 127.0.0.1:9748 y solo sabe hacer una cosa: lanzar run_planes.py.

Uso: python fountain9/servidor_bot.py   (o doble clic en servidor_bot.bat)
"""
import http.server, json, os, pathlib, subprocess, sys, threading, time, urllib.parse

PORT = 9748
RAIZ = pathlib.Path(__file__).resolve().parent.parent
ORIGENES = {"https://ososuarez.github.io", "http://localhost", "http://127.0.0.1"}
estado = {"running": False, "modo": None, "inicio": None, "fin": None, "rc": None}
lock = threading.Lock()


def lanzar(modo):
    env = os.environ.copy()
    env.setdefault("F9_HEADLESS", "0")
    env.setdefault("F9_CHANNEL", "chrome")
    env.setdefault("F9_PERFIL", str(pathlib.Path.home() / "f9_perfil"))
    if modo == "bajar":
        env["F9_SOLO_BAJAR"] = "1"
    else:
        env.pop("F9_SOLO_BAJAR", None)
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    p = subprocess.Popen([sys.executable, str(RAIZ / "fountain9" / "run_planes.py")], cwd=str(RAIZ), env=env, creationflags=flags)

    def esperar():
        rc = p.wait()
        with lock:
            estado.update(running=False, fin=time.time(), rc=rc)
    threading.Thread(target=esperar, daemon=True).start()


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        o = self.headers.get("Origin", "")
        if o in ORIGENES:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Vary", "Origin")

    def _json(self, d, code=200):
        b = json.dumps(d).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if self.headers.get("Origin", "") not in ORIGENES and self.headers.get("Origin"):
            return self._json({"error": "origen no permitido"}, 403)
        if u.path == "/ping":
            return self._json({"ok": True})
        if u.path == "/status":
            with lock:
                return self._json(dict(estado))
        if u.path == "/run":
            if self.headers.get("Origin", "") not in ORIGENES:
                return self._json({"error": "origen no permitido"}, 403)
            modo = urllib.parse.parse_qs(u.query).get("modo", ["completo"])[0]
            if modo not in ("completo", "bajar"):
                return self._json({"error": "modo invalido"}, 400)
            with lock:
                if estado["running"]:
                    return self._json({"started": False, "motivo": "ya esta corriendo", **estado})
                estado.update(running=True, modo=modo, inicio=time.time(), fin=None, rc=None)
            try:
                lanzar(modo)
            except Exception as e:
                with lock:
                    estado.update(running=False, rc=-1)
                return self._json({"started": False, "motivo": str(e)}, 500)
            return self._json({"started": True, "modo": modo})
        self._json({"error": "no existe"}, 404)


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Servidor del bot escuchando en 127.0.0.1:{PORT}. Dejá esta ventana abierta (o minimizada).")
    srv.serve_forever()
