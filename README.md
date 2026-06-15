# AI Study Assistant (Desktop Prototype)

A native desktop utility built in Python using CustomTkinter that lets users run keyword and semantic searches over local text files, using online Large Language Models (LLMs) to summarize and explain the retrieved notes.

> **Project Status:** This is an early-stage desktop prototype built as part of my learning journey in Python application development and AI orchestration. It focuses on functional architecture rather than a polished consumer deployment.

---

## Architectural Workflow



The application follows a simple operational loop to process user questions:
1. **Network Validation:** Confirms active internet status via an un-cached network socket handshake during startup.
2. **Semantic Embedding Matrix:** Indexes local raw text files (`.txt`) using the `all-MiniLM-L6-v2` transformer model to create local vectors.
3. **Hybrid Search Routing:** Combines frequency-based keyword matching with cosine similarity scoring to rank relevant context blocks.
4. **Cascade API Pipeline:** Sends compiled contexts sequentially down a fallback chain of external providers (Google AI Studio, Groq, OpenRouter) until a text completion response is successfully generated.

---

## Technical Reality & Limitations

Before setting up or testing the system, please note the following operational boundaries:
- **File Constraints:** The script currently expects a clean directory containing only standard text files (`.txt`). It does not dynamically parse complex extensions like `.pdf`, `.docx`, or `.json` notes.
- **Hardware Dependencies:** On cold boot, the dedicated loading screen will remain active while the local sentence-transformer model initializes into memory. Systems without dedicated hardware may experience longer boot intervals.
- **API Dependencies:** The application acts as a bridge to online LLMs. It contains no native text generation capabilities and requires valid external API keys configured in the environment.

---

## Setup & Local Testing Guide

### Prerequisites
- Python 3.10 or higher installed on your system.
- Valid API credentials for at least one of the supported model providers (Gemini, Groq, or OpenRouter).

### 1. Installation
Clone this repository to your local machine and install the exact library dependencies:
```bash
git clone https://github.com/AbrarH4/Study-Assistant.git
pip install -r requirements.txt