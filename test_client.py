import json
import requests

BASE_URL = "https://gridwise-solution-x61y.onrender.com"

# 1. Health check check kora
print("--- 1. Testing Health Check ---")
try:
    health_res = requests.get(f"{BASE_URL}/health")
    print("Health Status:", health_res.status_code, health_res.json())
except Exception as e:
    print("Error: Server run kora nai! Age server start koro। Details:", e)
    exit(1)

# 2. Sample Case Load Kora
print("\n--- 2. Loading Sample Cases ---")
try:
    with open("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json", "r") as f:
        data = json.load(f)
except FileNotFoundError:
    print("Error: BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json file pawa jayni!")
    exit(1)

first_case = data["cases"][0]
print(f"Testing Case ID: {first_case.get('id', 'case_1')}")

# 3. Post Request Pathano
response = requests.post(f"{BASE_URL}/optimize-energy", json=first_case["input"])
print("HTTP Status Code:", response.status_code)

if response.status_code == 200:
    res = response.json()
    print("\n--- Directives Output ---")
    print(json.dumps(res["directive_interpretation"], indent=2))
    
    print("\n--- Total Cost & Metrics ---")
    print("Total Grid kWh :", res["total_grid_kwh"])
    print("Total Cost BDT :", res["total_cost_bdt"])
    print("Peak Grid kWh  :", res["peak_grid_kwh"])
else:
    print("Request Failed!")
    print("Response:", response.text)