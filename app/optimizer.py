import pulp
from typing import List, Dict, Any, Tuple
import shutil

def solve_grid_optimization(
    load: List[float],
    solar: List[float],
    grid_prices: List[float],
    battery: Any,
    directives: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], float, float, float]:

    def get_bat(obj, key, default=0.0):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    cap = float(get_bat(battery, "capacity_kwh", 20.0))
    init_soc = float(get_bat(battery, "initial_soc_kwh", 10.0))
    max_charge = float(get_bat(battery, "max_charge_rate_kw", 5.0))
    max_discharge = float(get_bat(battery, "max_discharge_rate_kw", 5.0))
    eff = float(get_bat(battery, "efficiency", 0.95))

    prob = pulp.LpProblem("Microgrid_Optimization", pulp.LpMinimize)
    hours = list(range(24))

    # Decision variables
    grid_import = [pulp.LpVariable(f"grid_import_{t}", lowBound=0) for t in hours]
    charge = [pulp.LpVariable(f"charge_{t}", lowBound=0, upBound=max_charge) for t in hours]
    discharge = [pulp.LpVariable(f"discharge_{t}", lowBound=0, upBound=max_discharge) for t in hours]
    soc = [pulp.LpVariable(f"soc_{t}", lowBound=0, upBound=cap) for t in hours]

    # Objective
    prob += pulp.lpSum([grid_prices[t] * grid_import[t] for t in hours])

    # Directives processing
    usable_solar = [float(s) for s in solar]
    min_reserves = [0.0] * 24
    no_charge = [False] * 24
    no_discharge = [False] * 24
    max_grid = [None] * 24

    for d in directives:
        if isinstance(d, dict):
            applies = d.get("applies")
            dtype = d.get("directive_type")
            adj = d.get("structured_adjustment") or {}
        else:
            applies = getattr(d, "applies", False)
            dtype = getattr(d, "directive_type", "no_op")
            adj = getattr(d, "structured_adjustment", {}) or {}
            if hasattr(adj, "dict"):
                adj = adj.dict()
            elif hasattr(adj, "model_dump"):
                adj = adj.model_dump()

        if not applies:
            continue

        target_hours = adj.get("hours", [])

        if dtype == "solar_reduction":
            factor = float(adj.get("factor", 1.0))
            for h in target_hours:
                if 0 <= h < 24:
                    usable_solar[h] = float(solar[h]) * factor
        elif dtype == "minimum_battery_reserve":
            min_kwh = float(adj.get("minimum_energy_kwh", 0.0))
            for h in target_hours:
                if 0 <= h < 24:
                    min_reserves[h] = max(min_reserves[h], min_kwh)
        elif dtype == "no_charge_window":
            for h in target_hours:
                if 0 <= h < 24:
                    no_charge[h] = True
        elif dtype == "no_discharge_window":
            for h in target_hours:
                if 0 <= h < 24:
                    no_discharge[h] = True
        elif dtype == "max_grid_window":
            mg = adj.get("max_grid_kwh")
            for h in target_hours:
                if 0 <= h < 24:
                    max_grid[h] = float(mg) if mg is not None else None

    # Constraints
    prev_soc = init_soc
    for t in hours:
        prob += grid_import[t] + usable_solar[t] + discharge[t] == load[t] + charge[t]
        prob += soc[t] == prev_soc + (charge[t] * eff) - (discharge[t] / eff)
        prev_soc = soc[t]

        if min_reserves[t] > 0:
            prob += soc[t] >= min_reserves[t]
        if no_charge[t]:
            prob += charge[t] == 0
        if no_discharge[t]:
            prob += discharge[t] == 0
        if max_grid[t] is not None:
            prob += grid_import[t] <= max_grid[t]

    cbc_path = shutil.which("cbc")
    if cbc_path:
        solver = pulp.COIN_CMD(path=cbc_path, msg=False)
    else:
        solver = pulp.PULP_CBC_CMD(msg=False)

    prob.solve(solver)

    hourly_plan = []
    total_grid_kwh = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for t in hours:
        g = float(pulp.value(grid_import[t]) or 0.0)
        c = float(pulp.value(charge[t]) or 0.0)
        d = float(pulp.value(discharge[t]) or 0.0)
        s = float(pulp.value(soc[t]) or 0.0)

        cost = g * grid_prices[t]
        total_grid_kwh += g
        total_cost += cost
        if g > peak_grid:
            peak_grid = g

        hourly_plan.append({
            "hour": t,
            "grid_import_kwh": round(g, 2),
            "solar_used_kwh": round(usable_solar[t], 2),
            "battery_charge_kwh": round(c, 2),
            "battery_discharge_kwh": round(d, 2),
            "battery_soc_kwh": round(s, 2),
            "cost_bdt": round(cost, 2)
        })

    total_grid_kwh = round(total_grid_kwh, 2)
    total_cost = round(total_cost, 2)
    peak_grid = round(peak_grid, 2)

    return hourly_plan, total_grid_kwh, total_cost, peak_grid