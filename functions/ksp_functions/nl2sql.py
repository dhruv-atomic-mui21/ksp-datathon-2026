import os
import re
import logging
import google.generativeai as genai

# Setup Logger
logger = logging.getLogger()

# Detailed DB Schema description to feed the LLM
SCHEMA_CONTEXT = """
You are a SQL expert converting natural language into SQL queries for the Karnataka State Police (KSP) Crime Database.
The database has the following tables and columns:

1. CaseMaster (CaseMasterID INT PK, CrimeNo VARCHAR, CaseNo VARCHAR, CrimeRegisteredDate DATE, PolicePersonID INT FK, PoliceStationID INT FK, CaseCategoryID INT FK, GravityOffenceID INT FK, CrimeMajorHeadID INT FK, CrimeMinorHeadID INT FK, CaseStatusID INT FK, CourtID INT FK, IncidentFromDate DATETIME, IncidentToDate DATETIME, InfoReceivedPSDate DATETIME, latitude DECIMAL, longitude DECIMAL, BriefFacts TEXT)
   - CrimeNo is the unique identifier (e.g. 104430006202600001).
   - CaseNo is the running serial per station (e.g., 202600001).
   - PoliceStationID references Unit(UnitID).
   - CrimeMajorHeadID references CrimeHead(CrimeHeadID).
   - CrimeMinorHeadID references CrimeSubHead(CrimeSubHeadID).
   - CaseStatusID references CaseStatusMaster(CaseStatusID).
   - GravityOffenceID: 1 (Heinous), 2 (Non-Heinous).

2. ComplainantDetails (ComplainantID INT PK, CaseMasterID INT FK, ComplainantName VARCHAR, AgeYear INT, OccupationID INT FK, ReligionID INT FK, CasteID INT FK, GenderID INT)
   - GenderID: 1 (Male), 2 (Female), 3 (Transgender).
   - CasteID references CasteMaster(caste_master_id).
   - ReligionID references ReligionMaster(ReligionID).
   - OccupationID references OccupationMaster(OccupationID).

3. Victim (VictimMasterID INT PK, CaseMasterID INT FK, VictimName VARCHAR, AgeYear INT, GenderID INT, VictimPolice VARCHAR)
   - VictimPolice: '1' if the victim is a police officer, '0' otherwise.

4. Accused (AccusedMasterID INT PK, CaseMasterID INT FK, AccusedName VARCHAR, AgeYear INT, GenderID INT, PersonID VARCHAR, PhoneNo VARCHAR, Address VARCHAR, BankAccountNo VARCHAR)
   - PersonID: Sorting index like 'A1', 'A2'.
   - PhoneNo, Address, BankAccountNo are used for network linking.

5. ActSectionAssociation (CaseMasterID INT FK, ActID VARCHAR FK, SectionID VARCHAR FK, ActOrderID INT, SectionOrderID INT)
   - References Section(ActCode, SectionCode).

6. Act (ActCode VARCHAR PK, ActDescription VARCHAR, ShortName VARCHAR, Active BIT)
   - Codes: 'IPC', 'BNS', 'NDPS', 'Excise', 'KPAct', 'ITAct'.

7. Section (ActCode VARCHAR FK, SectionCode VARCHAR, SectionDescription TEXT, Active BIT)

8. CrimeHead (CrimeHeadID INT PK, CrimeGroupName VARCHAR, Active BIT)
   - GroupName: 'Crimes Against Body', 'Crimes Against Property', 'Economic Offences', 'Crimes Against Women', 'Special & Local Laws (SLL)', 'UDR / Accidental Deaths'.

9. CrimeSubHead (CrimeSubHeadID INT PK, CrimeHeadID INT FK, CrimeHeadName VARCHAR, SeqID INT)
   - Sub categories: 'Murder', 'Attempt to Murder', 'Grievous Hurt', 'Robbery', 'Ordinary Theft', 'Cheating & Corporate Fraud', 'Cyber Crime (IT Act)', 'Rape', 'Dowry Harassment (498A)', 'NDPS Act Offences', 'Suspicious / Unnatural Death'.

10. CaseStatusMaster (CaseStatusID INT PK, CaseStatusName VARCHAR)
    - Statuses: 'Under Investigation', 'Charge Sheeted', 'Closed - False Case', 'Closed - Undetected', 'Closed - Action Abated'.

11. District (DistrictID INT PK, DistrictName VARCHAR)
    - Districts: 'Bengaluru City', 'Mysuru', 'Belagavi', 'Kalaburagi', 'Hubballi-Dharwad City', 'Mangaluru City', 'Davanagere', 'Shivamogga', 'Tumakuru', 'Vijayapura', 'Udupi', 'Dakshina Kannada', 'Uttara Kannada', 'Kodagu', 'Hassan'.

12. Unit (UnitID INT PK, UnitName VARCHAR, TypeID INT, DistrictID INT FK)
    - Police stations: e.g. "Bengaluru City Town PS", "Mysuru Traffic PS".

13. CasteMaster (caste_master_id INT PK, caste_master_name VARCHAR)
14. ReligionMaster (ReligionID INT PK, ReligionName VARCHAR)
15. OccupationMaster (OccupationID INT PK, OccupationName VARCHAR)

---
RULES FOR SQL GENERATION:
1. ONLY return the SQL statement. No markdown blocks, no code fences, no explanations.
2. The query MUST be compatible with standard SQL (and ZCQL).
3. Do not use complex MySQL or PostgreSQL specific functions. Use standard functions like COUNT, SUM, AVG, datetime functions.
4. When filtering by District name, JOIN CaseMaster with Unit and District. Example: `WHERE District.DistrictName = 'Bengaluru City'`.
5. When filtering by Crime category, JOIN CaseMaster with CrimeSubHead. Example: `WHERE CrimeSubHead.CrimeHeadName = 'Ordinary Theft'`.
6. Limit the result set to a maximum of 100 rows unless specified otherwise.
7. Use table aliases clearly.
"""

