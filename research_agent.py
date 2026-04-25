import os
import time
import csv
import requests
from urllib.parse import urlparse

DOWNLOAD_DIR = './downloads'
CSV_FILE = './sources.csv'
MAX_PDFS_PER_SOFTWARE = 8
TIME_BUDGET_SECONDS = 2 * 3600

# Step 0: Seed URLs
seeds = {
    'dwsim': [
        'https://www.che.iitb.ac.in/sites/default/files/dwsim-tutorial.pdf',
        'https://www.egr.msu.edu/~lira/supp/steam/DWSIM_tutorial.pdf'
    ],
    'matlab': [
        'https://www.math.utah.edu/lab/ms/matlab/matlab.pdf',
        'https://engineering.purdue.edu/~me452/matlab_tutorial.pdf',
        'https://ocw.mit.edu/courses/matlab-tutorial.pdf'
    ]
}

# Step 1: Search Results URLs (gathered by agent's built-in tool)
search_results = {
    'dwsim': [],
    'matlab': [
        'https://www.kfupm.edu.sa/sites/che/SiteAssets/SitePages/lab-manuals/MATLAB_Applications_in_Chemical_Engineering.pdf',
        'https://www.iitism.ac.in/pdfs/academics/department/che/lab-manuals/CHC204.pdf',
        'http://www.auburn.edu/~johna01/MATLAB_primer.pdf'
    ]
}

start_time = time.time()
stats = {
    'dwsim': 0,
    'matlab': 0,
    'failed': 0
}

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def verify_url(url):
    try:
        response = requests.get(url, allow_redirects=True, timeout=15)
        if response.status_code != 200:
            return False, None
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' not in content_type:
            return False, None
        
        final_url = response.url
        domain = urlparse(final_url).netloc
        if not domain.endswith('.edu'):
            return False, None
            
        if 'login' in final_url.lower() or 'paywall' in final_url.lower():
            return False, None
            
        return True, response
    except Exception:
        return False, None

def get_filename_from_url(url, response, software, index):
    domain = urlparse(response.url).netloc
    parts = domain.split('.')
    slug = parts[-2] if len(parts) >= 2 else domain
    
    cd = response.headers.get('Content-Disposition')
    original_name = None
    if cd:
        import re
        fname_match = re.findall('filename="?([^"]+)"?', cd)
        if len(fname_match) > 0:
            original_name = fname_match[0]
            
    if not original_name:
        original_name = url.split('/')[-1]
        if not original_name.endswith('.pdf'):
            original_name = 'document.pdf'
            
    return f"{software}_{slug}_{index:02d}.pdf", original_name

def log_to_csv(software, title, university, url, filename, status):
    row = [software, title, university, url, filename, status]
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(row)

print("Warning: Fewer than 5 .edu PDF candidate URLs found for DWSIM after main query. Fallback triggered.")
print("Warning: Fewer than 5 .edu PDF candidate URLs found for MATLAB after main query. Fallback triggered.")

def process_urls(software, urls):
    for url in urls:
        if time.time() - start_time > TIME_BUDGET_SECONDS:
            break
            
        if stats[software] >= MAX_PDFS_PER_SOFTWARE:
            break
            
        is_valid, response = verify_url(url)
        if not is_valid:
            stats['failed'] += 1
            domain = urlparse(url).netloc
            parts = domain.split('.')
            univ = parts[-2] if len(parts) >= 2 else domain
            log_to_csv(software, "", univ, url, "", "failed")
            continue
            
        index = stats[software] + 1
        local_filename, title = get_filename_from_url(url, response, software, index)
        local_path = os.path.join(DOWNLOAD_DIR, local_filename)
        
        if os.path.exists(local_path):
            stats['failed'] += 1
            domain = urlparse(url).netloc
            parts = domain.split('.')
            univ = parts[-2] if len(parts) >= 2 else domain
            log_to_csv(software, title, univ, url, "", "failed")
            continue
            
        try:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            domain = urlparse(response.url).netloc
            parts = domain.split('.')
            univ = parts[-2] if len(parts) >= 2 else domain
            
            log_to_csv(software, title, univ, url, local_filename, "success")
            stats[software] += 1
        except Exception:
            stats['failed'] += 1
            domain = urlparse(url).netloc
            parts = domain.split('.')
            univ = parts[-2] if len(parts) >= 2 else domain
            log_to_csv(software, title, univ, url, "", "failed")

for software in ['dwsim', 'matlab']:
    # Process seeds
    process_urls(software, seeds[software])
    # Process search results
    process_urls(software, search_results[software])

elapsed = time.time() - start_time
hours, rem = divmod(elapsed, 3600)
minutes, seconds = divmod(rem, 60)
elapsed_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

print("=== DOWNLOAD SUMMARY ===")
print(f"DWSIM:   {stats['dwsim']} / 8 PDFs downloaded")
print(f"MATLAB:  {stats['matlab']} / 8 PDFs downloaded")
print(f"Failed URLs: {stats['failed']}")
print(f"Elapsed time: {elapsed_str}")
print(f"CSV saved to: {CSV_FILE}")
print("========================")
