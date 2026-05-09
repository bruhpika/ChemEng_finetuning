import sys
import os
import requests
from bs4 import BeautifulSoup
import re
import time
from playwright.sync_api import sync_playwright

def html_extractor(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        resp = requests.get(url, timeout=20, headers=headers)
        resp.raise_for_status()
        html_content = resp.text
    except requests.exceptions.RequestException as e:
        print(f"   [requests failed: {e}] falling back to Playwright (Firefox Stealth)...")
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()
            try:
                page.goto(url, timeout=90000, wait_until="domcontentloaded")
                if "Access Denied" in page.content():
                    print("   [Access Denied detected] waiting...")
                    time.sleep(5)
                html_content = page.content()
            except Exception as pe:
                print(f"   [Playwright failed: {pe}]")
                html_content = page.content()
            finally:
                browser.close()

    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    return text

url = "https://www.mathworks.com/help/matlab/ref/ode45.html"
print(f"Testing {url}...")
text = html_extractor(url)
print(f"Result length: {len(text)}")
print(f"Preview: {text[:200]}")
