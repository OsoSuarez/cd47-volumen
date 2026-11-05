"""Dispara los dos planes de reabasto en Fountain9, espera ~16 min y baja los CSV.

Secrets requeridos: F9_USER, F9_PASS.
Presets (no se modifican ni se guardan): ver PRESETS.
"""
import os
import re
import pathlib
import time

from playwright.sync_api import sync_playwright

URL = "https://rappi-ar.kronoscope.fountain9.com/"
USER = os.environ["F9_USER"]
PASS = os.environ["F9_PASS"]
PRESETS = ["TR_CD47_ID_Secos_No TOO-Room Temp", "TR_CD47_RyC"]
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
        page.wait_for_url(lambda u: "/login" not in u, timeout=45_000)
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
    # Tras el login se abre el dashboard de pronóstico. El módulo de compras/reabasto
    # está en la barra lateral con el ícono fa-cart-plus.
    # Esperamos a que la barra lateral esté visible antes de tocar nada (ventana maximizada).
    page.locator("i.fa-cart-plus").first.wait_for(state="attached", timeout=60_000)
    # dispatch_event evita que la barra lateral tape el clic (intercepta eventos del puntero).
    page.locator("i.fa-cart-plus").first.dispatch_event("click", timeout=20_000)
    page.wait_for_timeout(1500)
    try:
        page.get_by_text("Replenishment / Transfer Orders").click(timeout=20_000)
    except Exception:
        dump_debug(page, "sin_menu_replenishment")
        # Volcado a la consola del workflow (los artefactos no siempre se pueden bajar).
        print("URL:", page.url)
        print("TITULO:", page.title())
        print("TEXTO:", page.inner_text("body")[:1500].replace("\n", " | "))
        print("INPUTS:", page.evaluate("() => [...document.querySelectorAll('input,button')].slice(0,40).map(e => [e.tagName, e.type, e.name, e.placeholder, (e.innerText||'').slice(0,30)].join(' '))"))
        raise
    page.wait_for_timeout(2000)
    # El zoom de la página se fija a mano una vez en el perfil del bot (F9_PERFIL), en 80%.


def create_plan(page, preset):
    # El selector de vistas y su desplegable viven en el DOM pero ocultos (se muestran con :hover,
    # que no se reproduce desde Playwright). Los forzamos visibles por CSS y vamos probando vías
    # hasta que una seleccione el preset; cada paso deja constancia en la terminal.
    page.add_style_tag(content="""
        .searchUserView { display: block !important; visibility: visible !important; opacity: 1 !important; }
        .ant-select-dropdown { display: block !important; visibility: visible !important; opacity: 1 !important; }
    """)
    page.wait_for_timeout(500)
    selector = page.locator(".searchUserView").first

    def elegido():
        try:
            return selector.locator(".ant-select-selection-item").first.inner_text(timeout=2_000).strip()
        except Exception:
            return ""

    vias = []

    # Vía 1: clic en la flecha y después en la opción, como se hace a mano.
    def via_flecha():
        selector.locator(".ant-select-arrow").first.click(timeout=10_000)
        page.wait_for_timeout(800)
        page.locator(".ant-select-item-option", has_text=preset).first.click(timeout=10_000)

    # Vía 2: clic directo sobre la opción que ya está en el DOM, sin abrir nada.
    def via_opcion_directa():
        page.locator(".ant-select-item-option", has_text=preset).first.click(timeout=10_000, force=True)

    # Vía 3: clic por JavaScript sobre el nodo de la opción (React escucha el evento igual).
    def via_js():
        ok = page.evaluate("""(txt) => {
            const op = [...document.querySelectorAll('.ant-select-item-option')]
                .find(e => (e.innerText || '').trim().includes(txt));
            if (!op) return false;
            for (const t of ['mousedown', 'mouseup', 'click'])
                op.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window}));
            return true;
        }""", preset)
        if not ok:
            raise RuntimeError("no encontré la opción en el DOM")

    for nombre, via in [("flecha", via_flecha), ("opción directa", via_opcion_directa), ("javascript", via_js)]:
        try:
            via()
            page.wait_for_timeout(1500)
            if elegido() == preset:
                print(f"Preset seleccionado por vía '{nombre}': {preset}")
                break
            vias.append(f"{nombre}: el selector quedó en {elegido()!r}")
        except Exception as e:
            vias.append(f"{nombre}: {str(e).splitlines()[0][:120]}")
    else:
        print("Opciones visibles en el DOM:", page.evaluate(
            "() => [...document.querySelectorAll('.ant-select-item-option')].map(e => (e.innerText||'').trim())"))
        raise RuntimeError("Ninguna vía seleccionó el preset. Detalle: " + " | ".join(vias))

    page.locator("button.plan-create-button").first.click(timeout=20_000)
    page.wait_for_timeout(1500)
    modal = page.locator(".ant-modal:visible button.ant-btn-primary")
    if modal.count():
        modal.first.click()
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
        for preset in PRESETS:
            create_plan(page, preset)
        ctx.close()

    print(f"Planes disparados. Esperando {WAIT_SECONDS // 60} min para que Fountain9 los procese.")
    time.sleep(WAIT_SECONDS)

    with sync_playwright() as p:
        ctx, page = nueva_pagina(p)
        login(page)
        download_last_two(page)
        ctx.close()


if __name__ == "__main__":
    main()
