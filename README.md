# Karnataka State Police (KSP) Crime Platform — Datathon 2026

A unified, serverless intelligence platform deployed on **Zoho Catalyst** that addresses **Challenge 01** (Intelligent Conversational AI) and **Challenge 02** (AI-Driven Crime Analytics & Link-Analysis). 

By utilizing a shared Python Advanced I/O backend and a dual-mode database adapter (SQLite for local zero-friction execution + Catalyst Data Store ZCQL for cloud production), the platform minimizes code duplication and ensures absolute reliability.

---

## 🚀 Key Features

### 💬 Challenge 01: Intelligent Conversational AI
- **Schema-Grounded NL2SQL Engine:** Translates natural language queries (English & Kannada) into precise SQL queries executed directly against the database.
- **Explainability Layer:** Transparently displays the executed SQL statement and the exact table rows returned by the query in a slide-out query drawer.
- **Bilingual Translation Pass:** Native Kannada script queries are translated to English before querying the database, and the results/explanations are translated back to Kannada.
- **Voice Commands:** Uses the HTML5 Web Speech API for voice-to-text input and voice synthesis output.
- **Investigation PDF Export:** Allows investigators to download their multi-turn conversation logs as a structured PDF report.

### 📊 Challenge 02: AI-Driven Crime Analytics & Link-Analysis
- **Geospatial Hotspots (DBSCAN):** Filters coordinates and clusters vehicle theft and burglary incidents into hotspots, rendering radius density rings via Leaflet.
- **Spike Alert Indicator:** Triggers warning/critical alerts if a district's monthly crime count deviates by >1.8 standard deviations from its historical 12-month average.
- **Criminal Link Networks (NetworkX & Vis.js):** Builds an interactive graph of accused, cases, phone numbers, addresses, and bank accounts. Features repeat-offender tracking and connected components (gang detection).
- **Predictive Risk & Anomaly Forest:** Trains a RandomForest model to rate district risk levels. Local feature-level contributions are mapped and rendered as simulated **SHAP explanations**. Uses an **IsolationForest** model to flag anomalous cases (e.g. demographic or MO outliers).
- **Sociological Insights:** Cross-tabulates correlations between complainant demographics, age brackets, and crime sub-heads.
- **Access Compliance Audit Logs:** Supervisor-restricted view tracking user queries, roles, and timestamps (RBAC).

---

## 🛠️ Technology Stack
- **Backend:** Zoho Catalyst Serverless (Advanced I/O Python 3.12 Function, Flask, NetworkX, Scikit-Learn, FPDF2)
- **Frontend:** Zoho Catalyst Web Client Hosting (Vanilla HTML5, CSS3 Glassmorphism, Vanilla JS, Leaflet maps, Vis.js graphs)
- **Database:** Zoho Catalyst Data Store (ZCQL) / Local SQLite (`ksp_crime.db`)
- **LLM Engine:** Google Gemini API (Free Tier) with a local rule-based mock parser fallback.

---

## 📂 Project Structure
```
├── client/                     # Hosted frontend web client assets
│   ├── css/style.css           # Glassmorphic, dark theme UI styles
│   ├── challenge01/index.html  # Chatbot interface and explainability drawer
│   ├── challenge02/index.html  # Analytical Map, Network Graph, and ML Dashboards
│   ├── js/app.js               # Client API router, maps, and network controls
│   └── index.html              # Main portal landing page and RBAC selector
├── functions/
│   └── ksp_backend/            # Shared Catalyst Advanced I/O Python Function
│       ├── main.py             # HTTP routing controller and CORS middleware
│       ├── database.py         # DB manager (SQLite & ZCQL flattening logic)
│       ├── nl2sql.py           # Gemini prompting and translation pipelines
│       ├── analytics.py        # NetworkX, DBSCAN, RandomForest/SHAP, IsolationForest
│       ├── requirements.txt    # Python dependencies
│       └── catalyst-config.json# Catalyst function configuration
├── scripts/
│   ├── db_schema.sql           # Database DDL schema (25 KSP tables + AuditLog)
│   ├── generate_data.py        # Calibrated synthetic data generator
│   └── test_backend.py         # Automated Flask integration test suite
├── catalyst.json               # Catalyst project configuration
└── README.md                   # Setup and system documentation
```

---

## ⚙️ Setup & Local Execution

### 1. Pre-requisites
Ensure you have Node.js v14+, Python 3.10+, and Zoho Catalyst CLI installed:
```bash
npm install -g zcatalyst-cli
```

### 2. Install Python Dependencies
```bash
pip install -r functions/ksp_backend/requirements.txt
```

### 3. Generate SQLite Local Database
Run the synthetic generator to generate `ksp_crime.db` with calibrated Karnataka crime ratios and injected criminal networks/anomalies:
```bash
python scripts/generate_data.py
```

### 4. Configuration (Environment Variables)
Configure the following in your environment:
```env
DB_TYPE=sqlite                # 'sqlite' for zero-setup local dev; 'catalyst' for production
GEMINI_API_KEY=your-api-key    # Gemini key for NL2SQL and translations
```
*(If no `GEMINI_API_KEY` is provided, the chatbot automatically falls back to a regex-based query parser so the application is still fully testable).*

### 5. Serve locally
Start the Catalyst emulator to host the client portal and the backend API:
```bash
catalyst serve
```
Open `http://localhost:3000` in your web browser.

---

## ☁️ Zoho Catalyst Deployment

### 1. Database Schema Initialization
Because Zoho Catalyst does not support programmatic schema creations (DDL) via CLI/API:
1. Log into your **Zoho Catalyst Console**.
2. Navigate to **Cloud Scale > Data Store**.
3. Create the tables and define columns manually as documented in `scripts/db_schema.sql`.
4. Ensure you create the `AuditLog` table with columns: `UserEmail` (Text), `UserRole` (Text), `Action` (Text), `QueryExecuted` (Text).

### 2. Deploy to Production
Log in to your Catalyst account and deploy the project:
```bash
catalyst login
catalyst deploy
```
Catalyst will deploy your client files to **Web Client Hosting** and your server files to **Serverless Functions**, returning your live production URLs.
