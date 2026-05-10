# Track B: YouTube & Video Extraction

This module focuses on extracting structured JSON knowledge from YouTube walkthroughs and video tutorials for DWSIM and MATLAB.

## Key Features
- **Blackboard Mechanism**: Contributes video-derived knowledge to the centralized blackboard for merging and deduplication.
- **Progress Monitoring**: Integrated logging to track video processing status across the pipeline.
- **Transcript Parsing**: Converts video transcripts into structured JSON chunks.
- **UI Path Extraction**: Specifically identifies step-by-step UI navigation from video descriptions and transcripts.
- **Parameter Identification**: Extracts simulation parameters mentioned in tutorials.

## Challenges & Solutions

| Challenge | Mitigation |
|---|---|
| **Transcript Noise** | Refined prompt engineering to filter out filler words and non-technical chatter from transcripts. |
| **JSON Consistency** | Implemented schema validation to ensure the extracted data follows the unified project schema. |
| **Context Window Limits** | For long videos, the transcript is processed in logical segments to maintain coherence within LLM context limits. |
| **Hallucination in UI Paths** | Constrained the model to only output UI paths explicitly mentioned or clearly visible in the tutorial context. |

## Usage
Run the extraction agent:
```bash
python agent.py
```
