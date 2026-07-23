import sys
import json
import logging
import time
import os
import gzip
import urllib.request
import urllib.error
from flask import Request, make_response
from database import DatabaseManager
from nl2sql import NL2SQLEngine
from analytics import AnalyticsEngine
from fpdf import FPDF

# Force UTF-8 stream encoding on Windows to prevent charmap codec errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Configure logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("ksp")

# Initialize Singletons
db_manager = DatabaseManager()
nl2sql_engine = NL2SQLEngine(db_manager)
analytics_engine = AnalyticsEngine(db_manager)

# IP-based rate limiting tracking (Anti-DDoS)
ip_request_timestamps = {}
RATE_LIMIT_MAX_REQUESTS = 60  # max 60 requests
RATE_LIMIT_WINDOW = 60        # per 60 seconds

def handler(request: Request):
    """
    Main handler for Catalyst Advanced I/O Python function.
    Handles HTTP routing, CORS preflights, and analytical execution.
    """
    origin = request.headers.get("Origin") or request.headers.get("origin") or "*"
    req_headers = request.headers.get("Access-Control-Request-Headers") or "Content-Type, Authorization, Accept-Encoding, X-Requested-With"

    # 1. Enable CORS Support for OPTIONS preflight
    if request.method == 'OPTIONS':
        resp = make_response('', 204)
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = req_headers
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        resp.headers['Access-Control-Max-Age'] = '86400'
        return resp

    # 2. Rate Limiting Check (Anti-DDoS Guard)
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    current_time = time.time()
    if client_ip not in ip_request_timestamps:
        ip_request_timestamps[client_ip] = []
    
    # Filter timestamps to keep only those within the active time window
    ip_request_timestamps[client_ip] = [t for t in ip_request_timestamps[client_ip] if current_time - t < RATE_LIMIT_WINDOW]
    
    if len(ip_request_timestamps[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"DDoS Protection: Rate limit exceeded for client IP: {client_ip}")
        resp = make_response(json.dumps({"error": "Too many requests. Please try again in a minute."}), 429)
        resp.headers['Content-Type'] = 'application/json'
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = req_headers
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        return resp
        
    ip_request_timestamps[client_ip].append(current_time)

    # Parse path and request details
    path = request.path or "/"
    # Strip prefix if present in request.path
    for prefix in ["/server/ksp_functions", "/ksp_functions"]:
        if path.startswith(prefix):
            path = path[len(prefix):]
    if not path:
        path = "/"

    method = request.method
    logger.info(f"Incoming Request: {method} {path} (Origin: {origin})")

    # Helper function to inject CORS headers and gzip compression into responses
    def cors_json_response(data, status_code=200):
        json_str = json.dumps(data, ensure_ascii=False)
        body_bytes = json_str.encode('utf-8')
        accept_enc = request.headers.get('Accept-Encoding', '').lower()
        
        if 'gzip' in accept_enc:
            compressed = gzip.compress(body_bytes)
            resp = make_response(compressed, status_code)
            resp.headers['Content-Encoding'] = 'gzip'
        else:
            resp = make_response(body_bytes, status_code)

        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = req_headers
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        return resp

    try:
        # Route 1: NL2SQL Chat Interface
        if path == "/api/chat" and method == 'POST':
            req_data = request.get_json() or {}
            query = req_data.get("query", "")
            history = req_data.get("history", [])
            # Keep only the last 6 entries (3 turns) to prevent context inflation
            history = history[-6:]
            
            user_info = req_data.get("user", {"email": "guest@ksp.gov.in", "role": "guest"})
            
            email = user_info.get("email", "guest@ksp.gov.in")
            role = user_info.get("role", "guest")

            # Generate SQL
            is_kan = nl2sql_engine.is_kannada(query)
            sql_query = nl2sql_engine.generate_sql(query, history)
            
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
                answer = "I encountered an issue retrieving those records. Please try rephrasing your search query, or specify the request details again."
                if is_kan:
                    answer = "ಕ್ಷಮಿಸಿ, ಆ ದಾಖಲೆಗಳನ್ನು ಹಿಂಪಡೆಯುವಲ್ಲಿ ದೋಷ ಕಂಡುಬಂದಿದೆ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಬೇರೆ ರೀತಿಯಲ್ಲಿ ಕೇಳಿ."
            else:
                answer = nl2sql_engine.generate_explanation(query, sql_query, results, is_kannada=is_kan)

            # Record Audit Log
            db_manager.log_audit(email, role, "NL2SQL_CHAT", sql_query)

            # Update history (Exclude results database rows to prevent request size inflation)
            history.append({"role": "user", "text": query})
            history.append({"role": "assistant", "text": answer, "sql": sql_query})

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
            pdf.cell(pdf.epw, 10, "KSP Conversational AI - Investigation Report", new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(5)
            
            for turn_idx, turn in enumerate(history, 1):
                role = "User" if turn.get("role") == "user" else "Assistant"
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(pdf.epw, 7, f"{turn_idx}. {role}:", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)
                
                # Turn text
                text = turn.get("text", "")
                # Safely convert non-latin1 characters to ascii/latin1 to prevent FPDF encoding errors
                text_clean = text.encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(pdf.epw, 6, text_clean, new_x="LMARGIN", new_y="NEXT")
                
                if role == "Assistant" and turn.get("sql"):
                    pdf.set_font("Courier", "I", 9)
                    sql_text = f"Executed SQL: {turn.get('sql')}"
                    sql_clean = sql_text.encode("latin-1", "replace").decode("latin-1")
                    pdf.multi_cell(pdf.epw, 5, sql_clean, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)
                
            pdf_bytes = bytes(pdf.output())
            
            # Return as PDF file download
            resp = make_response(pdf_bytes)
            resp.headers['Content-Type'] = 'application/pdf'
            resp.headers['Content-Disposition'] = 'attachment; filename=investigation_report.pdf'
            resp.headers['Access-Control-Allow-Origin'] = origin
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = req_headers
            resp.headers['Access-Control-Allow-Credentials'] = 'true'
            return resp

        # Route 11: Sarvam TTS
        elif path == "/api/tts" and method == 'POST':
            req_data = request.get_json() or {}
            text = req_data.get("text", "")
            lang = req_data.get("language", "en-IN")
            
            api_key = os.environ.get("SARVAM_API_KEY")
                
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {
                "Content-Type": "application/json",
                "api-subscription-key": api_key
            }
            payload = {
                "inputs": [text[:2500]], # Sarvam uses inputs for array of text in some versions, but standard is inputs
                "target_language_code": lang
            }
            # The search said "text", but some say "inputs". Let's support the one we found exactly in the search:
            payload = {
                "text": text[:2500],
                "target_language_code": lang,
                "model": "bulbul:v3"
            }
            
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    
                audios = res_data.get("audios", [])
                if audios:
                    return cors_json_response({"audio_base64": audios[0]})
                return cors_json_response({"error": "No audio returned from Sarvam"}, 500)
            except Exception as e:
                logger.error(f"Sarvam API call failed: {str(e)}")
                return cors_json_response({"error": f"Sarvam TTS Error: {str(e)}"}, 500)

        # Catch-all endpoint not found
        else:
            return cors_json_response({"error": "Endpoint not found"}, 404)

    except Exception as e:
        logger.error(f"Global server error: {str(e)}")
        return cors_json_response({"error": f"Internal Server Error: {str(e)}"}, 500)
