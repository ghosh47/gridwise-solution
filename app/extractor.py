import os
import json
import time
from typing import List
from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.schemas import DirectiveInterpretation, BatteryInput

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

PROMPT = """You are an expert energy grid directive interpreter.
Convert natural-language operator notes into structured directives for a 24-hour microgrid.

Context:
Battery capacity: {capacity} kWh.

Strict Operational Rules:
1. Supported directive_type: "solar_reduction", "minimum_battery_reserve", "no_charge_window", "no_discharge_window", "max_grid_window", "no_op".
2. Irrelevant notes: applies = false, directive_type = "no_op", structured_adjustment = null.
3. Applicable directives: applies = true.
4. Time windows are start-inclusive, end-exclusive (e.g., 1 PM to 3 PM -> [13, 14], noon to 2 PM -> [12, 13], 6 PM to 9 PM -> [18, 19, 20]). Hours must be unique integers 0..23 in ascending order.
5. solar_reduction: factor is the REMAINING usable fraction between 0.0 and 1.0 (e.g., 80% reduction -> factor = 0.2; usable solar 25% -> factor = 0.25).
6. minimum_battery_reserve: if given as percentage (e.g. 50%), convert to kWh using capacity ({capacity} * percentage / 100).
7. Return exactly one interpretation per operator note in note_index order (0 to N-1).

Operator Notes:
{notes}
"""

CANDIDATE_MODELS = ["gemini-3.6-flash", "gemini-2.5-flash"]

def extract_directives(notes: List[str], battery: BatteryInput) -> List[dict]:
    notes_text = "\n".join([f"Note {idx}: {text}" for idx, text in enumerate(notes)])
    full_prompt = PROMPT.format(capacity=battery.capacity_kwh, notes=notes_text)

    last_err = None
    for model_name in CANDIDATE_MODELS:
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=list[DirectiveInterpretation],
                        temperature=0.0
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "503" in err_str or "unavailable" in err_str or "429" in err_str:
                    time.sleep(2 * (attempt + 1))
                    continue
                break

    raise last_err