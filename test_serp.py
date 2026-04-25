import requests
url = 'https://serpapi.com/search.json'
params = {'q': '"DWSIM tutorial" filetype:pdf site:edu'}
try:
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    print("Keys:", data.keys())
    if 'organic_results' in data:
        print("First result link:", data['organic_results'][0].get('link'))
    else:
        print("No organic results.")
except Exception as e:
    print("Error:", e)
