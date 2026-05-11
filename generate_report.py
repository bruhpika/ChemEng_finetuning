import json
import os
from collections import defaultdict

def generate_report():
    knowledge_dir = "track_a_json_extraction/data/blackboard/knowledge"
    files = ["chunks_DWSIM.json", "chunks_MATLAB.json"]
    
    report_lines = []
    report_lines.append("# Track A Extraction Summary Report")
    report_lines.append(f"\n**Generated on:** {os.popen('date /t').read().strip()} {os.popen('time /t').read().strip()}\n")
    
    for filename in files:
        path = os.path.join(knowledge_dir, filename)
        software = filename.replace("chunks_", "").replace(".json", "")
        
        if not os.path.exists(path):
            report_lines.append(f"## {software}\nNo data found.\n")
            continue
            
        with open(path, "r", encoding="utf-8") as f:
            try:
                chunks = json.load(f)
            except:
                report_lines.append(f"## {software}\nError reading JSON.\n")
                continue
        
        source_stats = defaultdict(lambda: {"total": 0, "good": 0, "incomplete": 0})
        
        for c in chunks:
            url = c.get("source_url", "Unknown")
            is_incomplete = c.get("flag") == "INCOMPLETE" or c.get("topic") in ["API_EXHAUSTED", "PARSE_ERROR", "404 Error Page"]
            
            source_stats[url]["total"] += 1
            if is_incomplete:
                source_stats[url]["incomplete"] += 1
            else:
                source_stats[url]["good"] += 1
        
        report_lines.append(f"## {software} Summary")
        report_lines.append(f"- **Total Sources:** {len(source_stats)}")
        report_lines.append(f"- **Total Chunks:** {len(chunks)}")
        report_lines.append(f"- **Good Chunks:** {sum(s['good'] for s in source_stats.values())}")
        report_lines.append(f"- **Incomplete/Error Chunks:** {sum(s['incomplete'] for s in source_stats.values())}\n")
        
        report_lines.append("| Source URL | Total Chunks | Good | Incomplete/Error |")
        report_lines.append("|---|---|---|---|")
        
        # Sort by total chunks descending
        sorted_sources = sorted(source_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        for url, stats in sorted_sources:
            report_lines.append(f"| {url} | {stats['total']} | {stats['good']} | {stats['incomplete']} |")
        
        report_lines.append("\n---\n")

    with open("track_a_extraction_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print("Report generated: track_a_extraction_report.md")

if __name__ == "__main__":
    generate_report()
