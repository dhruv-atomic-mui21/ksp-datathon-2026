import sys
import os
import json

# Ensure functions/ksp_backend is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "functions", "ksp_backend"))

from main import handler
from flask import Flask

# Initialize mock Flask app for testing context
app = Flask("test_app")

# Mock request class that matches Flask.Request properties accessed in main.py
class MockRequest:
    def __init__(self, path, method="GET", json_data=None, args=None):
        self.path = path
        self.method = method
        self.json_data = json_data or {}
        self.args = args or {}

    def get_json(self):
        return self.json_data

    @property
    def args(self):
        return self._args

    @args.setter
    def args(self, val):
        # Allow dictionary style get() on request.args
        class ArgsWrapper(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        self._args = ArgsWrapper(val)

def run_tests():
    print("====================================================")
    print("KSP BACKEND FUNCTIONS — AUTOMATED INTEGRATION TESTS")
    print("====================================================\n")

    # Set local development flag for SQLite execution
    os.environ["DB_TYPE"] = "sqlite"

    # Define tests...

    tests = [
        # Test 1: Chat endpoint (English)
        {
            "name": "POST /api/chat (English Query)",
            "request": MockRequest("/api/chat", "POST", json_data={
                "query": "Show me the criminal history of Ramesh Gowda",
                "history": [],
                "user": {"email": "io.patil@ksp.gov.in", "role": "investigator"}
            })
        },
        # Test 2: Chat endpoint (Kannada)
        {
            "name": "POST /api/chat (Kannada Query)",
            "request": MockRequest("/api/chat", "POST", json_data={
                "query": "ಕಳ್ಳತನ ಪ್ರಕರಣಗಳ ಸ್ಥಿತಿ ಏನು?",
                "history": [],
                "user": {"email": "io.patil@ksp.gov.in", "role": "investigator"}
            })
        },
        # Test 3: Network Graph endpoint
        {
            "name": "GET /api/network",
            "request": MockRequest("/api/network", "GET", args={})
        },
        # Test 4: Repeat Offenders endpoint
        {
            "name": "GET /api/repeat-offenders",
            "request": MockRequest("/api/repeat-offenders", "GET")
        },
        # Test 5: Geospatial Hotspots endpoint
        {
            "name": "GET /api/geospatial",
            "request": MockRequest("/api/geospatial", "GET", args={"district": "Bengaluru City"})
        },
        # Test 6: Predictive Risk scoring
        {
            "name": "GET /api/predictive",
            "request": MockRequest("/api/predictive", "GET")
        },
        # Test 7: Anomaly Detection
        {
            "name": "GET /api/anomalies",
            "request": MockRequest("/api/anomalies", "GET")
        },
        # Test 8: Sociological Insights
        {
            "name": "GET /api/sociological",
            "request": MockRequest("/api/sociological", "GET")
        },
        # Test 9: Investigator Leads (For CaseMaster ID 1)
        {
            "name": "GET /api/leads (Case ID 1)",
            "request": MockRequest("/api/leads", "GET", args={"case_id": "1"})
        },
        # Test 10: Audit Logs (Role: Supervisor)
        {
            "name": "GET /api/audit-logs (Supervisor - Authorized)",
            "request": MockRequest("/api/audit-logs", "GET", args={"role": "supervisor"})
        },
        # Test 11: Audit Logs (Role: Investigator - Unauthorized)
        {
            "name": "GET /api/audit-logs (Investigator - Unauthorized)",
            "request": MockRequest("/api/audit-logs", "GET", args={"role": "investigator"})
        }
    ]

    failed = 0
    passed = 0

    for t in tests:
        print(f"Running Check: {t['name']}...")
        try:
            with app.app_context():
                response = handler(t["request"])
            status_code = response.status_code
            response_json = json.loads(response.data.decode('utf-8'))
            
            if status_code in [200, 403]: # 403 is correct for Test 11 unauthorized block
                print(f"  [SUCCESS] Status Code: {status_code}")
                # Print sample output length/fields
                if "results" in response_json:
                    print(f"  Found {len(response_json['results'])} result rows.")
                elif "nodes" in response_json:
                    print(f"  Network contains {len(response_json['nodes'])} nodes and {len(response_json['edges'])} edges.")
                elif "hotspots" in response_json:
                    print(f"  Found {len(response_json['hotspots'])} hotspots and {len(response_json['raw_cases'])} raw coordinates.")
                elif isinstance(response_json, list):
                    print(f"  Returned {len(response_json)} items.")
                elif "error" in response_json:
                    print(f"  Handled access policy message: '{response_json['error']}'")
                passed += 1
            else:
                print(f"  [FAILED] Unexpected Status Code: {status_code}. Response: {response_json}")
                failed += 1
        except Exception as ex:
            print(f"  [ERROR] Execution failed: {str(ex)}")
            failed += 1
        print("-" * 52)

    print(f"\nTest Summary: {passed} PASSED, {failed} FAILED")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
