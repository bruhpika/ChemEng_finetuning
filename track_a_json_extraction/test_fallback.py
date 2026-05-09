import sys
import os

# Add parent dir to path so we can import agent
sys.path.append(os.path.dirname(__file__))

from agent import html_extractor

url = "https://www.mathworks.com/help/matlab/ref/ode45.html"
print(f"Testing html_extractor on {url}...")
try:
    text = html_extractor(url)
    print(f"SUCCESS! Extracted {len(text)} characters.")
    print("Preview of text:")
    print(text[:500] + "...")
except Exception as e:
    print(f"FAILED: {e}")
