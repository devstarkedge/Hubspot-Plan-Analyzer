# HubSpot Plan & Feature Utilization Analyzer (India INR)

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Render Deploy](https://img.shields.io/badge/deploy%20to-Render-46E3B7.svg)](https://render.com)
[![Catalog](https://img.shields.io/badge/HubSpot%20Catalog-Official%20INR%2029%20Oct%202026-orange.svg)](https://www.hubspot.com/pricing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An automated intelligence platform that audits your active HubSpot portal subscriptions, inspects feature utilization and user activity via live HubSpot APIs, benchmarks against the **Official HubSpot India INR Master Catalog**, identifies **shelfware (paid but idle features)**, calculates **wasted spend in ₹ INR**, and generates a modern, interactive audit dashboard.

---

## 🚀 Key Capabilities

1. **Official India INR Master Catalog**:
   - Pre-loaded with 176+ features across **Marketing Hub, Sales Hub, Service Hub, Content Hub, Data Hub, Revenue Hub**, and Platform limits.
   - Built-in official INR rates (monthly rates, quarterly invoiced amounts, annual commitments, and seat tiers).

2. **100% Automated Seat & Quota Detection**:
   - **Sales Seats**: Auto-detected from active CRM deal owners in `/crm/v3/objects/deals`.
   - **Service Seats**: Auto-detected from live CRM service reps and ticket workflows.
   - **Core Seats**: Automatically calculated and pooled based on chosen Hub tiers (e.g., Marketing Starter $+1$ + Content Pro $+3$ $= 4$ total seats) with assigned users mapped directly.
   - **Marketing Contacts**: Queried live via `hs_marketable_status == true` ($63 / 1,000$).

3. **Telemetry & Shelfware Analysis**:
   - 🟢 **Used**: Feature is included in plan and actively producing records/activity.
   - 🔴 **Shelfware**: Feature is paid for in your tier, but idle (0 items, 0 activity).
   - 🟡 **Unverified / Manual Check**: Requires in-app UI check (no public REST API).
   - 🔒 **Locked**: Available only in higher tiers.

4. **Monetary Waste & ROI Calculation (₹ INR)**:
   - Tracks idle seat budgets, underutilized allowances, and partner negotiated discounts.
   - Generates actionable downgrade risk simulations and seat assignment recommendations.

---

## ☁️ Deploying to Render

This project is pre-configured with a Render Blueprint (`render.yaml`) and `Procfile` for 1-click continuous deployment.

### Option 1: Automatic Blueprint Deployment (Recommended)

1. Fork or push this repository to your **GitHub** account.
2. Sign in to [Render](https://dashboard.render.com/).
3. Click **New +** in the top-right corner and select **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically detect `render.yaml` and set up:
   - **Runtime**: Python 3.11.9
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python server.py`
   - **Health Check Path**: `/health`
6. Click **Apply**. Render will build and deploy your live analyzer web app with a free `onrender.com` SSL URL.

---

### Option 2: Manual Web Service on Render

If you prefer setting up manually without a blueprint:

1. In Render Dashboard, click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Configure settings:
   - **Name**: `hubspot-plan-analyzer`
   - **Environment**: `Python`
   - **Region**: Choose closest to you (e.g., Singapore, Frankfurt, Oregon)
   - **Branch**: `master` or `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python server.py`
   - **Health Check Path**: `/health`
4. Click **Create Web Service**.

> [!NOTE]
> Render sets the `PORT` environment variable dynamically (e.g., 10000). `server.py` automatically binds to `0.0.0.0` and listens to `os.environ.get("PORT")`.

---

## 💻 Local Setup & Development

### 1. Clone Repository & Install Dependencies
```bash
git clone https://github.com/<YOUR_USERNAME>/hubspot-plan-analyzer.git
cd hubspot-plan-analyzer

# Optional: Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install required dependencies (openpyxl, requests)
pip install -r requirements.txt
```

### 2. Launch Local Web Dashboard
```bash
python server.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser:
1. Paste your **HubSpot Private App Access Token**.
2. Select your purchased Hub tiers (Marketing, Sales, Service, Content).
3. Click **"Analyze Live Portal & Generate Audit Report"**.
4. The dashboard will automatically fetch your live CRM telemetry, calculate seats and contacts, and display your interactive audit report at `/report`.

---

### 3. Run via Command Line (CLI)

```bash
# Interactive Mode
python cli.py -i

# Direct CLI Execution
python cli.py --token pat-na1-xxxxxxxx-xxxx-xxxx-xxxx --mkt-plan Starter --sales-plan Professional --content-plan Professional

# Export to Markdown
python cli.py --demo high_shelfware --export-md hubspot_audit.md
```

---

## 🔑 Required HubSpot Private App Scopes

When creating a Private App in HubSpot (**Settings ⚙️ > Integrations > Private Apps**), grant the following read-only scopes:

| Scope | Category | Purpose |
| :--- | :--- | :--- |
| `crm.objects.contacts.read` | CRM | Queries total contacts and billable marketing contacts (`hs_marketable_status == true`) |
| `crm.objects.deals.read` | CRM | Audits deal pipelines, stages, and detects active sales reps |
| `settings.users.read` | Settings | Checks user accounts, super admins, and seats |
| `automation` | Automation | Inspects active vs idle workflows and sequences |
| `crm.objects.custom.read` | CRM *(Optional)* | Custom object schema detection |
| `content` | CMS *(Optional)* | Landing pages and blog post counts |
| `forms` | Marketing *(Optional)* | Lead capture form counts |

---

## ⚙️ Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `8080` | Server listening port (automatically set by Render, Heroku, etc.) |
| `HOST` | `0.0.0.0` | Network interface to bind to |
| `PYTHON_VERSION` | `3.11.9` | Runtime Python version |

---

## 📁 Repository Structure

```
hubspot-plan-analyzer/
├── .gitignore                                                    # Clean Git exclusions
├── .python-version                                              # Python version hint for Render
├── runtime.txt                                                   # Python runtime specification
├── render.yaml                                                   # Render Blueprint configuration
├── Procfile                                                      # Process file for cloud hosting
├── requirements.txt                                              # Lean Python dependencies
├── README.md                                                     # Project documentation
│
├── HubSpot_All_Hubs_INR_Master_Catalog_Verified_29Oct2026.xlsx  # Official INR Master Knowledge Base
├── server.py                                                     # Multi-threaded Web Server (Render-ready)
├── cli.py                                                        # Terminal & batch execution runner
├── hubspot_audit_report.html                                     # Generated sample interactive dashboard
│
└── src/
    ├── catalog_parser.py     # Parses Excel pricing, features, limits & downgrade rules
    ├── hubspot_collector.py  # HubSpot REST API client with live seat & quota detection
    ├── analyzer.py           # Feature adoption, INR waste calculation & downgrade simulation
    └── report_generator.py   # Modern interactive HTML dashboard with floating popovers & SVG badges
```

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
