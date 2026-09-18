from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from app.schemas import OptimizeRequest, OptimizeResponse
from app.extractor import extract_directives
from app.guardrails import validate_and_sanitize_directives
from app.optimizer import solve_grid_optimization

app = FastAPI(title="GridWise Optimization API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/optimize-energy", response_model=OptimizeResponse)
def optimize_energy(req: OptimizeRequest):
    try:
        raw_directives = extract_directives(req.operator_notes, req.battery)
        directives = validate_and_sanitize_directives(raw_directives)
        plan, total_grid, total_cost, peak_grid = solve_grid_optimization(
            req.hours, req.battery, directives
        )
        return OptimizeResponse(
            scenario_id=req.scenario_id,
            directive_interpretation=directives,
            hourly_plan=plan,
            total_grid_kwh=total_grid,
            total_cost_bdt=total_cost,
            peak_grid_kwh=peak_grid,
            plan_summary="Directives interpreted via LLM and optimized via LP."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))