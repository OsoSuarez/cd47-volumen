"""Dispara los dos planes de reabasto en Fountain9, espera ~16 min y baja los CSV.

Secrets requeridos: F9_USER, F9_PASS.
Presets (no se modifican ni se guardan): ver PRESETS.
"""
import os
import re
import pathlib
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

URL = "https://rappi-ar.kronoscope.fountain9.com/"
USER = os.environ["F9_USER"]
PASS = os.environ["F9_PASS"]
PRESETS = [
    # (nombre del preset, texto con el que aparece en la lista desplegable)
    ("TR_CD47_ID_Secos_No TOO-Room Temp", "TR_CD47_ID_Secos_No TOO-Room"),
    ("TR_CD47_RyC", "TR_CD47_RyC"),
]
WAIT_SECONDS = 16 * 60
OUT = pathlib.Path("descargas")


class _SinCierre:
    # Envoltorio para el Chrome conectado por CDP: no lo cerramos al terminar cada etapa.
    def __init__(self, ctx):
        self.ctx = ctx

    def close(self):
        pass


def nueva_pagina(p):
    # F9_CDP_URL: se conecta a un Chrome que ya está abierto con depuración remota
    # (por ejemplo http://localhost:9222). Así el hover lo maneja el navegador real.
    cdp = os.environ.get("F9_CDP_URL")
    if cdp:
        browser = p.chromium.connect_over_cdp(cdp)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return _SinCierre(ctx), page
    # F9_PERFIL: carpeta donde se guarda la sesión de Chrome (se resuelve el captcha una vez).
    # F9_CHANNEL=chrome usa el Chrome instalado. F9_HEADLESS=0 muestra la ventana.
    channel = os.environ.get("F9_CHANNEL") or None
    headless = os.environ.get("F9_HEADLESS", "1") != "0"
    perfil = os.environ.get("F9_PERFIL")
    # Con ventana visible: Chrome arranca maximizado y la página toma el tamaño real de la ventana.
    args = [] if headless else ["--start-maximized"]
    no_viewport = not headless
    if perfil:
        ctx = p.chromium.launch_persistent_context(
            perfil, channel=channel, headless=headless, accept_downloads=True,
            args=args, no_viewport=no_viewport,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return ctx, page
    browser = p.chromium.launch(channel=channel, headless=headless, args=args)
    ctx = browser.new_context(accept_downloads=True, no_viewport=no_viewport)
    return ctx, ctx.new_page()


def login(page):
    page.goto(URL, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(1500)
    if "/login" not in page.url and not page.locator("input[type=password]").count():
        return  # ya hay sesión
    page.locator("input[type=email]").first.fill(USER)
    page.locator("input[type=password]").first.fill(PASS)
    page.locator("button[type=submit]", has_text="Login").first.click()
    try:
        page.wait_for_url(lambda u: "/login" not in u, timeout=90_000)
    except Exception:
        print("LOGIN FALLIDO. URL:", page.url)
        print("TEXTO:", page.inner_text("body")[:800].replace("\n", " | "))
        raise
    page.wait_for_load_state("domcontentloaded", timeout=90_000)
    pass_secondary_screen(page)


def pass_secondary_screen(page):
    # Si después del login aparece un modal (p. ej. "Choose Dataset"), se loguea su contenido
    # y se confirma con el botón OK / Aceptar / Continuar.
    page.wait_for_timeout(2000)
    modal = page.locator("[role=dialog]:visible, .modal:visible, .ant-modal:visible").first
    if not modal.count():
        print("SIN PANTALLA SECUNDARIA. URL:", page.url)
        return
    print("PANTALLA SECUNDARIA:", modal.inner_text()[:400].replace("\n", " | "))
    print("BOTONES:", modal.locator("button").all_inner_texts())
    ok = modal.locator("button", has_text=re.compile(r"^\s*(OK|Aceptar|Continuar|Continue|Confirm|Confirmar)\s*$", re.I)).first
    if ok.count():
        ok.click()
        print("CLIC EN OK. URL:", page.url)
    else:
        print("NO ENCONTRÉ BOTÓN OK")
    page.wait_for_timeout(3000)


def dump_debug(page, name):
    # Guarda captura y HTML para diagnosticar selectores desde los artefactos del workflow.
    dbg = OUT / "debug"
    dbg.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(dbg / f"{name}.png"), full_page=True)
    (dbg / f"{name}.html").write_text(page.content(), encoding="utf-8")


def go_replenishment(page):
    # Primero el carrito de la barra lateral (abre el módulo de compras/reabasto).
    # dispatch_event evita que la barra lateral intercepte el clic.
    page.locator("i.fa-cart-plus").first.wait_for(state="attached", timeout=60_000)
    page.locator("i.fa-cart-plus").first.dispatch_event("click", timeout=20_000)
    page.wait_for_timeout(2500)
    # Después la pestaña horizontal.
    page.get_by_text("Replenishment / Transfer Orders").click(timeout=20_000)
    page.wait_for_timeout(2500)
    print("En Replenishment / Transfer Orders")


def cerrar_avisos(page):
    # El cartel "Plan is being generated in the background" queda abierto y tapa los controles.
    for sel in [".ant-notification-notice-close", ".ant-alert-close-icon",
                ".ant-message-notice .anticon-close", ".ant-modal-close"]:
        cajas = page.locator(f"{sel}:visible")
        for i in range(cajas.count()):
            try:
                cajas.nth(i).click(timeout=3_000)
                page.wait_for_timeout(300)
            except Exception:
                pass


def esperar_carga(page, timeout=120_000):
    # Tras crear un plan la página queda con un spinner (.clipLoader) que tapa los controles.
    try:
        page.locator(".clipLoader").first.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass
    page.wait_for_timeout(1000)


def create_plan(page, preset, texto_opcion):
    esperar_carga(page)
    cerrar_avisos(page)
    # El bloque del selector solo se muestra con :hover sobre el ícono verde, y ese hover no se
    # reproduce desde Playwright. Lo forzamos visible por CSS y después clic directo al combobox.
    print("  paso: abrir selector de vistas")
    page.add_style_tag(content=".searchUserView { display: block !important; visibility: visible !important; opacity: 1 !important; }")
    page.wait_for_timeout(600)
    page.locator(".searchUserView").get_by_role("combobox").first.click(timeout=20_000)
    page.wait_for_timeout(1000)
    page.get_by_text(texto_opcion).click(timeout=20_000)
    page.wait_for_timeout(2000)
    print(f"Preset seleccionado: {preset}")

    # Fecha de simulación: hoy + 7 días (en la grabación, el 12 estando a 5 de noviembre).
    dia = (date.today() + timedelta(days=7)).day
    # Expandimos Future Order Planning solo si los switches todavía no están a la vista
    # (puede haber quedado abierto del plan anterior).
    print("  paso: expandir Future Order Planning")
    if not page.get_by_role("switch").count():
        # Lo que escucha el clic es el botón que envuelve el título y la flecha, no el título.
        # Nombre por coincidencia parcial: varía según si está abierto o cerrado.
        boton = page.get_by_role("button", name=re.compile("Future Order"))
        if boton.count():
            boton.first.dispatch_event("click", timeout=20_000)
        else:
            print("  No encontré el botón de Future Order. Botones en pantalla:",
                  page.evaluate("() => [...document.querySelectorAll('button')]"
                                ".map(b => (b.getAttribute('aria-label') || b.innerText || '').trim())"
                                ".filter(Boolean).slice(0, 40)"))
            raise RuntimeError("No pude expandir Future Order Planning")
        page.wait_for_timeout(2000)
    page.get_by_role("switch").first.wait_for(state="visible", timeout=20_000)
    # Lo mismo con los switches: solo los tocamos si no están ya encendidos, para no apagarlos.
    print("  paso: switches")
    for i in range(2):
        sw = page.get_by_role("switch").nth(i)
        if sw.get_attribute("aria-checked") != "true":
            sw.click(timeout=20_000)
            page.wait_for_timeout(500)
    print(f"  paso: fecha de simulacion (dia {dia})")
    page.get_by_role("textbox", name="Select date").click(timeout=20_000)
    page.wait_for_timeout(1000)
    # Acotado al calendario: un get_by_text suelto matchea cualquier numero de la pagina.
    calendario = page.locator(".ant-calendar-date, .ant-picker-cell-inner")
    calendario.filter(has_text=re.compile(rf"^{dia}$")).first.click(timeout=20_000)
    page.wait_for_timeout(1000)
    print(f"Fecha de simulación: día {dia}")

    print("  paso: Create Plan")
    page.get_by_role("button", name="Create Plan").click(timeout=20_000)
    page.wait_for_timeout(1500)
    page.get_by_role("dialog").get_by_role("button", name="Create Plan").click(timeout=20_000)
    page.wait_for_timeout(3000)
    print(f"Plan disparado para {preset}")


def download_last_two(page):
    page.get_by_text("View & Edit Plans").click()
    page.wait_for_timeout(3000)
    OUT.mkdir(exist_ok=True)
    cards = page.get_by_text(re.compile(r"All - Fixed Schedule Replenishment Plan"))
    for i in range(2):  # las dos primeras tarjetas son las más recientes
        cards.nth(i).click()
        page.wait_for_timeout(2000)
        page.get_by_text("Export as CSV").click()
        page.get_by_text("Download All Rows").hover()
        with page.expect_download(timeout=180_000) as dl:
            page.get_by_text("All Columns", exact=True).click()
        dl.value.save_as(OUT / f"plan_{i + 1}_{dl.value.suggested_filename}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(1000)


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx, page = nueva_pagina(p)
        login(page)
        go_replenishment(page)
        for preset, texto in PRESETS:
            create_plan(page, preset, texto)
        ctx.close()

    print(f"Planes disparados. Esperando {WAIT_SECONDS // 60} min para que Fountain9 los procese.")
    time.sleep(WAIT_SECONDS)

    with sync_playwright() as p:
        ctx, page = nueva_pagina(p)
        login(page)
        go_replenishment(page)
        download_last_two(page)
        ctx.close()


def filtrar_y_subir():
    """Paso 3: filtra los CSV y los sube al dashboard de forma persistente.

    - filtrar_csv.py      -> genera filtrado_secos_*.csv y filtrado_ryc_*.csv
    - csv_to_base_json.py -> convierte los CSV al formato base.json del repo,
                             hace commit y dispara el workflow de GitHub Actions
                             para que el dashboard se regenere con los datos
                             del plan permanentemente persistidos.
    """
    import subprocess
    import sys
    scripts = pathlib.Path(__file__).parent

    print("\n--- Paso 3a: Filtrando CSV (removiendo qty=0) ---")
    subprocess.run([sys.executable, str(scripts / "filtrar_csv.py")], check=True)

    print("\n--- Paso 3b: Convirtiendo CSV a base.json y subiendo al repo ---")
    subprocess.run([sys.executable, str(scripts / "csv_to_base_json.py")], check=True)


if __name__ == "__main__":
    main()
    filtrar_y_subir()
