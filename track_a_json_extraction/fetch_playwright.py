import sys
import os
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

urls = [
    "https://www.mathworks.com/help/matlab/ref/ode45.html",
    "https://www.mathworks.com/matlabcentral/content/fx/fx-transition-faq.html",
    "https://www.mathworks.com/matlabcentral/content/terms-of-use.html",
    "https://www.mathworks.com/matlabcentral/fileexchange/27850-mixture-property-calculations-using-pr-rk-and-srk-eos",
    "https://www.mathworks.com/matlabcentral/fileexchange/88331-web-apps-for-chemical-reaction-engineering",
    "https://api.mathworks.com/community/docs",
    "https://www.mathworks.com/help/index.html",
    "https://www.mathworks.com/help/matlab/index.html",
    "https://www.umkc.edu/is/resources/lab-information/matlab-toolboxes.html",
    "https://codes.arizona.edu/toolbox/help/html/general.html",
    "https://doi.org/10.25405/data.ncl.27055339",
    "https://it.purdue.edu/shopping/software/info/matlab_toolboxes.php",
    "https://oit.duke.edu/help/articles/kb0030777"
]

def sanitize_filename(url: str) -> str:
    clean = url.strip()
    clean = re.sub(r'^https?://', '', clean)
    clean = re.sub(r'[^a-zA-Z0-9]', '_', clean)
    if len(clean) > 180:
        clean = clean[:180]
    return clean + ".txt"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        for url in urls:
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            filename = sanitize_filename(url)
            out_path = os.path.join("data", "track_a", "cache", filename)
            
            print(f"Fetching {url}")
            try:
                page.goto(url, timeout=60000)
                time.sleep(4) # More time for JS
                html = page.content()
                
                soup = BeautifulSoup(html, "html.parser")
                
                # Target main content for MathWorks help pages
                main_content = soup.find(id="doc_center_content") or soup.find("main") or soup.find("article")
                target = main_content if main_content else soup
                
                # Strip noise
                for tag in target(["script", "style", "nav", "footer", "header", "aside", "form"]):
                    tag.decompose()
                
                # Extract text with real newlines
                text = target.get_text(separator="\n", strip=True)
                
                # Clean up multiple newlines
                text = re.sub(r'\n\s*\n', '\n\n', text)
                
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"Source: {url}\n\n{text}")
                print(f"Saved {url} ({len(text)} bytes)")
            except Exception as e:
                print(f"Failed {url}: {e}")
            finally:
                page.close()
        browser.close()

if __name__ == "__main__":
    run()
