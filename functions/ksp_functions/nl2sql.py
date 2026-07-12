import os
import re
import logging
import json
import sqlite3
from typing import List, Dict, Any, Optional
import google.generativeai as genai

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
You are a SQL expert converting natural language into SQL queries for the Karnataka State Police (KSP) Crime Database.
The database has the following tables and columns:

1. CaseMaster (CaseMasterID INT PK, CrimeNo VARCHAR, CaseNo VARCHAR, CrimeRegisteredDate DATE, PolicePersonID INT FK, PoliceStationID INT FK, CaseCategoryID INT FK, GravityOffenceID INT FK, CrimeMajorHeadID INT FK, CrimeMinorHeadID INT FK, CaseStatusID INT FK, CourtID INT FK, IncidentFromDate DATETIME, IncidentToDate DATETIME, InfoReceivedPSDate DATETIME, latitude DECIMAL, longitude DECIMAL, BriefFacts TEXT)
2. ComplainantDetails (ComplainantID INT PK, CaseMasterID INT FK, ComplainantName VARCHAR, AgeYear INT, OccupationID INT FK, ReligionID INT FK, CasteID INT FK, GenderID INT)
3. Victim (VictimMasterID INT PK, CaseMasterID INT FK, VictimName VARCHAR, AgeYear INT, GenderID INT, VictimPolice VARCHAR)
4. Accused (AccusedMasterID INT PK, CaseMasterID INT FK, AccusedName VARCHAR, AgeYear INT, GenderID INT, PersonID VARCHAR, PhoneNo VARCHAR, Address VARCHAR, BankAccountNo VARCHAR)
5. ActSectionAssociation (CaseMasterID INT FK, ActID VARCHAR FK, SectionID VARCHAR FK, ActOrderID INT, SectionOrderID INT)
6. Act (ActCode VARCHAR PK, ActDescription VARCHAR, ShortName VARCHAR, Active BIT)
7. Section (ActCode VARCHAR FK, SectionCode VARCHAR, SectionDescription TEXT, Active BIT)
8. CrimeHead (CrimeHeadID INT PK, CrimeGroupName VARCHAR, Active BIT)
9. CrimeSubHead (CrimeSubHeadID INT PK, CrimeHeadID INT FK, CrimeHeadName VARCHAR, SeqID INT)
10. CaseStatusMaster (CaseStatusID INT PK, CaseStatusName VARCHAR)
11. District (DistrictID INT PK, DistrictName VARCHAR)
12. Unit (UnitID INT PK, UnitName VARCHAR, TypeID INT, DistrictID INT FK)
13. CasteMaster (caste_master_id INT PK, caste_master_name VARCHAR)
14. ReligionMaster (ReligionID INT PK, ReligionName VARCHAR)
15. OccupationMaster (OccupationID INT PK, OccupationName VARCHAR)

