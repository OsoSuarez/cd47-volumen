"""
Levanta un servidor HTTP local temporal, sirve los CSV filtrados,
y los inyecta programáticamente en el Muelle de Carga del dashboard.

Uso:
    python fountain9/serve_and_upload.py <secos.csv> <ryc.csv>
"""
import sys
import os
import pathlib
import threading
import http.server
import json
import time
import urllib.request

def find_filtrados(descargas_dir: pathlib.Path):
    secos = sorted(descargas_dir.glob("filtrado_secos_*.csv"), key=lambda p: p.stat().st_mtime)
    ryc   = sorted(descargas_dir.glob("filtrado_ryc_*.csv"),   key=lambda p: p.stat().st_mtime)
    if not secos or not ryc:
        sys.exit(f"ERROR: No se encontraron archivos filtrado_secos_*.csv o filtrado_ryc_*.csv en {descargas_dir}")
    return secos[-1], ryc[-1]

def start_server(directory: pathlib.Path, port: int):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()
        def log_message(self, fmt, *args):
            pass  # silenciar logs
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

def inject_js(secos_name: str, ryc_name: str, port: int) -> str:
    """Genera el JS que inyecta los dos CSV como File objects en el input #fi."""
    return f"""
(async function() {{
  const BASE = 'http://127.0.0.1:{port}/';
  const files_info = [
    {{ name: '{secos_name}', label: 'Secos' }},
    {{ name: '{ryc_name}',   label: 'RyC'   }},
  ];

  const fileObjs = [];
  for (const fi of files_info) {{
    console.log('Fetching', fi.label, '...');
    const resp = await fetch(BASE + fi.name);
    if (!resp.ok) throw new Error('Error fetching ' + fi.name + ': ' + resp.status);
    const blob = await resp.blob();
    fileObjs.push(new File([blob], fi.name, {{ type: 'text/csv' }}));
    console.log(fi.label, 'OK:', blob.size, 'bytes');
  }}

  const input = document.getElementById('fi');
  if (!input) throw new Error('No se encontró el input #fi');

  const dt = new DataTransfer();
  for (const f of fileObjs) dt.items.add(f);
  input.files = dt.files;
  input.dispatchEvent(new Event('change', {{ bubbles: true }}));
  console.log('Archivos inyectados:', fileObjs.map(f => f.name).join(', '));
  return 'OK: ' + fileObjs.length + ' archivos inyectados';
}})()
"""

def main():
    descargas = pathlib.Path(__file__).parent.parent / "descargas"
    secos_path, ryc_path = find_filtrados(descargas)

    print(f"Secos:  {secos_path.name} ({secos_path.stat().st_size // 1_000_000} MB)")
    print(f"RyC:    {ryc_path.name} ({ryc_path.stat().st_size // 1_000_000} MB)")

    port = 18347
    server = start_server(descargas, port)
    print(f"\nServidor local iniciado en http://127.0.0.1:{port}/")
    print("Verificando acceso...")

    # Esperar que el server arranque
    for _ in range(10):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/{secos_path.name}", timeout=1)
            break
        except Exception:
            time.sleep(0.3)

    js = inject_js(secos_path.name, ryc_path.name, port)

    print("\n--- COPIÁ ESTE JS EN LA CONSOLA DEL DASHBOARD ---")
    print(js)
    print("--- FIN DEL JS ---")
    print("\nO si Claude controla Chrome, puede ejecutarlo directo.")
    print("\nPresioná Enter para cerrar el servidor cuando termines...")
    input()
    server.shutdown()

if __name__ == "__main__":
    main()
