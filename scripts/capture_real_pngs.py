import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
html_path = os.path.join(PROJECT_ROOT, "linkedin_assets", "live_verification_dashboard.html")
png_path = os.path.join(PROJECT_ROOT, "linkedin_assets", "real_execution_proof_screenshot.png")

print("Attempting to capture real execution dashboard to PNG via Playwright...")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1200})
        page.goto(f"file:///{html_path.replace(os.sep, '/')}")
        page.screenshot(path=png_path, full_page=True)
        browser.close()
    print(f"[SUCCESS] Captured real execution proof PNG: {png_path}")
except Exception as e:
    print(f"[NOTE] Playwright capture issue: {e}")
    print("Dashboard HTML and JSON are fully generated and ready to view directly.")
