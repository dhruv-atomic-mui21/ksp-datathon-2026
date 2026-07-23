import sys
import os
import time
import json
import statistics
import tracemalloc

# Ensure functions/ksp_functions is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "functions", "ksp_functions"))

os.environ["DB_TYPE"] = "sqlite"

from main import handler, ip_request_timestamps
from database import DatabaseManager
from nl2sql import NL2SQLEngine, DBConnection
from analytics import AnalyticsEngine
from flask import Flask

app = Flask("benchmark_app")

req_counter = 0

class MockRequest:
    def __init__(self, path, method="GET", json_data=None, args=None, headers=None):
        global req_counter
        req_counter += 1
        self.path = path
        self.method = method
        self.json_data = json_data or {}
        self._args_dict = args or {}
        self.headers = headers or {}
        # Vary IP address so rate limiter doesn't block mock requests during benchmarks
        self.remote_addr = f"127.0.{ (req_counter // 50) % 250 }.{ req_counter % 250 }"

    def get_json(self):
        return self.json_data

    @property
    def args(self):
        class ArgsWrapper(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        return ArgsWrapper(self._args_dict)

def benchmark_function(func, iterations=30, warmup=2):
    # Warmup runs
    for _ in range(warmup):
        try:
            ip_request_timestamps.clear()
            func()
        except Exception:
            pass

    tracemalloc.start()
    times = []
    payload_sizes = []
    
    for _ in range(iterations):
        ip_request_timestamps.clear()
        t0 = time.perf_counter()
        res = func()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0) # convert to ms
        
        # Calculate payload size if available
        if hasattr(res, 'data'):
            payload_sizes.append(len(res.data))
        elif isinstance(res, (dict, list)):
            try:
                payload_sizes.append(len(json.dumps(res, default=str)))
            except Exception:
                payload_sizes.append(0)
        else:
            payload_sizes.append(0)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    times.sort()
    p50 = statistics.median(times)
    p95 = times[int(0.95 * len(times))]
    p99 = times[int(0.99 * len(times))]
    avg = statistics.mean(times)
    min_t = min(times)
    max_t = max(times)
    avg_payload_kb = (statistics.mean(payload_sizes) / 1024.0) if payload_sizes else 0.0
    throughput = (1000.0 / avg) if avg > 0 else 0.0

    return {
        "iterations": iterations,
        "min_ms": round(min_t, 2),
        "mean_ms": round(avg, 2),
        "median_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max_t, 2),
        "throughput_rps": round(throughput, 1),
        "payload_kb": round(avg_payload_kb, 2),
        "peak_mem_kb": round(peak / 1024.0, 2)
    }

