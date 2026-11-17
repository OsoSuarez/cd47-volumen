"""
Servidor local para el boton "Ejecutar bot" del tablero.
Escucha solo en 127.0.0.1:9748 y solo sabe hacer una cosa: lanzar run_planes.py.

Uso: python fountain9/servidor_bot.py   (o doble clic en servidor_bot.bat)
"""
import http.server, json, os, pathlib, shutil, subprocess, sys, tempfile, threading, time, urllib.parse

PORT = 9748
REPO_URL = os.environ.get("TRV_REPO", "https://github.com/OsoSuarez/cd47-volumen.git")
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


def publicar_tr(payload):
    """Mezcla el TR de un dia en trv.json y lo sube al repo (clon temporal, igual que el bot con base.json)."""
    fecha = str(payload["fecha"])
    T = payload["T"]
    if not (len(fecha) == 10 and isinstance(T, dict) and T.get("rows")):
        raise ValueError("TR invalido")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="trv_pub_"))
    try:
        g = lambda *a, **k: subprocess.run(["git", "-C", str(tmp), *a], check=True, capture_output=True, text=True, **k)
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(tmp)], check=True, capture_output=True, text=True)
        g("config", "user.email", "jorge.suarez@rappi.com")
        g("config", "user.name", "Jorge Suarez")
        f = tmp / "trv.json"
        base = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"tr": {}, "names": {}}
        T = dict(T)
        T.pop("pub", None)
        T["at"] = int(time.time() * 1000)
        base.setdefault("tr", {})[fecha] = T
        base.setdefault("names", {}).update({str(k): v for k, v in (payload.get("names") or {}).items()})
        lim = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 45 * 86400))
        base["tr"] = {d: v for d, v in base["tr"].items() if d >= lim}
        f.write_text(json.dumps(base, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        g("add", "trv.json")
        if not g("diff", "--cached", "--stat").stdout.strip():
            return {"ok": True, "cambio": False}
        g("commit", "-m", f"TR real {fecha}: publicar Detalle de TRs (trv.json)")
        try:
            g("push")
        except subprocess.CalledProcessError:
            g("pull", "--rebase")
            g("push")
        return {"ok": True, "cambio": True, "fecha": fecha, "filas": len(T["rows"]) // 5}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if self.headers.get("Origin", "") not in ORIGENES:
            return self._json({"error": "origen no permitido"}, 403)
        if u.path != "/publicar-tr":
            return self._json({"error": "no existe"}, 404)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > 60_000_000:
                return self._json({"error": "tamano invalido"}, 400)
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
            return self._json(publicar_tr(payload))
        except subprocess.CalledProcessError as e:
            return self._json({"ok": False, "error": (e.stderr or str(e))[-400:]}, 500)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

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
