"""
cargar_planes.py — carga los filtrado_secos y filtrado_ryc más recientes
en el dashboard (ososuarez.github.io/cd47-volumen/) via localStorage.

Uso:
    python fountain9/cargar_planes.py

Requiere: Google Chrome instalado en la ruta estándar de Windows.
"""

import base64, json, pathlib, subprocess, sys, tempfile, textwrap, time
from datetime import datetime

DASHBOARD_URL = "https://ososuarez.github.io/cd47-volumen/"
DESCARGAS     = pathlib.Path(__file__).parent.parent / "descargas"
MAX_BYTES     = 50 * 1024 * 1024   # 50 MB por archivo — avisa si es más grande

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

    for f in (secos, ryc):
        if f.stat().st_size > MAX_BYTES:
            print(f"⚠️  {f.name} pesa {f.stat().st_size/1e6:.0f} MB — puede tardar unos segundos en cargar.")

    # Leer y encodear
    print("⏳  Leyendo archivos...")
    secos_b64 = base64.b64encode(secos.read_bytes()).decode()
    ryc_b64   = base64.b64encode(ryc.read_bytes()).decode()

    ts_now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    payload = json.dumps({
        "files": [
            {"name": secos.name, "b64": secos_b64},
            {"name": ryc.name,   "b64": ryc_b64},
        ],
        "ts": ts_now,
    })

    # HTML de puente: escribe en localStorage y redirige al dashboard
    bridge_html = textwrap.dedent(f"""\
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Cargando planes…</title></head>
        <body style="background:#0d0f13;color:#7dd3fc;font-family:monospace;padding:40px;font-size:1rem">
        <p>⏳ Cargando planes en el dashboard…</p>
        <script>
        try {{
          const payload = {json.dumps(payload)};
          const data = JSON.parse(payload);
          localStorage.setItem('cd47_autoload', payload);
          localStorage.setItem('cd47_last_load', data.ts);
        }} catch(e) {{ document.body.innerHTML += '<p style="color:#ff9d97">Error: ' + e.message + '</p>'; }}
        setTimeout(() => window.location.href = {json.dumps(DASHBOARD_URL)}, 400);
        </script>
        </body>
        </html>
    """)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(bridge_html)
        bridge_path = tmp.name

    print(f"🌐  Abriendo dashboard con los planes cargados…")

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    chrome = next((p for p in chrome_paths if pathlib.Path(p).exists()), None)

    if chrome:
        subprocess.Popen([chrome, f"file:///{bridge_path.replace(chr(92), '/')}"])
    else:
        import webbrowser
        webbrowser.open(f"file:///{bridge_path.replace(chr(92), '/')}")

    print("✅  Listo. El browser debería abrir el dashboard con los planes cargados.")
    print(f"   Timestamp: {ts_now}")

if __name__ == "__main__":
    main()
