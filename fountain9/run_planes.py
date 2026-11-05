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


def nueva_pagina(p):
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
    # Flujo: pasar el cursor sobre el ícono verde (searchUserView), desplegar la flecha,
    # hacer clic en el preset y después en Create Plan.
    # Hay dos elementos userSpecificView: se usa el que está más a la derecha (el ícono verde).
    # Elegimos el ícono que realmente está al frente en su centro (no uno tapado por la barra de pestañas).
    idx = page.evaluate("""() => {
        const els = [...document.querySelectorAll('.userSpecificView')];
        for (let i = 0; i < els.length; i++) {
            const r = els[i].getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            if (top && (top === els[i] || els[i].contains(top))) return i;
        }
        return -1;
    }""")
    if idx < 0:
        raise RuntimeError("No encontré el ícono verde al frente en la página (¿la ventana está maximizada?)")
    icono = page.locator(".userSpecificView").nth(idx)
    icono.scroll_into_view_if_needed(timeout=20_000)
    # El selector verde solo aparece con :hover real, así que movemos el cursor de verdad.
    # Primero pasamos por la barra de pestañas (el panel activo puede tapar el ícono) y después al ícono.
    box = icono.bounding_box()
    tabs = page.locator(".ant-tabs-nav").first.bounding_box()
    if tabs:
        page.mouse.move(tabs["x"] + tabs["width"] / 2, tabs["y"] + tabs["height"] / 2)
        page.wait_for_timeout(300)
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=10)
    page.wait_for_timeout(500)
    selector = page.locator(".searchUserView").first
    # El selector solo aparece con el cursor real sobre el icono. Reintentamos el movimiento
    # y dejamos en la terminal dónde está el icono, para diagnosticar si no llega.
    visible = False
    for intento in range(5):
        box = icono.bounding_box()
        print(f"Icono verde en {box} (intento {intento + 1})")
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=5)
        page.wait_for_timeout(700)
        if selector.is_visible():
            visible = True
            break
    if not visible:
        # Diagnóstico: qué elemento queda realmente debajo del centro del icono, y el estado del selector.
        b = icono.bounding_box()
        cx, cy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        print("Diagnóstico, elemento bajo el centro del icono:", page.evaluate(
            "([x, y]) => { const e = document.elementFromPoint(x, y); return e ? e.tagName + '.' + String(e.className).slice(0, 80) : null }",
            [cx, cy]))
        print("Diagnóstico, display del selector:", page.evaluate(
            "() => { const s = document.querySelector('.searchUserView'); return s ? getComputedStyle(s).display : 'no existe' }"))
        print("Diagnóstico, ventana con foco:", page.evaluate("() => document.hasFocus()"))
        # Probamos disparar eventos de entrada sobre el contenedor del icono y miramos si el selector se muestra.
        for evento in ["pointerenter", "mouseenter", "mouseover"]:
            page.evaluate(
                "([x, y, ev]) => { const e = document.elementFromPoint(x, y); if (!e) return;"
                " const c = e.closest('.userSpecificView, .floating-button') || e;"
                " c.dispatchEvent(new Event(ev, {bubbles: true})); }",
                [cx, cy, evento])
            page.wait_for_timeout(400)
            print(f"Diagnóstico, tras {evento}:", page.evaluate(
                "() => { const s = document.querySelector('.searchUserView'); return s ? getComputedStyle(s).display : 'no existe' }"))
        raise RuntimeError(f"El selector verde no se desplegó con el cursor sobre el icono. Icono en {icono.bounding_box()}")
    # Igual que a mano: con el selector visible, clic real en la flecha para expandirlo.
    # La flecha queda debajo del icono, a 64 px de su borde superior y centrada en su eje.
    # Bajamos en línea recta desde el icono para no salir de la zona del selector.
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + 64
    page.mouse.move(cx, cy, steps=8)
    page.wait_for_timeout(300)
    page.mouse.click(cx, cy)
    page.wait_for_timeout(800)
    # Si la flecha no abrió el desplegable, respaldo por teclado: enfocamos el campo,
    # escribimos el nombre del preset y confirmamos con Enter.
    page.evaluate("() => document.querySelector('.searchUserView input').focus()")
    page.wait_for_timeout(300)
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(800)
    page.keyboard.type(preset, delay=40)
    page.wait_for_timeout(800)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1000)
    # Verificamos que el selector quedó con el preset elegido antes de crear el plan.
    elegido = selector.locator(".ant-select-selection-item").first.inner_text(timeout=5_000)
    if elegido.strip() != preset:
        raise RuntimeError(f"No se seleccionó el preset: el selector muestra {elegido!r}")
    page.locator("button.plan-create-button").first.click(timeout=20_000)
    # Si aparece modal de confirmación, se acepta.
    modal = page.locator(".ant-modal:visible button.ant-btn-primary")
    if modal.count():
        modal.first.click()
    page.wait_for_timeout(3000)


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
