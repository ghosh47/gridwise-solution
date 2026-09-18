import pulp
from typing import List, Dict, Any
import shutil

def solve_grid_optimization(*args, **kwargs) -> Dict[str, Any]:
    # আর্গুমেন্ট আনপ্যাক করা (পজিশনাল বা কি-ওয়ার্ড যেকোনো ভাবেই আসুক)
    load = kwargs.get("load") if "load" in kwargs else (args[0] if len(args) > 0 else [])
    solar = kwargs.get("solar") if "solar" in kwargs else (args[1] if len(args) > 1 else [])
    grid_prices = kwargs.get("grid_prices") if "grid_prices" in kwargs else (args[2] if len(args) > 2 else [])
    battery = kwargs.get("battery") if "battery" in kwargs else (args[3] if len(args) > 3 else None)
    directives = kwargs.get("directives") if "directives" in kwargs else (args[4] if len(args) > 4 else [])

    prob = pulp.LpProblem("Microgrid_Optimization", pulp.LpMinimize)
    hours = list(range(24))

    # Decision variables
    grid_import = [pulp.LpVariable(f"grid_import_{t}", lowBound=0) for t in hours]
    charge = [pulp.LpVariable(f"charge_{t}", lowBound=0, upBound=battery.max_charge_rate_kw) for t in hours]
    discharge = [pulp.LpVariable(f"discharge_{t}", lowBound=0, upBound=battery.max_discharge_rate_kw) for t in hours]
    soc = [pulp.LpVariable(f"soc_{t}", lowBound=0, upBound=battery.capacity_kwh) for t in hours]

    # Objective
    prob += pulp.lpSum([grid_prices[t] * grid_import[t] for t in hours])

    # Dynamic directive modifications
    usable_solar = list(solar)
    min_reserves = [0.0] * 24
    no_charge = [False] * 24
    no_discharge = [False] * 24
    max_grid = [None] * 24

    for d in directives:
        if not d.get("applies"):
            continue
        dtype = d.get("directive_type")
        adj = d.get("structured_adjustment") or {}
        target_hours = adj.get("hours", [])

        if dtype == "solar_reduction":
            factor = adj.get("factor", 1.0)
            for h in target_hours:
                if 0 <= h < 24:
                    usable_solar[h] = solar[h] * factor
        elif dtype == "minimum_battery_reserve":
            min_kwh = adj.get("minimum_energy_kwh", 0.0)
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
                    max_grid[h] = mg

    # Constraints
    prev_soc = battery.initial_soc_kwh
    for t in hours:
        prob += grid_import[t] + usable_solar[t] + discharge[t] == load[t] + charge[t]
        prob += soc[t] == prev_soc + (charge[t] * battery.efficiency) - (discharge[t] / battery.efficiency)
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

        total_grid_kwh += g
        total_cost += g * grid_prices[t]
        if g > peak_grid:
            peak_grid = g

        hourly_plan.append({
            "hour": t,
            "grid_import_kwh": round(g, 2),
            "solar_used_kwh": round(usable_solar[t], 2),
            "battery_charge_kwh": round(c, 2),
            "battery_discharge_kwh": round(d, 2),
            "battery_soc_kwh": round(s, 2),
            "cost_bdt": round(g * grid_prices[t], 2)
        })

    return {
        "hourly_plan": hourly_plan,
        "metrics": {
            "total_grid_kwh": round(total_grid_kwh, 2),
            "total_cost_bdt": round(total_cost, 2),
            "peak_grid_kwh": round(peak_grid, 2)
        }
    }