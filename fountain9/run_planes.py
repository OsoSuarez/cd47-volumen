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


def login(page):
    page.goto(URL, wait_until="networkidle")
    # Selectores del login sin validar: la sesión de Chrome ya estaba iniciada.
    if page.locator("input[type=password]").count():
        page.locator("input[type=text], input[type=email], input[name=username]").first.fill(USER)
        page.locator("input[type=password]").first.fill(PASS)
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle")


def go_replenishment(page):
    page.get_by_text("Replenishment / Transfer Orders").click()
    page.wait_for_timeout(2000)


def create_plan(page, preset):
    # Selecciona el preset guardado en el dropdown (no se edita ni guarda).
    page.locator(".searchUserView .ant-select-selection").first.click()
    page.locator(".ant-select-dropdown:visible li", has_text=preset).first.click()
    page.wait_for_timeout(500)
    page.locator("button.plan-create-button").first.click()
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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(accept_downloads=True).new_page()
        login(page)
        go_replenishment(page)
        for preset in PRESETS:
            create_plan(page, preset)
        browser.close()

    print(f"Planes disparados. Esperando {WAIT_SECONDS // 60} min para que Fountain9 los procese.")
    time.sleep(WAIT_SECONDS)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(accept_downloads=True).new_page()
        login(page)
        download_last_two(page)
        browser.close()


if __name__ == "__main__":
    main()
