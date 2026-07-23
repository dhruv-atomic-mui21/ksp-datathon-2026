import sys
import os
import re
import logging
import json
import sqlite3
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

# Force UTF-8 stream encoding on Windows to prevent charmap codec errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def load_env_file():
    """Loads .env file into os.environ if present and keys not already set."""
    search_paths = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        ".env"
    ]
    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip('"').strip("'")
                            if key not in os.environ:
                                os.environ[key] = val
            except Exception:
                pass

load_env_file()

try:
    import pymysql
except ImportError:
    pymysql = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

# Setup Logger
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Database connection factory
# ----------------------------------------------------------------------
class DBConnection:
    """Simple wrapper for SQLite / MySQL / PostgreSQL connections."""
    def __init__(self, db_type='sqlite', **kwargs):
        self.db_type = db_type
        self.params = kwargs
        self.conn = None

    def connect(self):
        if self.db_type == 'sqlite':
            db_file = self.params.get('database', 'ksp_crime.db')
            # Look for db locally first
            if not os.path.exists(db_file):
                local_db = os.path.join(os.path.dirname(__file__), 'ksp_crime.db')
                if os.path.exists(local_db):
                    db_file = local_db
            self.conn = sqlite3.connect(db_file)
            self.conn.row_factory = sqlite3.Row
        elif self.db_type == 'mysql':
            if not pymysql:
                raise ImportError("pymysql module is not installed.")
            self.conn = pymysql.connect(
                host=self.params.get('host', 'localhost'),
                user=self.params.get('user'),
                password=self.params.get('password'),
                database=self.params.get('database'),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
        elif self.db_type == 'postgres':
            if not psycopg2:
                raise ImportError("psycopg2 module is not installed.")
            self.conn = psycopg2.connect(
                host=self.params.get('host', 'localhost'),
                user=self.params.get('user'),
                password=self.params.get('password'),
                dbname=self.params.get('database')
            )
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
        return self.conn

    def execute(self, sql: str) -> List[Dict[str, Any]]:
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(sql)
        if self.db_type == 'sqlite':
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            return cursor.fetchall()

    def close(self):
        if self.conn:
            self.conn.close()

# ----------------------------------------------------------------------
# NL2SQLEngine with DB execution and explanation
# ----------------------------------------------------------------------
SCHEMA_CONTEXT = """
Convert natural language to SQL for KSP Crime Database. Tables:
1. CaseMaster (CaseMasterID PK, CrimeNo, CaseNo, CrimeRegisteredDate, PoliceStationID FK, CaseCategoryID FK, GravityOffenceID, CrimeMajorHeadID FK, CrimeMinorHeadID FK, CaseStatusID FK, latitude, longitude, BriefFacts)
2. ComplainantDetails (ComplainantID PK, CaseMasterID FK, ComplainantName, AgeYear, GenderID)
3. Victim (VictimMasterID PK, CaseMasterID FK, VictimName, AgeYear, GenderID)
4. Accused (AccusedMasterID PK, CaseMasterID FK, AccusedName, AgeYear, GenderID, PhoneNo, Address, BankAccountNo)
5. ActSectionAssociation (CaseMasterID FK, ActID FK, SectionID FK)
6. Act (ActCode PK, ActDescription, ShortName)
7. Section (ActCode FK, SectionCode, SectionDescription)
8. CrimeHead (CrimeHeadID PK, CrimeGroupName)
9. CrimeSubHead (CrimeSubHeadID PK, CrimeHeadID FK, CrimeHeadName)
10. CaseStatusMaster (CaseStatusID PK, CaseStatusName)
11. District (DistrictID PK, DistrictName)
12. Unit (UnitID PK, UnitName, DistrictID FK)
13. CasteMaster (caste_master_id PK, caste_master_name)
14. ReligionMaster (ReligionID PK, ReligionName)
15. OccupationMaster (OccupationID PK, OccupationName)

RULES:
1. ONLY return the SQL statement. No markdown, no explanations, no code blocks.
2. Filter District name by JOINing CaseMaster -> Unit -> District.
3. Filter Crime category by JOINing CaseMaster -> CrimeSubHead.
4. Limit results to 100 rows.
"""

FEW_SHOT_EXAMPLES = """
Example 1: List all cases of murder in Bengaluru City.
SQL: SELECT CM.CaseMasterID, CM.CrimeNo, CM.CaseNo, CM.CrimeRegisteredDate, CM.BriefFacts FROM CaseMaster CM JOIN Unit U ON CM.PoliceStationID = U.UnitID JOIN District D ON U.DistrictID = D.DistrictID JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CSH.CrimeHeadName = 'Murder' AND D.DistrictName = 'Bengaluru City';

Example 2: How many thefts happened in December 2025?
SQL: SELECT COUNT(*) as TotalThefts FROM CaseMaster CM JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CSH.CrimeHeadName = 'Ordinary Theft' AND CM.CrimeRegisteredDate >= '2025-12-01' AND CM.CrimeRegisteredDate <= '2025-12-31';

Example 3: Search history for accused named 'Ramesh Gowda'.
SQL: SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, A.AccusedName, A.PhoneNo, CM.BriefFacts FROM CaseMaster CM JOIN Accused A ON CM.CaseMasterID = A.CaseMasterID WHERE A.AccusedName LIKE '%Ramesh Gowda%';

Example 4: Show status of cybercrime cases in Mysuru.
SQL: SELECT CM.CrimeNo, CSM.CaseStatusName, CM.BriefFacts FROM CaseMaster CM JOIN Unit U ON CM.PoliceStationID = U.UnitID JOIN District D ON U.DistrictID = D.DistrictID JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID JOIN CaseStatusMaster CSM ON CM.CaseStatusID = CSM.CaseStatusID WHERE CSH.CrimeHeadName = 'Cyber Crime (IT Act)' AND D.DistrictName = 'Mysuru';

Example 5 (Kannada Input): ಬೆಂಗಳೂರಿನಲ್ಲಿ ನಡೆದ ಕೊಲೆ ಪ್ರಕರಣಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿ
SQL: SELECT CM.CaseMasterID, CM.CrimeNo, CM.CaseNo, CM.CrimeRegisteredDate, CM.BriefFacts FROM CaseMaster CM JOIN Unit U ON CM.PoliceStationID = U.UnitID JOIN District D ON U.DistrictID = D.DistrictID JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CSH.CrimeHeadName = 'Murder' AND D.DistrictName = 'Bengaluru City';
"""

class NL2SQLEngine:
    def __init__(self, db_connection=None):
        self.db = db_connection
        
        # Priority: Environment variables (os.environ or loaded from .env/Catalyst config)
        load_env_file()
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            
        if self.api_key and self.api_key != "YOUR_GEMINI_API_KEY_HERE":
            self.has_llm = True
        else:
            self.has_llm = False
            logger.warning("GEMINI_API_KEY not configured in environment. Running in rule-based fallback mode.")
            
        self.conversation_history = []  # list of {role, text}

    def _call_llm(self, prompt: str) -> str:
        """Makes a single HTTP request to Google Gemini API using a pinned model to minimize API quota usage."""
        obscured_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if self.api_key else "None"
        
        # Single pinned target model
        target_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info(f"Executing LLM request using single model '{target_model}' (Key: {obscured_key})")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.5) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                logger.info(f"Gemini API call succeeded ({target_model})")
                return text
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"Gemini API Quota Exceeded / Rate Limited (429) for model '{target_model}'. Using instant fallback.")
            else:
                logger.warning(f"Gemini API model '{target_model}' failed with HTTP {e.code}: {e.reason}")
            raise e
        except Exception as e:
            logger.warning(f"Gemini API model '{target_model}' failed: {str(e)}")
            raise e

    def is_kannada(self, text: str) -> bool:
        kannada_pattern = re.compile(r'[\u0C80-\u0CFF]+')
        return bool(kannada_pattern.search(text))

    def generate_sql(self, natural_query: str, history: Optional[List[Dict]] = None) -> str:
        """
        Translates natural language query (English or Kannada) directly into SQL using single Gemini LLM call.
        """
        # 0. Check for greetings or small talk
        q_clean = natural_query.strip().lower().replace(".", "").replace("!", "")
        greetings = ["hi", "hello", "hey", "namaste", "good morning", "good afternoon", "hi there", "hello there"]
        if q_clean in greetings:
            return ""

        # 1. Build history context
        history_context = ""
        if history:
            history_context = "\nConversation context:\n"
            for turn in history[-4:]:  # last 2 turns
                if turn["role"] == "user":
                    history_context += f"User: {turn['text']}\n"
                else:
                    sql_info = f" [Executed SQL: {turn.get('sql')}]" if turn.get('sql') else ""
                    history_context += f"Assistant: {turn['text']}{sql_info}\n"

        # 2. Generate SQL directly from user's natural query (multilingual support built-in)
        sql = None
        if self.has_llm:
            prompt = f"{SCHEMA_CONTEXT}\n{FEW_SHOT_EXAMPLES}\n{history_context}\nTranslate this natural query (English or Kannada) directly into SQL: {natural_query}\nSQL:"
            try:
                response = self._call_llm(prompt)
                sql = response
            except Exception as e:
                logger.warning(f"Gemini SQL generation fallback triggered: {str(e)}")
                sql = self._generate_sql_fallback(natural_query)
        else:
            sql = self._generate_sql_fallback(natural_query)

        # 3. Clean SQL
        sql = self.clean_sql_query(sql)
        return sql

    def _generate_sql_fallback(self, query: str) -> str:
        """Rule-based fallback for common queries."""
        query_lower = query.lower()
        match_accused = re.search(r"(?:accused|history of|offender|criminal)\s+([\w\s]+)", query_lower)
        if match_accused or "accused" in query_lower:
            name = match_accused.group(1).strip() if match_accused else "ramesh"
            name = re.sub(r'^(?:named|called|is|for)\s+', '', name)
            return f"SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, A.AccusedName, A.PhoneNo, CM.BriefFacts FROM CaseMaster CM JOIN Accused A ON CM.CaseMasterID = A.CaseMasterID WHERE A.AccusedName LIKE '%{name}%' LIMIT 10;"
        if "hotspot" in query_lower or "thefts in" in query_lower:
            district = "Bengaluru City"
            if "mysuru" in query_lower: district = "Mysuru"
            elif "belagavi" in query_lower: district = "Belagavi"
            return f"SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, CM.latitude, CM.longitude, CM.BriefFacts FROM CaseMaster CM JOIN Unit U ON CM.PoliceStationID = U.UnitID JOIN District D ON U.DistrictID = D.DistrictID JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CSH.CrimeHeadName = 'Ordinary Theft' AND D.DistrictName = '{district}' LIMIT 50;"
        if "udr" in query_lower or "suspicious death" in query_lower:
            return "SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, CM.BriefFacts FROM CaseMaster CM JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CSH.CrimeHeadName = 'Suspicious / Unnatural Death' LIMIT 10;"
        if "heinous" in query_lower:
            return "SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, CSH.CrimeHeadName, CM.BriefFacts FROM CaseMaster CM JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CM.GravityOffenceID = 1 LIMIT 10;"
        return "SELECT CM.CaseMasterID, CM.CrimeNo, CM.CaseNo, CM.CrimeRegisteredDate, CM.BriefFacts FROM CaseMaster CM ORDER BY CM.CrimeRegisteredDate DESC LIMIT 10;"

    def clean_sql_query(self, query: str) -> str:
        if not query:
            return ""
        query = re.sub(r'```sql', '', query, flags=re.IGNORECASE)
        query = re.sub(r'```', '', query)
        query = query.strip()
        if query.endswith(';'):
            query = query[:-1]
        return query.strip()

    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """Execute the SQL and return results as list of dicts."""
        if not sql:
            return []
        try:
            return self.db.execute(sql)
        except Exception as e:
            logger.error(f"SQL execution error: {str(e)}")
            raise

    def generate_explanation(self, user_query: str, sql_query: str, results: List[Dict], is_kannada: bool = False) -> str:
        """
        Synthesizes a natural language RAG answer based on retrieved database rows.
        Falls back to a smart programmatic summary if LLM call fails.
        """
        q_clean = user_query.strip().lower().replace(".", "").replace("!", "")
        greetings = ["hi", "hello", "hey", "namaste", "good morning", "good afternoon", "hi there", "hello there"]
        is_greeting = q_clean in greetings

        # Helper for natural language fallback if LLM is down
        def _build_programmatic_fallback():
            if is_greeting:
                return "Hello! I am your intelligent conversational assistant for the Karnataka State Police crime database. How can I assist you with your investigation today?"
            if not results:
                return "No matching records were found in the Karnataka State Police crime database for your query. Try refining your search parameters or checking case numbers."
            first = results[0]
            count_key = next((k for k in first if 'count' in k.lower() or 'total' in k.lower()), None)
            if count_key:
                val = first[count_key]
                return f"Based on current KSP database records, a total of {val} matching records were found for your query."
            elif "CrimeNo" in first or "CaseMasterID" in first:
                recent_crime = first.get("CrimeNo") or first.get("CaseMasterID")
                date = first.get("CrimeRegisteredDate") or "N/A"
                facts = first.get("BriefFacts") or "Details available in CaseMaster."
                return f"Retrieved {len(results)} matching crime cases. Most recent record: Crime No. {recent_crime} registered on {date}. Key details: {facts}"
            elif "AccusedName" in first:
                name = first.get("AccusedName")
                phone = first.get("PhoneNo") or "N/A"
                return f"Retrieved {len(results)} accused records matching your query. Subject: {name} (Contact: {phone}). Check Link Analysis for associated network connections."
            else:
                sample_pairs = [f"{k}: {first[k]}" for k in list(first.keys())[:3]]
                return f"Retrieved {len(results)} matching records from the database. Summary: {', '.join(sample_pairs)}."

        if not self.has_llm:
            return _build_programmatic_fallback()

        try:
            if is_greeting:
                prompt = (
                    "You are 'KSP Investigation AI', an intelligent conversational assistant for Karnataka State Police. "
                    "The user sent a greeting. Respond with a warm, professional welcome. Tell them you can help query the crime database, "
                    "perform link analysis, search case histories, or check risk alerts in English or Kannada. Keep it concise (1-2 sentences)."
                )
            else:
                prompt = (
                    f"You are 'KSP Investigation AI', a senior law enforcement intelligence officer assistant for Karnataka State Police. "
                    f"Synthesize a clear, direct natural language answer for the investigating police officer based strictly on the retrieved database resources below.\n\n"
                    f"Police Officer's Question: '{user_query}'\n"
                    f"Executed SQL Database Query: '{sql_query}'\n"
                    f"Retrieved Database Results (up to 15 records): {json.dumps(results[:15], default=str, indent=2)}\n\n"
                    f"Instructions:\n"
                    f"1. Direct Answer (RAG): Answer the officer's question directly in natural language using the database data. If it's a count/total, state the exact count clearly.\n"
                    f"2. Specific Details: Synthesize specific details like Crime Numbers, accused names, registered dates, locations, or brief facts from the retrieved records.\n"
                    f"3. Actionable Intelligence: Provide 1 practical follow-up step (e.g. cross-referencing phone/bank details in Link Analysis, checking Repeat Offenders, or verifying accomplices).\n"
                    f"4. Tone: Professional, authoritative law enforcement assistant tone.\n"
                    f"5. Length: Keep response to 2 to 4 concise paragraphs or bullet points."
                )
            response = self._call_llm(prompt)
            return response
        except Exception as e:
            logger.warning(f"Gemini LLM call failed or rate limited (429): {str(e)}")
            return _build_programmatic_fallback()

    def run(self):
        """Interactive REPL for the agent."""
        print("\n" + "="*60)
        print("KSP Investigation AI Agent (type 'exit' to quit, 'show sql' to display generated SQL)")
        print("="*60 + "\n")

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("Goodbye!")
                    break

                if user_input.lower() == 'show sql':
                    if hasattr(self, '_last_sql') and self._last_sql:
                        print(f"SQL: {self._last_sql}")
                    else:
                        print("No SQL generated yet. Ask a question first.")
                    continue
                if user_input.lower() == 'help':
                    print("Commands: 'show sql' to view last SQL, 'exit' to quit.")
                    continue

                is_kan = self.is_kannada(user_input)
                sql = self.generate_sql(user_input, self.conversation_history)
                self._last_sql = sql

                try:
                    results = self.execute_sql(sql)
                except Exception as e:
                    print(f"Error executing SQL: {str(e)}")
                    print(f"Generated SQL: {sql}")
                    continue

                explanation = self.generate_explanation(user_input, sql, results, is_kan)
                print(f"Assistant: {explanation}")

                self.conversation_history.append({"role": "user", "text": user_input})
                self.conversation_history.append({"role": "assistant", "text": explanation})

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    db = DBConnection(db_type='sqlite', database='ksp_crime.db')
    agent = NL2SQLEngine(db)
    try:
        agent.run()
    finally:
        db.close()
