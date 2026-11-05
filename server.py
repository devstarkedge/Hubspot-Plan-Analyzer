"""
HubSpot Plan & Feature Utilization Analyzer - Interactive Web Server
Provides a modern web dashboard on http://localhost:8080 with live token scanning and user plan selection.
"""

import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.catalog_parser import HubSpotCatalog
from src.hubspot_collector import HubSpotCollector
from src.analyzer import PlanAnalyzer
from src.report_generator import ReportGenerator

# Preload Catalog
CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HubSpot_All_Hubs_INR_Master_Catalog_Verified_29Oct2026.xlsx")
catalog = HubSpotCatalog(CATALOG_PATH)
analyzer = PlanAnalyzer(catalog)
LATEST_REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hubspot_audit_report.html")

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HubSpot Plan & Feature Utilization Analyzer</title>
    <style>
        :root {
            --primary: #ff5c35;
            --primary-dark: #e0441e;
            --dark: #0f172a;
            --card-bg: #ffffff;
            --gray-100: #f8fafc;
            --gray-200: #e2e8f0;
            --gray-600: #64748b;
            --success: #10b981;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background: #f8fafc; color: var(--dark); min-height: 100vh; padding: 40px 20px; }
        .container { max-width: 960px; margin: 0 auto; }
        .hero { text-align: center; margin-bottom: 28px; }
        .badge { display: inline-block; background: #ffedd5; color: #c2410c; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 700; margin-bottom: 12px; }
        h1 { font-size: 32px; font-weight: 800; color: var(--dark); margin-bottom: 10px; }
        p.subtitle { color: var(--gray-600); font-size: 16px; }

        .card { background: var(--card-bg); border-radius: 16px; padding: 32px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01); border: 1px solid var(--gray-200); margin-bottom: 24px; }
        .form-group { margin-bottom: 22px; }
        label { display: block; font-weight: 600; font-size: 14px; margin-bottom: 8px; color: #1e293b; }
        .input-text { width: 100%; padding: 12px 16px; border: 1.5px solid var(--gray-200); border-radius: 10px; font-size: 15px; outline: none; transition: border-color 0.2s, box-shadow 0.2s; background: white; }
        .input-text:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(255, 92, 53, 0.12); }
        .select-box { 
            appearance: none;
            -webkit-appearance: none;
            -moz-appearance: none;
            width: 100%; 
            padding: 10px 36px 10px 14px; 
            border: 1.5px solid #cbd5e1; 
            border-radius: 8px; 
            font-size: 14px; 
            font-weight: 600;
            color: #0f172a;
            outline: none; 
            background-color: white; 
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            background-size: 14px;
            cursor: pointer;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
            transition: all 0.15s ease-in-out;
        }
        .select-box:hover { border-color: #94a3b8; background-color: #f8fafc; }
        .select-box:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(255, 92, 53, 0.15); background-color: white; }
        .helper { font-size: 13px; color: var(--gray-600); margin-top: 6px; }

        .plans-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-top: 10px; }
        .plan-item { background: #f8fafc; border: 1px solid var(--gray-200); border-radius: 10px; padding: 14px; }
        .plan-item label { font-size: 13px; margin-bottom: 6px; }

        .btn-submit { width: 100%; background: var(--primary); color: white; padding: 16px; border: none; border-radius: 10px; font-size: 16px; font-weight: 700; cursor: pointer; transition: background 0.2s; display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 24px; }
        .btn-submit:hover { background: var(--primary-dark); }
        .btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }

        #loading { display: none; text-align: center; padding: 24px; }
        .spinner { width: 36px; height: 36px; border: 4px solid #fed7aa; border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 12px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .catalog-banner { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 14px 18px; font-size: 13px; color: #1e40af; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; }
        
        .discount-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 14px 18px; margin-top: 14px; font-size: 13px; color: #166534; display: flex; align-items: center; gap: 10px; }
        .discount-box input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <span class="badge">INR MASTER CATALOG VERIFIED</span>
            <h1>HubSpot Plan & Feature Utilization Analyzer</h1>
            <p class="subtitle">Connect your portal to uncover shelfware, unassigned seats, and wasted spend in ₹ INR.</p>
        </div>

        <div class="catalog-banner">
            <div>
                <strong>Active Master Catalog:</strong> 176 Features &bull; Official India INR Rates &bull; Updated 29 Oct 2026
            </div>
            <span style="font-weight: 600; font-size: 12px; background: white; padding: 4px 10px; border-radius: 6px;">7 Hubs Covered</span>
        </div>

        <div class="card">
            <form id="auditForm" onsubmit="runAudit(event)">
                <!-- Live Token Section -->
                <div class="form-group">
                    <label for="token">HubSpot Private App Access Token <span style="color: #ef4444;">*</span></label>
                    <input type="password" id="token" class="input-text" placeholder="pat-na1-xxxx-xxxx-xxxx" required />
                    <div class="helper">
                        Generate in HubSpot (<strong>Settings ⚙️ &gt; Integrations &gt; Private Apps</strong>) with 4 read scopes:
                        <code>crm.objects.contacts.read</code>, <code>crm.objects.deals.read</code>, <code>settings.users.read</code>, <code>automation</code>.
                    </div>
                </div>

                <!-- Plan Customization Accordion -->
                <div class="form-group" style="margin-top: 24px;">
                    <label style="margin-bottom: 2px;">Select Your Purchased Hub Plans:</label>
                    <div style="font-size: 13px; color: #64748b; margin-bottom: 12px;">
                        Seats and contacts are automatically detected and fetched by the API from your live CRM users &amp; selected tier allowances.
                    </div>

                    <div class="plans-grid">
                        <!-- Marketing Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Marketing Hub</strong></label>
                                <span id="mkt_badge" style="background: #dbeafe; color: #1e40af; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">+1 Core Seat</span>
                            </div>
                            <select id="plan_mkt" class="select-box" onchange="updateAllPlansAndSeats()">
                                <option value="Starter" selected>Starter</option>
                                <option value="Professional">Professional</option>
                                <option value="Enterprise">Enterprise</option>
                                <option value="Free">Free</option>
                            </select>
                        </div>

                        <!-- Sales Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Sales Hub</strong></label>
                                <span id="sales_badge" style="background: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Pro CRM</span>
                            </div>
                            <select id="plan_sales" class="select-box" onchange="updateAllPlansAndSeats()">
                                <option value="Professional" selected>Professional</option>
                                <option value="Starter">Starter</option>
                                <option value="Enterprise">Enterprise</option>
                                <option value="Free">Free</option>
                            </select>
                        </div>

                        <!-- Service Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Service Hub</strong></label>
                                <span id="service_badge" style="background: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Pro Service</span>
                            </div>
                            <select id="plan_service" class="select-box" onchange="updateAllPlansAndSeats()">
                                <option value="Professional" selected>Professional</option>
                                <option value="Starter">Starter</option>
                                <option value="Enterprise">Enterprise</option>
                                <option value="Free">Free</option>
                            </select>
                        </div>

                        <!-- Content Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Content Hub</strong></label>
                                <span id="content_badge" style="background: #dbeafe; color: #1e40af; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">+3 Core Seats</span>
                            </div>
                            <select id="plan_content" class="select-box" onchange="updateAllPlansAndSeats()">
                                <option value="Professional" selected>Professional</option>
                                <option value="Starter">Starter</option>
                                <option value="Enterprise">Enterprise</option>
                                <option value="Free">Free</option>
                            </select>
                        </div>
                    </div>

                    <!-- Discount Checkbox -->
                    <div class="discount-box">
                        <input type="checkbox" id="applyDiscounts" checked />
                        <div>
                            <strong>Apply Custom Partner Discounts from Invoice:</strong>
                            <div style="font-size: 12px; margin-top: 2px;">
                                Applies negotiated partner contract discounts (e.g. Stark Edge: Sales Pro 40% off, Service Pro 39.93% off, Content Pro 50% off, Marketing Starter ₹5,010/3mo). <strong>Uncheck to evaluate standard HubSpot India INR catalog list prices for any portal.</strong>
                            </div>
                        </div>
                    </div>
                </div>

                <button type="submit" id="submitBtn" class="btn-submit">
                    <span>Analyze Live Portal &amp; Generate Audit Report</span>
                </button>
            </form>

            <div id="loading">
                <div class="spinner"></div>
                <p>Connecting to HubSpot API &amp; auditing assets against INR Master Catalog...</p>
            </div>
        </div>
    </div>

    <script>
        function getPlanCoreSeats(hub, tier) {
            if (tier === 'Free') return 0;
            if (tier === 'Starter') return 1;
            if (tier === 'Professional') return 3;
            if (tier === 'Enterprise') return 5;
            return 0;
        }

        function updateAllPlansAndSeats() {
            const mktTier = document.getElementById('plan_mkt').value;
            const salesTier = document.getElementById('plan_sales').value;
            const serviceTier = document.getElementById('plan_service').value;
            const contentTier = document.getElementById('plan_content').value;

            document.getElementById('mkt_badge').textContent = mktTier === 'Free' ? 'Free Tools' : (mktTier === 'Starter' ? '+1 Core Seat' : (mktTier === 'Professional' ? '+3 Core Seats' : '+5 Core Seats'));
            document.getElementById('sales_badge').textContent = salesTier === 'Free' ? 'Free CRM' : (salesTier === 'Starter' ? 'Starter CRM' : (salesTier === 'Professional' ? 'Pro CRM' : 'Enterprise CRM'));
            document.getElementById('service_badge').textContent = serviceTier === 'Free' ? 'Free Service' : (serviceTier === 'Starter' ? 'Starter Service' : (serviceTier === 'Professional' ? 'Pro Service' : 'Enterprise Service'));
            document.getElementById('content_badge').textContent = contentTier === 'Free' ? 'Free CMS' : (contentTier === 'Starter' ? '+1 Core Seat' : (contentTier === 'Professional' ? '+3 Core Seats' : '+5 Core Seats'));
        }

        async function runAudit(e) {
            e.preventDefault();
            const tokenVal = document.getElementById('token').value.trim();
            if (!tokenVal) {
                alert('Please enter your HubSpot Private App Access Token to audit your portal.');
                return;
            }

            const submitBtn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            
            submitBtn.style.display = 'none';
            loading.style.display = 'block';

            const mktTier = document.getElementById('plan_mkt').value;
            const contentTier = document.getElementById('plan_content').value;
            const salesTier = document.getElementById('plan_sales').value;
            const serviceTier = document.getElementById('plan_service').value;

            const hasDiscounts = document.getElementById('applyDiscounts').checked;

            const contractInfo = {
                credits: {
                    total_credits: 3000,
                    used_credits: 230,
                    wasted_credits: 2770,
                    utilization_pct: 7.7,
                    resets_date: 'Nov 25, 2026'
                },
                contacts_quota: {
                    tier: mktTier === 'Enterprise' ? 10000 : (mktTier === 'Professional' ? 2000 : (mktTier === 'Starter' ? 1000 : 0))
                },
                quarterly_billed: hasDiscounts ? {
                    'Marketing Hub': 5010.0,
                    'Sales Hub': 29988.0,
                    'Service Hub': 15011.99,
                    'Content Hub': 62550.0
                } : {},
                discounts: hasDiscounts ? {
                    'Sales Hub': 40.0,
                    'Service Hub': 39.93,
                    'Content Hub': 50.0
                } : {}
            };

            const payload = {
                token: tokenVal,
                plans: {
                    'Marketing Hub': mktTier,
                    'Sales Hub': salesTier,
                    'Service Hub': serviceTier,
                    'Content Hub': contentTier,
                    'Data Hub': 'Free'
                },
                contract_info: contractInfo
            };

            try {
                const resp = await fetch('/api/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const res = await resp.json();
                if (res.success) {
                    window.location.href = '/report';
                } else {
                    alert('Audit Error: ' + (res.error || 'Failed to analyze portal'));
                    submitBtn.style.display = 'flex';
                    loading.style.display = 'none';
                }
            } catch (err) {
                alert('Connection error: ' + err.message);
                submitBtn.style.display = 'flex';
                loading.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

class AuditServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(INDEX_HTML.encode("utf-8"))

        elif parsed.path == "/report":
            if os.path.exists(LATEST_REPORT_PATH):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(LATEST_REPORT_PATH, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"No report generated yet. Run an audit first!")

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/audit":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)
            try:
                req_data = json.loads(post_body.decode("utf-8"))
                token = req_data.get("token")
                if not token:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "error": "HubSpot Private App Access Token is required."}).encode("utf-8"))
                    return

                plans = req_data.get("plans")
                seats = req_data.get("seats")
                contract_info = req_data.get("contract_info")

                collector = HubSpotCollector(token)
                portal_data = collector.collect_all(
                    declared_plans=plans,
                    contracted_seats=seats,
                    contract_info=contract_info
                )

                audit_result = analyzer.analyze(portal_data)
                rg = ReportGenerator(audit_result)
                rg.generate_html(LATEST_REPORT_PATH)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port: int = 8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, AuditServerHandler)
    print(f"==================================================================")
    print(f" HubSpot Plan Analyzer Web Server Running on: http://localhost:{port}")
    print(f" Open http://localhost:{port} in your browser to run portal scans!")
    print(f" Press Ctrl+C to stop.")
    print(f"==================================================================")
    httpd.serve_forever()

if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
