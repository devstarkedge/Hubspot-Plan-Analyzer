# HubSpot Plan & Feature Utilization Analyzer (India INR)

An automated intelligence tool that audits a HubSpot portal's active subscription plans, inspects asset utilization, benchmarks against the **Official HubSpot India INR Master Catalog**, identifies **shelfware (paid but unused features)**, calculates **wasted spend in ₹ INR**, and simulates **downgrade risks**.

---

## 🚀 Key Capabilities

1. **Master Catalog Integration**:
   - Pre-loaded with 176+ features across **Marketing Hub, Sales Hub, Service Hub, Content Hub, Data Hub, Revenue Hub**, and Platform limits from `HubSpot_All_Hubs_INR_Master_Catalog_Verified_29Oct2026.xlsx`.
   - Built-in official INR rates (monthly, annual commitment, per-seat tiers, and contact limits).

2. **Automated Portal Telemetry Inspection**:
   - Queries HubSpot APIs using a Private App Access Token.
   - Audits:
     - **Paid Seats**: Total users, Sales/Service Pro seats, active vs inactive users (last 30-day login).
     - **Automation**: Active workflows, draft workflows, sales sequences, enrollments.
     - **CRM Assets**: Deal & Ticket pipelines, custom stages, custom object schemas.
     - **Marketing & CMS**: Forms, landing pages, blog posts, marketing contacts vs total contacts.
     - **Sales CPQ**: Quotes generated, product catalog items, call minutes.

3. **Adoption & Shelfware Classification**:
   - 🟢 **Used**: Feature is included in plan and actively producing records/activity.
   - 🔴 **Shelfware**: Feature is paid for in your tier, but idle (0 items, 0 activity).
   - 🔒 **Locked**: Available in higher tiers.

4. **Monetary Waste & ROI Calculation (₹ INR)**:
   - Calculates **Idle Seat Waste**: e.g. paying ₹7,497/seat/mo for reps who haven't logged in for 30+ days.
   - Calculates **Tier Overpayment**: e.g. paying ₹74,200/mo for Marketing Pro with 0 workflows running when Marketing Starter (₹1,670/mo) suffices.
   - Tracks **Unengaged & Hard-Bounced Contacts** inflating billable contact tiers.

5. **Downgrade Impact Simulator**:
   - Automatically cross-checks existing portal assets against HubSpot's downgrade rules.
   - Flags breaking changes (e.g., active workflows being locked, pipelines exceeding Starter limits of 2).

---

## 🛠️ Quick Start

### Option A: Launch Interactive Web Dashboard

Start the local web server:
```bash
python server.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser:
* Paste your **HubSpot Private App Token**.
* Select your purchased Hub tiers and seat counts (or click **"⚡ Auto-Fill Stark Edge Subscription"**).
* Click **"Analyze Live Portal & Generate Audit Report"**.
* View the interactive report with charts, filters, and actionable recommendations.

---

### Option B: Run via Command Line (CLI)

#### 1. Interactive Q&A Mode
```bash
python cli.py -i
```
Prompts you to enter your token and choose your plans step-by-step.

#### 2. Run Directly with Token and Plan Flags
```bash
python cli.py --token pat-na1-xxxxxxxx-xxxx-xxxx-xxxx --mkt-plan Starter --sales-plan Professional --sales-seats 2 --content-plan Professional
```

#### 3. Export to Markdown
```bash
python cli.py --demo high_shelfware --export-md hubspot_audit.md
```

---

## 🔑 Required HubSpot Private App Scopes

When creating a Private App in HubSpot (**Settings > Integrations > Private Apps**), grant these read-only scopes:

| Scope | Purpose |
| :--- | :--- |
| `crm.objects.contacts.read` | Marketing contacts count & bounce detection |
| `crm.objects.deals.read` | Pipeline & deal stage audit |
| `crm.objects.custom.read` | Custom object schemas detection |
| `crm.schemas.custom.read` | Enterprise custom object verification |
| `automation` | Workflow and sequence audit |
| `settings.users.read` | User seat allocations & last login activity |
| `content` | Landing pages & blog posts count |
| `forms` | Active forms & popup forms |

---

## 📁 Repository Structure

```
hubspot plan analyzer/
│
├── HubSpot_All_Hubs_INR_Master_Catalog_Verified_29Oct2026.xlsx  # Master Knowledge Base
├── hubspot_audit_report.html                                   # Generated Interactive Dashboard
│
├── server.py                                                   # Web Dashboard Server (Port 8080)
├── cli.py                                                      # CLI Runner
│
└── src/
    ├── catalog_parser.py     # Parses Excel pricing, features, limits & downgrade rules
    ├── hubspot_collector.py  # HubSpot REST API client + realistic mock datasets
    ├── analyzer.py           # Feature adoption, INR waste calculation & downgrade simulation
    └── report_generator.py   # Generates standalone HTML dashboards and Markdown reports
```