RULES FOR SQL GENERATION:
1. ONLY return the SQL statement. No markdown, no code fences, no explanations.
2. The query MUST be compatible with standard SQL.
3. Use standard functions like COUNT, SUM, AVG, datetime functions.
4. When filtering by District name, JOIN CaseMaster with Unit and District.
5. When filtering by Crime category, JOIN CaseMaster with CrimeSubHead.
6. Limit result set to a maximum of 100 rows unless specified otherwise.
7. Use table aliases clearly.
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
"""

TRANSLATE_TO_ENG_PROMPT = "You are a bilingual English-Kannada translator for a police application. Translate the following Kannada query into simple English. Output ONLY the English translation, no other text:\n"
TRANSLATE_TO_KAN_PROMPT = "You are a bilingual English-Kannada translator for a police application. Translate the following English response into Kannada. Output ONLY the Kannada translation. Do not translate code, SQL, or numbers. Clearly state the response is translation-assisted at the end:\n"

class NL2SQLEngine:
    def __init__(self, db_connection=None):
        self.db = db_connection
        # Configure Gemini
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            self.has_llm = True
        else:
            self.has_llm = False
            logger.warning("GEMINI_API_KEY environment variable not set. Running in rule-based fallback mode.")
        self.conversation_history = []  # list of {role, text}

    def is_kannada(self, text: str) -> bool:
        kannada_pattern = re.compile(r'[\u0C80-\u0CFF]+')
        return bool(kannada_pattern.search(text))

    def translate_kannada_to_english(self, kannada_query: str) -> str:
        if not self.has_llm:
            # Simple fallback
            lowered = kannada_query.lower()
            if "ಕೊಲೆ" in lowered: return "murder"
            if "ಕಳ್ಳತನ" in lowered: return "theft"
            if "ಬೆಂಗಳೂರು" in lowered: return "Bengaluru City"
            return kannada_query
        try:
            response = self.model.generate_content(TRANSLATE_TO_ENG_PROMPT + kannada_query)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Kannada to English translation error: {str(e)}")
            return kannada_query

    def translate_english_to_kannada(self, english_text: str) -> str:
        if not self.has_llm:
            return english_text + "\n\n(ಕನ್ನಡ ಭಾಷಾಂತರ ಲಭ್ಯವಿಲ್ಲ - GEMINI_API_KEY not set)"
        try:
            response = self.model.generate_content(TRANSLATE_TO_KAN_PROMPT + english_text)
            return response.text.strip() + "\n\n*(ಕನ್ನಡ ಅನುವಾದ ನೆರವು ಲಭ್ಯವಿದೆ - Translation Assisted)*"
        except Exception as e:
            logger.error(f"English to Kannada translation error: {str(e)}")
            return english_text + "\n\n*(ಅನುವಾದ ದೋಷ - Translation Error)*"

    def generate_sql(self, natural_query: str, history: Optional[List[Dict]] = None) -> str:
        """
        Translates a natural language query into SQL using Gemini or fallback.
        """
        # 1. Check if the input is Kannada, and translate to English
        is_kan = self.is_kannada(natural_query)
        english_query = natural_query
        if is_kan:
            english_query = self.translate_kannada_to_english(natural_query)
            logger.info(f"Translated Kannada query: '{natural_query}' -> '{english_query}'")

        # 2. Build history context (injecting previous executed SQL strings so the LLM remembers its actions)
        history_context = ""
        if history:
            history_context = "\nConversation context:\n"
            for turn in history[-4:]:  # last 2 turns
                if turn["role"] == "user":
                    history_context += f"User: {turn['text']}\n"
                else:
                    sql_info = f" [Executed SQL: {turn.get('sql')}]" if turn.get('sql') else ""
                    history_context += f"Assistant: {turn['text']}{sql_info}\n"

        # 3. Generate SQL
        sql = None
        if self.has_llm:
            prompt = f"{SCHEMA_CONTEXT}\n{FEW_SHOT_EXAMPLES}\n{history_context}\nTranslate this natural query into SQL: {english_query}\nSQL:"
            try:
                response = self.model.generate_content(prompt)
                sql = response.text.strip()
            except Exception as e:
                logger.error(f"Gemini SQL generation failed: {str(e)}")
                sql = self._generate_sql_fallback(english_query)
        else:
            sql = self._generate_sql_fallback(english_query)

        # 4. Clean SQL
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
        try:
            return self.db.execute(sql)
        except Exception as e:
            logger.error(f"SQL execution error: {str(e)}")
            raise

    def generate_explanation(self, user_query: str, sql_query: str, results: List[Dict], is_kannada: bool = False) -> str:
        """
        Ask Gemini to explain the output based on the user query and SQL.
        If no API key, return a programmatic summary.
        """
        if not self.has_llm:
            if not results:
                explanation = "No matching records were found in the crime database for your query."
                if is_kannada:
                    return "ನಿಮ್ಮ ಪ್ರಶ್ನೆಗೆ ಅಪರಾಧ ಡೇಟಾಬೇಸ್‌ನಲ್ಲಿ ಯಾವುದೇ ಹೊಂದಾಣಿಕೆಯ ದಾಖಲೆಗಳು ಕಂಡುಬಂದಿಲ್ಲ."
                return explanation
            first = results[0]
            if "CrimeNo" in first:
                explanation = f"Found {len(results)} matching cases. Most recent: Crime No. {first.get('CrimeNo')} registered on {first.get('CrimeRegisteredDate') or 'N/A'}. Brief facts: {first.get('BriefFacts', 'No facts')}."
            elif "AccusedName" in first:
                explanation = f"Retrieved {len(results)} accused records. Detail: {first.get('AccusedName')}, Phone: {first.get('PhoneNo', 'N/A')}."
            else:
                keys = list(first.keys())[:3]
                vals = [f"{k}: {first[k]}" for k in keys]
                explanation = f"Retrieved {len(results)} records. Sample: {', '.join(vals)}."
            if is_kannada:
                return self.translate_english_to_kannada(explanation) if self.has_llm else explanation
            return explanation

        try:
            q_clean = user_query.strip().lower().replace(".", "").replace("!", "")
            if q_clean in ["hi", "hello", "hey", "namaste", "good morning", "good afternoon", "hi there", "hello there"]:
                prompt = (
                    "You are 'KSP Investigation AI', an intelligent conversational assistant for Karnataka State Police. "
                    "The user sent a greeting. Respond with a warm, professional welcome. Tell them you can help query the crime database, "
                    "perform link analysis, search case histories, or check risk alerts in English or Kannada. Keep it concise (1-2 sentences)."
                )
            else:
                prompt = (
                    f"You are a specialized AI assistant for Karnataka State Police. Analyze the following database search results and provide "
                    f"a professional, clear summary back to the police officer.\n\n"
                    f"Police Officer's Question: '{user_query}'\n"
                    f"Executed SQL Database Query: '{sql_query}'\n"
                    f"Database Results (up to 10 rows): {json.dumps(results[:10], default=str, indent=2)}\n\n"
                    f"Instructions:\n"
                    f"1. Direct Answer: Answer the officer's question directly based on the database results.\n"
                    f"2. Detail & Insights: Include key details such as Crime Numbers, accused names, registered dates, and brief facts.\n"
                    f"3. Actionable Suggestion: Suggest a next logical step (e.g., check phone numbers/bank accounts in the Link Analysis graph under Challenge 02, or verify accomplices).\n"
                    f"4. Professional Tone: Maintain a strict, helpful police intelligence officer tone.\n"
                    f"5. Keep it concise: Output 3-4 sentences total."
                )
            response = self.model.generate_content(prompt)
            explanation_eng = response.text.strip()
            if is_kannada:
                return self.translate_english_to_kannada(explanation_eng)
            return explanation_eng
        except Exception as e:
            logger.error(f"Gemini explanation generation failed: {str(e)}")
            return f"Retrieved {len(results)} records matching your query."

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
