"""Capture the current studio UI for release documentation (no provider calls)."""
import argparse
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser()
parser.add_argument('project')
args=parser.parse_args()
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
    page.add_init_script("localStorage.setItem('framecore-onboarding-v2','done');")
    page.goto('http://127.0.0.1:8877/',wait_until='domcontentloaded')
    page.evaluate('(id)=>localStorage.setItem("framecore-project",id)',args.project)
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function('window.framecoreContext && window.framecoreContext()?.id')
    page.wait_for_function('document.querySelector("#player").ready')
    page.wait_for_timeout(1200)
    page.locator('#studioAgent').click()
    page.locator('#assistantPrompt').fill('Zaproponuj ulepszenia tej reklamy. Zachowaj sześć scen po 5 sekund.')
    page.screenshot(path='assets/framecore-studio-v2.png')
    page.locator('#closeAgent').click()
    page.locator('#studioTour').click()
    page.screenshot(path='assets/framecore-onboarding-v2.png')
    browser.close()