def run_benchmarks():
    print("=" * 70)
    print("      KARNATAKA STATE POLICE (KSP) DATATHON 2026 BENCHMARK SUITE      ")
    print("=" * 70)

    db_path = os.path.join(os.path.dirname(__file__), "..", "functions", "ksp_functions", "ksp_crime.db")
    db_mgr = DatabaseManager(db_type="sqlite", sqlite_path=db_path)
    db_conn = DBConnection(db_type="sqlite", database=db_path)
    engine = NL2SQLEngine(db_connection=db_conn)
    analytics = AnalyticsEngine(db_mgr)

    results = {
        "challenge_01": {},
        "challenge_02": {}
    }

    # ----------------------------------------------------
    # CHALLENGE 01 BENCHMARKS
    # ----------------------------------------------------
    print("\n--- Running Challenge 01 Benchmarks (Intelligent Conversational AI) ---")

    # C1.1 Rule-Based NL2SQL Parsing Speed
    print("[C1.1] Rule-Based Query Intent Parsing & Pattern Matching...")
    def c1_1():
        return engine._generate_sql_fallback("Show all theft cases in Bengaluru City")
    results["challenge_01"]["rule_based_nl2sql_parse"] = benchmark_function(c1_1, iterations=50)

    # C1.2 Database Query Execution Latency (Simple vs Complex JOIN)
    print("[C1.2a] Simple SQL Query Execution...")
    def c1_2a():
        conn = engine.db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM CaseMaster WHERE CaseMasterID <= 50")
        return cursor.fetchall()
    results["challenge_01"]["sql_simple_query_exec"] = benchmark_function(c1_2a, iterations=50)

    print("[C1.2b] Complex Relational 4-Way JOIN Query Execution...")
    def c1_2b():
        conn = engine.db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.CrimeNo, d.DistrictName, a.AccusedName, a.PhoneNo
            FROM CaseMaster c
            JOIN Unit u ON c.PoliceStationID = u.UnitID
            JOIN District d ON u.DistrictID = d.DistrictID
            JOIN Accused a ON c.CaseMasterID = a.CaseMasterID
            LIMIT 100
        """)
        return cursor.fetchall()
    results["challenge_01"]["sql_complex_join_exec"] = benchmark_function(c1_2b, iterations=50)

    # C1.3 End-to-End Chat API Response (English Query)
    print("[C1.3] POST /api/chat (English Query End-to-End)...")
    def c1_3():
        req = MockRequest("/api/chat", "POST", json_data={
            "query": "Show accused persons in case FIR 101/2025",
            "history": [],
            "user": {"email": "io.patil@ksp.gov.in", "role": "investigator"}
        })
        with app.app_context():
            return handler(req)
    results["challenge_01"]["chat_api_english_e2e"] = benchmark_function(c1_3, iterations=15)

    # C1.4 End-to-End Chat API Response (Kannada Query with Translation Fallback)
    print("[C1.4] POST /api/chat (Kannada Query End-to-End)...")
    def c1_4():
        req = MockRequest("/api/chat", "POST", json_data={
            "query": "ಕಳ್ಳತನ ಪ್ರಕರಣಗಳ ವಿವರ ನೀಡಿ",
            "history": [],
            "user": {"email": "io.patil@ksp.gov.in", "role": "investigator"}
        })
        with app.app_context():
            return handler(req)
    results["challenge_01"]["chat_api_kannada_e2e"] = benchmark_function(c1_4, iterations=15)

    # C1.5 PDF Investigation Report Generation
    print("[C1.5] POST /api/export-pdf (Structured Case PDF Report Generation)...")
    def c1_5():
        req = MockRequest("/api/export-pdf", "POST", json_data={
            "messages": [
                {"role": "user", "text": "Show me details for case FIR 101/2025"},
                {"role": "assistant", "text": "Found 3 accused suspects associated with stolen property valued at ₹4,50,000.", "sql": "SELECT * FROM CaseMaster WHERE CaseMasterID=1"}
            ],
            "case_id": "FIR 101/2025"
        })
        with app.app_context():
            return handler(req)
    results["challenge_01"]["pdf_export_generation"] = benchmark_function(c1_5, iterations=30)


    # ----------------------------------------------------
    # CHALLENGE 02 BENCHMARKS
    # ----------------------------------------------------
    print("\n--- Running Challenge 02 Benchmarks (AI-Driven Crime Analytics & Link-Analysis) ---")

    # C2.1 Network Graph Construction (Full Node & Edge Build)
    print("[C2.1a] Network Graph Construction (4,200+ Nodes & 4,000+ Edges Cold Start)...")
    def c2_1_uncached():
        analytics._cache.clear()
        return analytics.get_criminal_network()
    results["challenge_02"]["criminal_network_uncached_cold_start"] = benchmark_function(c2_1_uncached, iterations=10, warmup=1)

    print("[C2.1b] Network Graph Fetch (Cached Speed)...")
    def c2_1_cached():
        return analytics.get_criminal_network()
    results["challenge_02"]["criminal_network_cached"] = benchmark_function(c2_1_cached, iterations=50)

    # C2.2 Filtered Case Network Graph Extraction
    print("[C2.2] Sub-network Extraction (Target Case Link Analysis)...")
    def c2_2():
        analytics._cache.clear()
        return analytics.get_criminal_network(filter_case_id=1)
    results["challenge_02"]["subnetwork_extraction"] = benchmark_function(c2_2, iterations=40)

    # C2.3 Repeat Offenders & Gang Connected Components
    print("[C2.3] Repeat Offenders & Gang Detection Algorithm...")
    def c2_3():
        analytics._cache.clear()
        return analytics.get_repeat_offenders()
    results["challenge_02"]["repeat_offenders_detection"] = benchmark_function(c2_3, iterations=30)

    # C2.4 Geospatial DBSCAN Clustering & Hotspot Detection
    print("[C2.4] Geospatial DBSCAN Clustering & Hotspot Latency...")
    def c2_4():
        analytics._cache.clear()
        return analytics.get_hotspots(district_name="Bengaluru City")
    results["challenge_02"]["geospatial_dbscan_clustering"] = benchmark_function(c2_4, iterations=30)

    # C2.5 Predictive Risk Scoring & SHAP Feature Attribution
    print("[C2.5] Predictive Risk Model Scoring & SHAP Feature Attribution...")
    def c2_5():
        analytics._cache.clear()
        return analytics.get_predictive_risk()
    results["challenge_02"]["predictive_risk_shap_scoring"] = benchmark_function(c2_5, iterations=30)

    # C2.6 IsolationForest Anomaly Detection Engine
    print("[C2.6] IsolationForest Crime Anomaly Detection Engine...")
    def c2_6():
        analytics._cache.clear()
        return analytics.get_anomalies()
    results["challenge_02"]["isolation_forest_anomaly_detection"] = benchmark_function(c2_6, iterations=30)

    # C2.7 Sociological Cross-Tabulation & Spike Detection
    print("[C2.7] Sociological Cross-Tabulation & Monthly Spike Alerts...")
    def c2_7():
        analytics._cache.clear()
        return analytics.get_sociological_insights()
    results["challenge_02"]["sociological_cross_tabulation"] = benchmark_function(c2_7, iterations=40)

    # C2.8 Audit Logging & RBAC Access Policy Compliance
    print("[C2.8] RBAC Security Verification & Supervisor Audit Logs...")
    def c2_8():
        req = MockRequest("/api/audit-logs", "GET", args={"role": "supervisor"})
        with app.app_context():
            return handler(req)
    results["challenge_02"]["audit_logs_rbac_auth"] = benchmark_function(c2_8, iterations=50)

    # Save benchmark results to file
    out_file = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"BENCHMARK COMPLETE! Raw JSON saved to: {out_file}")
    print("=" * 70)

    return results

if __name__ == "__main__":
    run_benchmarks()