# Few-shot examples
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

# Kannada Translation System Prompt
TRANSLATE_TO_ENG_PROMPT = "You are a bilingual English-Kannada translator for a police application. Translate the following Kannada query into simple English. Output ONLY the English translation, no other text:\n"
TRANSLATE_TO_KAN_PROMPT = "You are a bilingual English-Kannada translator for a police application. Translate the following English response into Kannada. Output ONLY the Kannada translation. Do not translate code, SQL, or numbers. Clearly state the response is translation-assisted at the end:\n"

class NL2SQLEngine:
    def __init__(self):
        # Configure Gemini API
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            self.has_llm = True
        else:
            self.has_llm = False
            logger.warning("GEMINI_API_KEY environment variable not set. Running in rule-based fallback mode.")

    def is_kannada(self, text):
        # Basic Kannada unicode range check (U+0C80 to U+0CFF)
        kannada_pattern = re.compile(r'[\u0C80-\u0CFF]+')
        return bool(kannada_pattern.search(text))

    def translate_kannada_to_english(self, kannada_query):
        if not self.has_llm:
            # Simple rule-based translation fallback
            lowered = kannada_query.lower()
            if "ಕೊಲೆ" in lowered or "ಕಾಲೇ" in lowered: return "murder"
            if "ಕಳ್ಳತನ" in lowered: return "theft"
            if "ಬೆಂಗಳೂರು" in lowered: return "Bengaluru City"
            return kannada_query  # return as-is
        
        try:
            response = self.model.generate_content(TRANSLATE_TO_ENG_PROMPT + kannada_query)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Kannada to English translation error: {str(e)}")
            return kannada_query

    def translate_english_to_kannada(self, english_text):
        if not self.has_llm:
            return english_text + "\n\n(ಕನ್ನಡ ಭಾಷಾಂತರ ಲಭ್ಯವಿಲ್ಲ - GEMINI_API_KEY ಸಂರಚಿಸಿಲ್ಲ)"
            
        try:
            response = self.model.generate_content(TRANSLATE_TO_KAN_PROMPT + english_text)
            return response.text.strip() + "\n\n*(ಕನ್ನಡ ಅನುವಾದ ನೆರವು ಲಭ್ಯವಿದೆ - Translation Assisted)*"
        except Exception as e:
            logger.error(f"English to Kannada translation error: {str(e)}")
            return english_text + "\n\n*(ಅನುವಾದ ದೋಷ - Translation Error)*"

    def generate_sql(self, natural_query, history=None):
        """
        Translates a natural language query into SQL using Gemini API.
        If no API key is set, falls back to a rule-based template parser.
        """
        # 1. Check if the input is Kannada, and translate to English
        is_kan = self.is_kannada(natural_query)
        english_query = natural_query
        if is_kan:
            english_query = self.translate_kannada_to_english(natural_query)
            logger.info(f"Translated Kannada query: '{natural_query}' -> '{english_query}'")

        # 2. Generate SQL
        sql = None
        if self.has_llm:
            sql = self._generate_sql_llm(english_query, history)
        else:
            sql = self._generate_sql_fallback(english_query)

        # 3. Ensure safety/casing and clean SQL markers
        sql = self.clean_sql_query(sql)
        return sql, is_kan

    def _generate_sql_llm(self, query, history):
        history_context = ""
        if history:
            history_context = "\nConversation context:\n"
            for turn in history[-4:]:  # last 2 turns (4 entries)
                role = "User" if turn["role"] == "user" else "Assistant"
                history_context += f"{role}: {turn['text']}\n"

        prompt = f"{SCHEMA_CONTEXT}\n{FEW_SHOT_EXAMPLES}\n{history_context}\nTranslate this natural query into SQL: {query}\nSQL:"
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini SQL generation failed: {str(e)}")
            return self._generate_sql_fallback(query)

    def _generate_sql_fallback(self, query):
        """
        Rule-based parser fallback for common queries when API key is missing.
        """
        query_lower = query.lower()
        
        # 1. Accused history lookup
        match_accused = re.search(r"(?:accused|history of|offender|criminal)\s+([\w\s]+)", query_lower)
        if match_accused or "accused" in query_lower:
            name = match_accused.group(1).strip() if match_accused else "ramesh"
            # Clean up words like "named" or "called"
            name = re.sub(r'^(?:named|called|is|for)\s+', '', name)
            return f"SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, A.AccusedName, A.PhoneNo, CM.BriefFacts FROM CaseMaster CM JOIN Accused A ON CM.CaseMasterID = A.CaseMasterID WHERE A.AccusedName LIKE '%{name}%' LIMIT 10;"

        # 2. Hotspots / Location lookup
        if "hotspot" in query_lower or "thefts in" in query_lower or "theft in" in query_lower:
            # Check for city
            district = "Bengaluru City"
            if "mysuru" in query_lower: district = "Mysuru"
            elif "belagavi" in query_lower: district = "Belagavi"
            elif "kalaburagi" in query_lower: district = "Kalaburagi"
            
            return f"SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, CM.latitude, CM.longitude, CM.BriefFacts FROM CaseMaster CM JOIN Unit U ON CM.PoliceStationID = U.UnitID JOIN District D ON U.DistrictID = D.DistrictID JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CSH.CrimeHeadName = 'Ordinary Theft' AND D.DistrictName = '{district}' LIMIT 50;"

        # 3. UDR cases
        if "udr" in query_lower or "suspicious death" in query_lower or "unnatural" in query_lower:
            return "SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, CM.BriefFacts FROM CaseMaster CM JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CSH.CrimeHeadName = 'Suspicious / Unnatural Death' LIMIT 10;"

        # 4. Heinous crimes
        if "heinous" in query_lower or "serious" in query_lower:
            return "SELECT CM.CaseMasterID, CM.CrimeNo, CM.CrimeRegisteredDate, CSH.CrimeHeadName, CM.BriefFacts FROM CaseMaster CM JOIN CrimeSubHead CSH ON CM.CrimeMinorHeadID = CSH.CrimeSubHeadID WHERE CM.GravityOffenceID = 1 LIMIT 10;"

        # 5. Default: Get cases
        return "SELECT CM.CaseMasterID, CM.CrimeNo, CM.CaseNo, CM.CrimeRegisteredDate, CM.BriefFacts FROM CaseMaster CM ORDER BY CM.CrimeRegisteredDate DESC LIMIT 10;"

    def clean_sql_query(self, query):
        """
        Removes SQL markdown wrappers and trailing semicolons.
        """
        if not query:
            return ""
        # Remove markdown fences
        query = re.sub(r'```sql', '', query, flags=re.IGNORECASE)
        query = re.sub(r'```', '', query)
        query = query.strip()
        # Remove trailing semicolons for compatibility with some wrappers
        if query.endswith(';'):
            query = query[:-1]
        return query.strip()

    def generate_explanation(self, query, results, is_kannada=False):
        """
        Asks Gemini to explain the output rows based on the user query and SQL.
        """
        if not self.has_llm:
            explanation = f"Returned {len(results)} rows using ZCQL: '{query}'."
            if is_kannada:
                return "ZCQL ಬಳಸಿಕೊಂಡು " + str(len(results)) + " ಸಾಲುಗಳನ್ನು ಮರುಪಡೆಯಲಾಗಿದೆ: '" + query + "'."
            return explanation

        try:
            prompt = f"Explain the following search results to a police officer. Natural query: '{query}'. The system executed the SQL: '{query}'. Results returned: {str(results[:3])} (total {len(results)} records). Summarize what was found in 2-3 simple sentences."
            response = self.model.generate_content(prompt)
            explanation_eng = response.text.strip()
            
            if is_kannada:
                return self.translate_english_to_kannada(explanation_eng)
            return explanation_eng
        except Exception as e:
            logger.error(f"Gemini explanation generation failed: {str(e)}")
            return f"Retrieved {len(results)} records matching your query."
