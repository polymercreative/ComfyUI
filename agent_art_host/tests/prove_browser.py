from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8794/agent-art')
    page.wait_for_function('document.querySelector("#hero").naturalWidth > 0')
    page.locator('#part').select_option('fish')
    page.locator('#angle').fill('24')
    page.get_by_role('button', name='Apply & inspect').click()
    page.wait_for_function('document.querySelector("#status").textContent.includes("end to end")')
    page.screenshot(path=str(ROOT/'output/creative-browser.png'), full_page=True)
    print(page.locator('#status').inner_text())
    assert not errors, errors
    page.locator('#name').fill('motion-bookmark')
    page.get_by_role('button', name='Open', exact=True).click()
    page.wait_for_function('document.querySelector("#description").textContent.startsWith("12 frame")')
    assert page.locator('#proofs img').count() >= 3
    page.screenshot(path=str(ROOT/'output/motion-browser.png'), full_page=True)
    print('Browser edit and motion inspection passed; no page errors')
    browser.close()
