# GridWise Solution - BUP CSE FEST 2026

Microgrid Energy Optimization Engine powered by FastAPI, Gemini LLM, and Linear Programming (PuLP).

## System Architecture
1. **API Service**: Built with FastAPI providing high-throughput asynchronous endpoints.
2. **LLM Directive Extractor**: Uses Google Gemini (`gemini-3.6-flash`, `gemini-2.5-flash`) with structured JSON schema output to interpret natural language operator notes.
3. **Deterministic Guardrails**: Validates and post-processes LLM directives, ensuring strict hour ranges (0-23), solar scaling factor limits, and marking irrelevant notes as `no_op`.
4. **LP Optimizer**: Uses PuLP and the COIN-OR CBC solver to model energy balance, battery storage capacity, charge/discharge rates, and dynamic grid pricing over 24 hours.

## Live API Service
* **Base URL**: `https://gridwise-solution-x61y.onrender.com`

## Environment Variables
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
PORT=8000