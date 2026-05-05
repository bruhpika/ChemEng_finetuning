import json
import os

# URLs to re-process with new logic
urls_to_clean = {
    "https://api.mathworks.com/community/docs",
    "https://atmos.uw.edu/~wmtsa/",
    "https://codes.arizona.edu/toolbox/help/html/general.html",
    "https://www.mathworks.com/help/matlab/ref/ode45.html",
    "https://www.mathworks.com/matlabcentral/content/fx/fx-transition-faq.html",
    "https://www.mathworks.com/matlabcentral/content/terms-of-use.html",
    "https://www.mathworks.com/matlabcentral/fileexchange/27850-mixture-property-calculations-using-pr-rk-and-srk-eos",
    "https://www.mathworks.com/matlabcentral/fileexchange/88331-web-apps-for-chemical-reaction-engineering",
    "https://www.mathworks.com/help/index.html",
    "https://www.mathworks.com/help/matlab/index.html",
    "https://www.umkc.edu/is/resources/lab-information/matlab-toolboxes.html",
    "https://doi.org/10.25405/data.ncl.27055339",
    "https://it.purdue.edu/shopping/software/info/matlab_toolboxes.php",
    "https://oit.duke.edu/help/articles/kb0030777"
}

file_path = "data/track_a/chunks_MATLAB.json"

if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        original_count = len(chunks)
        clean_chunks = [c for c in chunks if c.get("source_url") not in urls_to_clean]
        new_count = len(clean_chunks)
        with open(file_path, "w", encoding="utf-8") as fw:
            json.dump(clean_chunks, fw, indent=2)
        print(f"Removed {original_count - new_count} chunks for re-processing.")
