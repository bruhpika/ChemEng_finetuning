# Track A: PDF & Documentation Extraction

This module is responsible for extracting structured knowledge from PDF files and official documentation (DWSIM, MATLAB).

## Key Features
- **Blackboard Mechanism**: Participates in a centralized coordination hub, reading from and writing to shared JSON knowledge stores and progress logs.
- **Dynamic Progress Tracking**: Real-time updates to `data/track_a/progress_tracker.md` showing extraction status and API health.
- **Gemini File API (OCR)**: Used for high-quality extraction from scanned engineering PDFs.
- **Playwright Scraping**: Robust scraping for web-based documentation (e.g., MathWorks) to bypass anti-bot measures.

## Challenges & Solutions

| Challenge | Mitigation |
|---|---|
| **MathWorks Anti-Bot** | Used Playwright to simulate browser behavior and successfully retrieve documentation. |
| **Scanned/Image-heavy PDFs** | Implemented OCR-mode using Gemini's File API to ensure text extraction from complex engineering diagrams and tables. |
| **API Rate Limiting** | Implemented a rotation mechanism for multiple Gemini API keys to maintain high throughput. |
| **CLI Software Schema** | Adjusted the extraction prompt and validation logic to handle CLI-based tools (like MATLAB) where UI paths are not applicable. |
| **Windows Path Encoding** | Fixed issues with Unicode characters and long paths in Windows environments. |

## Usage
Run the extraction agent:
```bash
python agent.py
```
Or for local PDFs specifically:
```bash
python extract_local_pdfs.py
```
