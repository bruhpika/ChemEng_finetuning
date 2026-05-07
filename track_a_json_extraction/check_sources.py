import csv
import os
import requests
import time

def check_csv(filename):
    path = os.path.join("data", filename)
    if not os.path.exists(path):
        print(f"File {path} not found.")
        return

    print(f"\nChecking {filename}...")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if "status" not in fieldnames:
            fieldnames.append("status")
        for row in reader:
            rows.append(row)

    headers = {"User-Agent": "Mozilla/5.0"}
    for i, row in enumerate(rows):
        url = row["url"]
        print(f"[{i+1}/{len(rows)}] Checking {url} ... ", end="", flush=True)
        try:
            resp = requests.head(url, timeout=10, headers=headers, allow_redirects=True)
            if resp.status_code == 403:
                row["status"] = "RETRY_WITH_PLAYWRIGHT"
                print("403 (Will use Playwright)")
            elif resp.status_code >= 400:
                # Some sites don't like HEAD, try GET
                resp_get = requests.get(url, timeout=10, headers=headers, stream=True)
                resp_get.close()
                if resp_get.status_code == 403:
                    row["status"] = "RETRY_WITH_PLAYWRIGHT"
                    print("403 (Will use Playwright)")
                elif resp_get.status_code >= 400:
                    row["status"] = f"BROKEN_{resp_get.status_code}"
                    print(f"Broken ({resp_get.status_code})")
                else:
                    row["status"] = "READY"
                    print("OK")
            else:
                row["status"] = "READY"
                print("OK")
        except Exception as e:
            row["status"] = "BROKEN_EXCEPTION"
            print(f"Failed ({type(e).__name__})")
        time.sleep(0.5)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Updated {filename}")

if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__))
    check_csv("sources_matlab.csv")
    check_csv("sources_dwsim.csv")
