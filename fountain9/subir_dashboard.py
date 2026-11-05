"""
Sube los CSV filtrados al Muelle de Carga del dashboard cd47-volumen
usando Playwright para abrir el dashboard y simular el file input.

Uso:
    python fountain9/subir_dashboard.py

No necesita servidor local ni permisos especiales.
Playwright abre el dashboard, lee los archivos del disco y los inyecta.
"""
import pathlib
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "https://ososuarez.github.io/cd47-volumen/"
DESCARGAS = pathlib.Path(__file__).parent.parent / "descargas"


def find_filtrados():
    secos = sorted(DESCARGAS.glob("filtrado_secos_*.csv"), key=lambda p: p.stat().st_mtime)
    ryc   = sorted(DESCARGAS.glob("filtrado_ryc_*.csv"),   key=lambda p: p.stat().st_mtime)
    if not secos or not ryc:
        sys.exit(f"ERROR: No se encontraron archivos filtrado_secos_*.csv o filtrado_ryc_*.csv en {DESCARGAS}")
    return secos[-1], ryc[-1]


def main():
    secos_path, ryc_path = find_filtrados()

    print(f"Secos:  {secos_path.name} ({secos_path.stat().st_size // 1_000_000} MB)")
    print(f"RyC:    {ryc_path.name} ({ryc_path.stat().st_size // 1_000_000} MB)")
    print(f"\nSubiendo al dashboard: {DASHBOARD_URL}")

    with sync_playwright() as p:
        # Abrir navegador con contexto persistente para mantener sesión
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Abriendo dashboard...")
        page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=30_000)

        # Verificar que el input existe
        page.wait_for_selector("#fi", timeout=10_000)
        print("Dashboard cargado. Subiendo archivos...")

        # Usar set_input_files — Playwright maneja la lectura del archivo local
        # sin ningún problema de CORS o mixed content
        file_input = page.locator("#fi")
        file_input.set_input_files([str(secos_path), str(ryc_path)])

        # Esperar a que el dashboard procese los archivos
        # El dashboard muestra el nombre del archivo en el Muelle de Carga
        print("Esperando procesamiento...")
        page.wait_for_timeout(5_000)

        # Verificar que los archivos aparecieron
        page_text = page.inner_text("body")
        secos_ok = secos_path.stem.replace("_", "-") in page_text or secos_path.name in page_text
        ryc_ok   = ryc_path.stem.replace("_", "-") in page_text or ryc_path.name in page_text

        hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        print(f"\n{'✓' if secos_ok else '?'} Secos: {secos_path.name}")
        print(f"{'✓' if ryc_ok   else '?'} RyC:   {ryc_path.name}")
        print(f"\nSubido el {hora}")
        print("Listo. Cerrando navegador en 3 segundos...")
        page.wait_for_timeout(3_000)
        browser.close()


if __name__ == "__main__":
    main()
