"""Prueba aislada de la descarga de un plan ya existente en View & Edit Plans.

No crea planes. Baja el CSV del plan que se indique por posición (por defecto el más reciente).

Uso (con el Chrome del puerto 9222 abierto y la sesión iniciada):
    $env:F9_CDP_URL="http://localhost:9222"
    python fountain9/test_descarga.py        # el más reciente
    python fountain9/test_descarga.py 2      # el segundo de la lista
"""
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

OUT = pathlib.Path("descargas")


def abrir(p):
    cdp = os.environ.get("F9_CDP_URL")
    if not cdp:
        raise SystemExit("Falta F9_CDP_URL (ej. http://localhost:9222)")
    browser = p.chromium.connect_over_cdp(cdp)
    ctx = browser.contexts[0]
    return ctx.pages[0] if ctx.pages else ctx.new_page()


def descargar(page, n):
    OUT.mkdir(exist_ok=True)

    print("paso: abrir View & Edit Plans")
    page.get_by_text("View & Edit Plans").click(timeout=30_000)
    page.wait_for_timeout(4000)

    print(f"paso: abrir el plan n° {n} de la lista")
    tarjetas = page.get_by_text("All - Fixed Schedule Replenishment Plan")
    print(f"  planes visibles: {tarjetas.count()}")
    tarjetas.nth(n - 1).click(timeout=30_000)
    page.wait_for_timeout(5000)

    print("paso: Export as CSV")
    page.get_by_text("Export as CSV").click(timeout=30_000)
    page.wait_for_timeout(1500)

    print("paso: Download All Rows")
    page.get_by_text("Download All Rows").hover(timeout=30_000)
    page.wait_for_timeout(1500)

    print("paso: All Columns (puede tardar varios minutos)")
    try:
        with page.expect_download(timeout=600_000) as dl:
            page.get_by_text("All Columns", exact=True).click(timeout=30_000)
        destino = OUT / dl.value.suggested_filename
        dl.value.save_as(destino)
        print(f"LISTO: {destino}")
    except Exception as e:
        # Conectado por CDP el archivo puede ir a la carpeta de descargas de Chrome.
        print("No pude capturar la descarga desde el script:", str(e).splitlines()[0][:150])
        print("Fijate en la carpeta de Descargas de Chrome si el archivo llegó igual.")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    with sync_playwright() as p:
        descargar(abrir(p), n)


if __name__ == "__main__":
    main()
