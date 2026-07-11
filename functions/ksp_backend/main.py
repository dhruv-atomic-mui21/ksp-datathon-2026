import json
import logging
from flask import Request, make_response
from database import DatabaseManager
from nl2sql import NL2SQLEngine
from analytics import AnalyticsEngine
from fpdf import FPDF

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize Singletons
db_manager = DatabaseManager()
nl2sql_engine = NL2SQLEngine()
analytics_engine = AnalyticsEngine(db_manager)

def handler(request: Request):
    """
    Main handler for Catalyst Advanced I/O Python function.
    Handles HTTP routing, CORS preflights, and analytical execution.
    """
    # 1. Enable CORS Support
    if request.method == 'OPTIONS':
        resp = make_response('', 204)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return resp

    # Parse path and request details
    path = request.path
    method = request.method
    logger.info(f"Incoming Request: {method} {path}")

    # Helper function to inject CORS headers into responses
    def cors_json_response(data, status_code=200):
        resp = make_response(json.dumps(data), status_code)
        resp.headers['Content-Type'] = 'application/json'
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return resp

    try:
        # Route 1: NL2SQL Chat Interface
        if path == "/api/chat" and method == 'POST':
            req_data = request.get_json() or {}
            query = req_data.get("query", "")
            history = req_data.get("history", [])
            user_info = req_data.get("user", {"email": "guest@ksp.gov.in", "role": "guest"})
            
            email = user_info.get("email", "guest@ksp.gov.in")
            role = user_info.get("role", "guest")

            # Generate SQL
            sql_query, is_kan = nl2sql_engine.generate_sql(query, history)
            
            # Execute SQL
            results = []
            error_message = None
            if sql_query:
                try:
                    results = db_manager.execute_query(sql_query)
                except Exception as db_err:
                    error_message = str(db_err)
                    logger.error(f"SQL execution error: {error_message}")
            
            # Generate Explanation
            if error_message:
                answer = f"The query generated invalid SQL syntax: {error_message}."
                if is_kan:
                    answer = f"ರಚಿಸಲಾದ SQL ವಾಕ್ಯರಚನೆ ಅಮಾನ್ಯವಾಗಿದೆ: {error_message}."
            else:
                answer = nl2sql_engine.generate_explanation(query, results, is_kannada=is_kan)

            # Record Audit Log
            db_manager.log_audit(email, role, "NL2SQL_CHAT", sql_query)

            # Update history
            history.append({"role": "user", "text": query})
            history.append({"role": "assistant", "text": answer, "sql": sql_query, "results": results})

            return cors_json_response({
                "answer": answer,
                "sql": sql_query,
                "results": results[:20], # limit to first 20 in UI
                "total_rows": len(results),
                "is_kannada": is_kan,
                "history": history
            })

        # Route 2: Criminal Network Graph
        elif path == "/api/network" and method == 'GET':
            case_id = request.args.get("case_id")
            accused_name = request.args.get("accused_name")
            
            network_data = analytics_engine.get_criminal_network(case_id, accused_name)
            return cors_json_response(network_data)

        # Route 3: Repeat Offenders
        elif path == "/api/repeat-offenders" and method == 'GET':
            offenders = analytics_engine.get_repeat_offenders()
            return cors_json_response(offenders)

        # Route 4: Geospatial & Hotspots
        elif path == "/api/geospatial" and method == 'GET':
            district = request.args.get("district")
            category = request.args.get("category")
            
            hotspots_data = analytics_engine.get_hotspots(district, category)
            return cors_json_response(hotspots_data)

        # Route 5: Predictive Risk Scoring
        elif path == "/api/predictive" and method == 'GET':
            risk_data = analytics_engine.get_predictive_risk()
            return cors_json_response(risk_data)

        # Route 6: Anomaly Detection
        elif path == "/api/anomalies" and method == 'GET':
            anomalies = analytics_engine.get_anomalies()
            return cors_json_response(anomalies)

        # Route 7: Sociological Correlations
        elif path == "/api/sociological" and method == 'GET':
            insights = analytics_engine.get_sociological_insights()
            return cors_json_response(insights)

        # Route 8: Investigator Leads
        elif path == "/api/leads" and method == 'GET':
            case_id = request.args.get("case_id")
            if not case_id:
                return cors_json_response({"error": "Missing case_id"}, 400)
            
            leads_data = analytics_engine.get_leads_and_summary(int(case_id))
            return cors_json_response(leads_data)

        # Route 9: Audit Logs (Supervisor & Policymaker only)
        elif path == "/api/audit-logs" and method == 'GET':
            role = request.args.get("role", "guest")
            if role.lower() not in ["supervisor", "policymaker"]:
                return cors_json_response({"error": "Unauthorized access. Supervisor role required."}, 403)
                
            sql = "SELECT * FROM AuditLog ORDER BY Timestamp DESC LIMIT 50"
            logs = db_manager.execute_query(sql)
            return cors_json_response(logs)

        # Route 10: PDF Session Export
        elif path == "/api/export-pdf" and method == 'POST':
            req_data = request.get_json() or {}
            history = req_data.get("history", [])
            
            # Construct PDF using fpdf2
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "KSP Conversational AI - Investigation Report", ln=True, align="C")
            pdf.ln(10)
            
            for turn_idx, turn in enumerate(history, 1):
                role = "User" if turn["role"] == "user" else "Assistant"
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, f"{turn_idx}. {role}:", ln=True)
                pdf.set_font("Helvetica", "", 10)
                
                # Turn text
                text = turn.get("text", "")
                # Clean non-ascii
                text_clean = text.encode("latin-1", "ignore").decode("latin-1")
                pdf.multi_cell(0, 6, text_clean)
                
                if role == "Assistant" and "sql" in turn and turn["sql"]:
                    pdf.set_font("Courier", "I", 9)
                    pdf.multi_cell(0, 5, f"Executed SQL: {turn['sql']}")
                pdf.ln(5)
                
            pdf_bytes = pdf.output()
            
            # Return as PDF file download
            resp = make_response(pdf_bytes)
            resp.headers['Content-Type'] = 'application/pdf'
            resp.headers['Content-Disposition'] = 'attachment; filename=investigation_report.pdf'
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp

        # Catch-all endpoint not found
        else:
            return cors_json_response({"error": "Endpoint not found"}, 404)

    except Exception as e:
        logger.error(f"Global server error: {str(e)}")
        return cors_json_response({"error": f"Internal Server Error: {str(e)}"}, 500)
