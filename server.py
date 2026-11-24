"""
HubSpot Plan & Feature Utilization Analyzer - Interactive Web Server
Provides a modern web dashboard on http://localhost:8080 with live token scanning and user plan selection.
"""

import sys
import os
import json
import re
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
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
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

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
        .select-box:disabled {
            background-color: #f1f5f9;
            color: #94a3b8;
            border-color: #e2e8f0;
            cursor: not-allowed;
            opacity: 0.7;
        }

        .plan-section-locked {
            opacity: 0.5;
            pointer-events: none;
            user-select: none;
            filter: grayscale(15%);
            transition: all 0.3s ease;
        }

        .plan-section-unlocked {
            opacity: 1;
            pointer-events: auto;
            user-select: auto;
            filter: none;
            transition: all 0.3s ease;
        }

        .helper { font-size: 13px; color: var(--gray-600); margin-top: 6px; }

        .plans-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-top: 10px; }
        .plan-item { background: #f8fafc; border: 1px solid var(--gray-200); border-radius: 10px; padding: 14px; }
        .plan-item label { font-size: 13px; margin-bottom: 6px; }

        .btn-submit { width: 100%; background: var(--primary); color: white; padding: 16px; border: none; border-radius: 10px; font-size: 16px; font-weight: 700; cursor: pointer; transition: background 0.2s; display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 24px; }
        .btn-submit:hover { background: var(--primary-dark); }
        .btn-submit:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background: #94a3b8 !important;
            box-shadow: none;
        }

        .spinner-mini {
            width: 14px;
            height: 14px;
            border: 2px solid #bfdbfe;
            border-top-color: #2563eb;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            display: inline-block;
            vertical-align: middle;
            margin-right: 6px;
        }

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

        <!-- Saved Reports Quick Access -->
        <div id="recentReportsContainer" style="display: none; margin-bottom: 24px; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 16px;">📁</span>
                    <strong style="font-size: 14px; color: #1e293b;">Previously Audited Portals &amp; Unique Reports</strong>
                </div>
                <span id="reportCountBadge" style="font-size: 11px; background: #f1f5f9; color: #475569; padding: 2px 8px; border-radius: 10px; font-weight: 700;"></span>
            </div>
            <div id="recentReportsList" style="display: flex; flex-direction: column; gap: 8px;"></div>
        </div>

        <div class="card">
            <form id="auditForm" onsubmit="runAudit(event)">
                <!-- Live Token Section -->
                <div class="form-group">
                    <label for="token">HubSpot Private App Access Token <span style="color: #ef4444;">*</span></label>
                    <input type="password" id="token" class="input-text" placeholder="pat-na1-xxxx-xxxx-xxxx" required oninput="debounceDetect()" />
                    <div class="helper">
                        Generate in HubSpot (<strong>Settings ⚙️ &gt; Integrations &gt; Private Apps</strong>) with read scopes:
                        <code>crm.objects.contacts.read</code>, <code>crm.objects.deals.read</code>, <code>settings.users.read</code>, <code>automation</code>.
                    </div>
                </div>

                <!-- Live Auto-Detection Banner -->
                <div id="detectionBanner" style="display: none; background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #166534; margin-top: 14px; align-items: center; justify-content: space-between;">
                    <div id="detectionText"></div>
                    <span id="detectionBadge" style="font-size: 11px; font-weight: 700; background: #dcfce7; padding: 3px 8px; border-radius: 5px; color: #15803d; white-space: nowrap; margin-left: 10px;">LIVE API VERIFIED</span>
                </div>

                <!-- Plan Customization Accordion (Disabled until token entered & fetched) -->
                <div id="planSection" class="form-group plan-section-locked" style="margin-top: 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <label style="margin-bottom: 0;"><strong>Purchased Hub Plans &amp; Tiers:</strong></label>
                        <span id="planLockBadge" style="font-size: 11px; font-weight: 700; background: #fef3c7; color: #b45309; padding: 2px 8px; border-radius: 6px;">
                            🔒 Locked &bull; Add Token Above
                        </span>
                    </div>
                    <div id="planHelpText" style="font-size: 13px; color: #64748b; margin-bottom: 12px;">
                        Enter your HubSpot Private App Token above. The API will auto-detect your active seats and unlock plan configuration.
                    </div>

                    <div class="plans-grid">
                        <!-- Marketing Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Marketing Hub</strong></label>
                                <span id="mkt_badge" style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Free Tools</span>
                            </div>
                            <select id="plan_mkt" class="select-box" onchange="updateAllPlansAndSeats()" disabled>
                                <option value="Free" selected>Free</option>
                                <option value="Starter">Starter</option>
                                <option value="Professional">Professional</option>
                                <option value="Enterprise">Enterprise</option>
                            </select>
                        </div>

                        <!-- Sales Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Sales Hub</strong></label>
                                <span id="sales_badge" style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Free CRM</span>
                            </div>
                            <select id="plan_sales" class="select-box" onchange="updateAllPlansAndSeats()" disabled>
                                <option value="Free" selected>Free</option>
                                <option value="Starter">Starter</option>
                                <option value="Professional">Professional</option>
                                <option value="Enterprise">Enterprise</option>
                            </select>
                        </div>

                        <!-- Service Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Service Hub</strong></label>
                                <span id="service_badge" style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Free Service</span>
                            </div>
                            <select id="plan_service" class="select-box" onchange="updateAllPlansAndSeats()" disabled>
                                <option value="Free" selected>Free</option>
                                <option value="Starter">Starter</option>
                                <option value="Professional">Professional</option>
                                <option value="Enterprise">Enterprise</option>
                            </select>
                        </div>

                        <!-- Content Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <label style="margin-bottom: 0;"><strong>Content Hub</strong></label>
                                <span id="content_badge" style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Free CMS</span>
                            </div>
                            <select id="plan_content" class="select-box" onchange="updateAllPlansAndSeats()" disabled>
                                <option value="Free" selected>Free</option>
                                <option value="Starter">Starter</option>
                                <option value="Professional">Professional</option>
                                <option value="Enterprise">Enterprise</option>
                            </select>
                        </div>

                        <!-- Data Hub (formerly Operations Hub) -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <div>
                                    <label style="margin-bottom: 0;"><strong>Data Hub</strong></label>
                                    <div style="font-size: 10px; color: #64748b; margin-top: -2px;">(formerly Operations Hub)</div>
                                </div>
                                <span id="data_badge" style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Free Tools</span>
                            </div>
                            <select id="plan_data" class="select-box" onchange="updateAllPlansAndSeats()" disabled>
                                <option value="Free" selected>Free</option>
                                <option value="Starter">Starter</option>
                                <option value="Professional">Professional</option>
                                <option value="Enterprise">Enterprise</option>
                            </select>
                        </div>

                        <!-- Commerce Hub -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <div>
                                    <label style="margin-bottom: 0;"><strong>Commerce Hub</strong></label>
                                    <div style="font-size: 10px; color: #64748b; margin-top: -2px;">(Invoicing &amp; CPQ)</div>
                                </div>
                                <span id="revenue_badge" style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Free Tools</span>
                            </div>
                            <select id="plan_revenue" class="select-box" onchange="updateAllPlansAndSeats()" disabled>
                                <option value="Free" selected>Free</option>
                                <option value="Professional">Professional</option>
                                <option value="Enterprise">Enterprise</option>
                            </select>
                        </div>

                        <!-- Smart CRM -->
                        <div class="plan-item">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <div>
                                    <label style="margin-bottom: 0;"><strong>Smart CRM</strong></label>
                                    <div style="font-size: 10px; color: #64748b; margin-top: -2px;">(Platform Foundation)</div>
                                </div>
                                <span id="crm_badge" style="background: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">Included ₹0</span>
                            </div>
                            <select id="plan_crm" class="select-box" onchange="updateAllPlansAndSeats()" disabled>
                                <option value="Free" selected>Free Foundation (Included)</option>
                                <option value="Starter">Starter CRM Suite</option>
                                <option value="Professional">Professional CRM Suite</option>
                                <option value="Enterprise">Enterprise CRM Suite</option>
                            </select>
                        </div>
                    </div>

                    <!-- Portal Usage & Customization (100% Dynamic, Zero Hardcoding) -->
                    <div style="margin-top: 24px; padding: 18px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                            <h3 style="font-size: 14.5px; font-weight: 700; color: #0f172a;">Portal Usage &amp; Customization (Auto-Detected)</h3>
                            <span style="font-size: 11px; background: #e0f2fe; color: #0369a1; font-weight: 700; padding: 2px 8px; border-radius: 6px;">EDITABLE DEFAULTS</span>
                        </div>

                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 14px;">
                            <div>
                                <label style="font-size: 12px; font-weight: 600; color: #475569; display: block; margin-bottom: 4px;">Company / Portal Name</label>
                                <input type="text" id="portal_company_name" class="select-box" style="padding: 8px 12px; font-size: 13px;" placeholder="Auto-detected brand or name" disabled />
                            </div>
                            <div>
                                <label style="font-size: 12px; font-weight: 600; color: #475569; display: block; margin-bottom: 4px;">Marketing Contacts Tier</label>
                                <input type="number" id="contacts_tier_input" class="select-box" style="padding: 8px 12px; font-size: 13px;" placeholder="e.g. 7000 or 12000" disabled />
                            </div>
                            <div>
                                <label style="font-size: 12px; font-weight: 600; color: #475569; display: block; margin-bottom: 4px;">HubSpot Monthly AI Credits</label>
                                <input type="number" id="credits_total_input" class="select-box" style="padding: 8px 12px; font-size: 13px;" value="0" placeholder="3000 for Pro/Ent" disabled />
                            </div>
                            <div>
                                <label style="font-size: 12px; font-weight: 600; color: #475569; display: block; margin-bottom: 4px;">AI Credits Used</label>
                                <input type="number" id="credits_used_input" class="select-box" style="padding: 8px 12px; font-size: 13px;" value="0" placeholder="e.g. 460" disabled />
                            </div>
                        </div>

                        <!-- Optional Invoiced Spend or Discount -->
                        <div class="discount-box" style="margin-top: 10px; background: white; padding: 12px; border: 1px solid #cbd5e1; border-radius: 8px;">
                            <input type="checkbox" id="applyDiscounts" onchange="toggleDiscountFields()" disabled style="cursor: pointer;" />
                            <div style="flex: 1;">
                                <label for="applyDiscounts" style="font-size: 13px; font-weight: 700; cursor: pointer;">Apply Custom Negotiated Invoice / Discount (Optional)</label>
                                <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
                                    Enable if your contract has customized discount pricing instead of standard Master Catalog rates.
                                </div>
                                <div id="discountInputs" style="display: none; margin-top: 10px; gap: 14px; flex-wrap: wrap;">
                                    <div style="display: inline-block; margin-right: 14px;">
                                        <label style="font-size: 11.5px; font-weight: 600; color: #475569; display: block; margin-bottom: 3px;">Contract Discount %</label>
                                        <input type="number" id="custom_discount_pct" placeholder="e.g. 40" min="0" max="100" style="padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px; width: 110px; font-size: 12.5px;">
                                    </div>
                                    <div style="display: inline-block;">
                                        <label style="font-size: 11.5px; font-weight: 600; color: #475569; display: block; margin-bottom: 3px;">Total Quarterly Invoice (₹ / $)</label>
                                        <input type="number" id="custom_quarterly_invoice" placeholder="e.g. 132820" style="padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px; width: 160px; font-size: 12.5px;">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <button type="submit" id="submitBtn" class="btn-submit" disabled>
                    <span id="btnText">Enter Token to Analyze Portal</span>
                </button>
            </form>

            <div id="loading">
                <div class="spinner"></div>
                <p>Connecting to HubSpot API &amp; auditing assets against INR Master Catalog...</p>
            </div>
        </div>
    </div>

    <script>
        function setPlansLocked(locked, reasonText) {
            const section = document.getElementById('planSection');
            const badge = document.getElementById('planLockBadge');
            const help = document.getElementById('planHelpText');
            const submitBtn = document.getElementById('submitBtn');
            const btnText = document.getElementById('btnText');

            const selects = ['plan_mkt', 'plan_sales', 'plan_service', 'plan_content', 'plan_data', 'plan_revenue', 'plan_crm', 'applyDiscounts', 'portal_company_name', 'contacts_tier_input', 'credits_total_input', 'credits_used_input'];
            selects.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.disabled = locked;
            });

            if (locked) {
                if (section) {
                    section.classList.remove('plan-section-unlocked');
                    section.classList.add('plan-section-locked');
                }
                if (badge) {
                    badge.innerHTML = '🔒 Locked &bull; Add Token Above';
                    badge.style.background = '#fef3c7';
                    badge.style.color = '#b45309';
                }
                if (help) help.textContent = reasonText || 'Enter your HubSpot Private App Token above. The API will auto-detect your active seats and unlock plan configuration.';
                if (submitBtn) submitBtn.disabled = true;
                if (btnText) btnText.textContent = 'Enter Token to Analyze Portal';
            } else {
                if (section) {
                    section.classList.remove('plan-section-locked');
                    section.classList.add('plan-section-unlocked');
                }
                if (badge) {
                    badge.innerHTML = '🔓 Unlocked &bull; Live Telemetry Synced';
                    badge.style.background = '#dcfce7';
                    badge.style.color = '#15803d';
                }
                if (help) help.textContent = 'User seats & allowances auto-detected from live API. You can review or adjust plan tiers below before auditing.';
                if (submitBtn) submitBtn.disabled = false;
                if (btnText) btnText.textContent = 'Analyze Live Portal & Generate Audit Report';
            }
        }

        function resetLoadingState() {
            const submitBtn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const token = document.getElementById('token').value.trim();

            if (loading) loading.style.display = 'none';
            if (submitBtn) {
                submitBtn.style.display = 'flex';
                submitBtn.disabled = !(token && token.length >= 15);
                const btnText = document.getElementById('btnText');
                if (btnText) {
                    btnText.textContent = (token && token.length >= 15) ? 'Analyze Live Portal & Generate Audit Report' : 'Enter Token to Analyze Portal';
                }
            }
        }

        // Restore button and hide loading spinner whenever page is shown (handles browser back button & bfcache)
        window.addEventListener('pageshow', function () {
            resetLoadingState();
            const token = document.getElementById('token').value.trim();
            if (token && token.length >= 15) {
                autoDetectPortal();
            } else {
                setPlansLocked(true);
            }
        });
        window.addEventListener('load', resetLoadingState);
        document.addEventListener('DOMContentLoaded', resetLoadingState);
        window.addEventListener('popstate', resetLoadingState);

        let detectTimer = null;
        function debounceDetect() {
            clearTimeout(detectTimer);
            const token = document.getElementById('token').value.trim();
            const banner = document.getElementById('detectionBanner');
            const textEl = document.getElementById('detectionText');
            const badgeEl = document.getElementById('detectionBadge');

            if (!token || token.length < 15) {
                if (banner) banner.style.display = 'none';
                setPlansLocked(true);
                return;
            }

            // Immediately show connecting status
            if (banner && textEl && badgeEl) {
                banner.style.display = 'flex';
                banner.style.background = '#eff6ff';
                banner.style.borderColor = '#93c5fd';
                banner.style.color = '#1e40af';
                textEl.innerHTML = '<span class="spinner-mini"></span> Connecting to HubSpot API &amp; detecting user seats...';
                badgeEl.textContent = 'FETCHING SEATS...';
                badgeEl.style.background = '#dbeafe';
                badgeEl.style.color = '#1e40af';
            }
            setPlansLocked(true, 'Connecting to HubSpot to fetch user seats and permissions...');

            detectTimer = setTimeout(autoDetectPortal, 400);
        }

        async function autoDetectPortal() {
            const token = document.getElementById('token').value.trim();
            if (!token || token.length < 15) {
                setPlansLocked(true);
                return;
            }

            const banner = document.getElementById('detectionBanner');
            const textEl = document.getElementById('detectionText');
            const badgeEl = document.getElementById('detectionBadge');

            try {
                const resp = await fetch('/api/detect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token })
                });
                const res = await resp.json();
                if (res.success) {
                    window._detectedData = res;
                    let seatsSummary = [];
                    if (res.paid_sales_seats > 0) seatsSummary.push(`${res.paid_sales_seats} Sales ${res.detected_sales_tier || 'Seat'}${res.paid_sales_seats > 1 ? 's' : ''}`);
                    if (res.paid_service_seats > 0) seatsSummary.push(`${res.paid_service_seats} Service ${res.detected_service_tier || 'Seat'}${res.paid_service_seats > 1 ? 's' : ''}`);
                    if (res.paid_revenue_seats > 0) seatsSummary.push(`${res.paid_revenue_seats} Commerce ${res.detected_revenue_tier || 'Seat'}${res.paid_revenue_seats > 1 ? 's' : ''}`);
                    if (res.core_seats_used > 0) seatsSummary.push(`${res.core_seats_used} Core Seats`);

                    let details = [];
                    if (res.detected_contact_tier) details.push(`Contacts: ${res.marketing_contacts.toLocaleString()} / ${res.detected_contact_tier.toLocaleString()}`);
                    if (res.total_credits) details.push(`Credits: ${res.used_credits || 0}/${res.total_credits.toLocaleString()}`);
                    if (res.total_workflows !== undefined) details.push(`Workflows: ${res.active_workflows}/${res.total_workflows}`);

                    banner.style.display = 'flex';
                    banner.style.background = '#f0fdf4';
                    banner.style.borderColor = '#86efac';
                    banner.style.color = '#166534';
                    textEl.innerHTML = `<strong>Connected: ${res.company_name} (Portal ${res.portal_id})</strong> &bull; Currency: ${res.currency}<br><span style="font-size:12px; opacity:0.9;">${seatsSummary.join(', ') || res.total_users + ' team users'} &bull; ${details.join(' &bull; ')}</span>`;
                    badgeEl.textContent = 'LIVE API VERIFIED';
                    badgeEl.style.background = '#dcfce7';
                    badgeEl.style.color = '#15803d';

                    // Auto-select detected tiers from live API
                    document.getElementById('plan_mkt').value = res.detected_mkt_tier || 'Free';
                    document.getElementById('plan_sales').value = res.detected_sales_tier || 'Free';
                    document.getElementById('plan_service').value = res.detected_service_tier || 'Free';
                    document.getElementById('plan_content').value = res.detected_content_tier || 'Free';
                    document.getElementById('plan_revenue').value = res.detected_revenue_tier || 'Free';
                    document.getElementById('plan_data').value = res.detected_data_tier || 'Free';
                    document.getElementById('plan_crm').value = res.detected_crm_tier || 'Free';
                    updateAllPlansAndSeats();

                    // Auto-populate dynamic defaults into editable fields
                    if (res.company_name) document.getElementById('portal_company_name').value = res.company_name;
                    if (res.detected_contact_tier) document.getElementById('contacts_tier_input').value = res.detected_contact_tier;
                    if (res.total_credits !== undefined) document.getElementById('credits_total_input').value = res.total_credits;
                    if (res.used_credits !== undefined) document.getElementById('credits_used_input').value = res.used_credits;

                    // Unlock plan selection and enable Analyze button!
                    setPlansLocked(false);
                } else {
                    banner.style.display = 'flex';
                    banner.style.background = '#fef2f2';
                    banner.style.borderColor = '#fca5a5';
                    banner.style.color = '#991b1b';
                    textEl.innerHTML = `<strong>Connection Error:</strong> ${res.error || 'Invalid token or missing required permissions.'}`;
                    badgeEl.textContent = 'TOKEN ERROR';
                    badgeEl.style.background = '#fee2e2';
                    badgeEl.style.color = '#991b1b';
                    setPlansLocked(true, 'Token error: Please verify your Private App Token and permissions.');
                }
            } catch(e) {
                banner.style.display = 'flex';
                banner.style.background = '#fef2f2';
                banner.style.borderColor = '#fca5a5';
                banner.style.color = '#991b1b';
                textEl.innerHTML = `<strong>Connection Error:</strong> ${e.message}`;
                badgeEl.textContent = 'NETWORK ERROR';
                badgeEl.style.background = '#fee2e2';
                badgeEl.style.color = '#991b1b';
                setPlansLocked(true, 'Network error connecting to API.');
            }
        }

        function toggleDiscountFields() {
            const isChecked = document.getElementById('applyDiscounts').checked;
            const box = document.getElementById('discountInputs');
            if (box) box.style.display = isChecked ? 'flex' : 'none';
        }

        function updateAllPlansAndSeats() {
            const mktTier = document.getElementById('plan_mkt').value;
            const salesTier = document.getElementById('plan_sales').value;
            const serviceTier = document.getElementById('plan_service').value;
            const contentTier = document.getElementById('plan_content').value;
            const dataTier = document.getElementById('plan_data').value;
            const revTier = document.getElementById('plan_revenue').value;
            const crmTier = document.getElementById('plan_crm').value;

            document.getElementById('mkt_badge').textContent = mktTier === 'Free' ? 'Free Tools' : (mktTier === 'Starter' ? '+1 Core Seat' : (mktTier === 'Professional' ? '+3 Core Seats' : '+5 Core Seats'));
            document.getElementById('sales_badge').textContent = salesTier === 'Free' ? 'Free CRM' : (salesTier === 'Starter' ? 'Starter CRM' : (salesTier === 'Professional' ? 'Pro CRM' : 'Enterprise CRM'));
            document.getElementById('service_badge').textContent = serviceTier === 'Free' ? 'Free Service' : (serviceTier === 'Starter' ? 'Starter Service' : (serviceTier === 'Professional' ? 'Pro Service' : 'Enterprise Service'));
            document.getElementById('content_badge').textContent = contentTier === 'Free' ? 'Free CMS' : (contentTier === 'Starter' ? '+1 Core Seat' : (contentTier === 'Professional' ? '+3 Core Seats' : '+5 Core Seats'));
            document.getElementById('data_badge').textContent = dataTier === 'Free' ? 'Free Tools' : (dataTier === 'Starter' ? '+1 Core Seat' : (dataTier === 'Professional' ? 'Pro Datasets' : 'Enterprise Ops'));
            document.getElementById('revenue_badge').textContent = revTier === 'Free' ? 'Free Tools' : (revTier === 'Professional' ? 'Pro CPQ' : 'Enterprise CPQ');
            document.getElementById('crm_badge').textContent = crmTier === 'Free' ? 'Included ₹0' : `${crmTier} Suite`;
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
            const dataTier = document.getElementById('plan_data').value;
            const revTier = document.getElementById('plan_revenue').value;
            const crmTier = document.getElementById('plan_crm').value;

            const hasDiscounts = document.getElementById('applyDiscounts').checked;

            const contractInfo = {};

            // Dynamic Company Name
            const compName = document.getElementById('portal_company_name').value.trim();
            if (compName) {
                contractInfo.company_name = compName;
            }

            // Dynamic Marketing Contacts Tier
            const cTierVal = parseInt(document.getElementById('contacts_tier_input').value);
            if (!isNaN(cTierVal) && cTierVal > 0) {
                contractInfo.contacts_quota = { tier: cTierVal };
            }

            // Dynamic HubSpot AI Credits
            const credTotal = parseInt(document.getElementById('credits_total_input').value);
            const credUsed = parseInt(document.getElementById('credits_used_input').value) || 0;
            if (!isNaN(credTotal) && credTotal > 0) {
                contractInfo.credits = {
                    total_credits: credTotal,
                    used_credits: credUsed,
                    resets_date: 'Monthly Renewal'
                };
            }

            // Optional Dynamic Partner Discounts / Invoice
            if (hasDiscounts) {
                const discPctEl = document.getElementById('custom_discount_pct');
                const discPct = discPctEl ? parseFloat(discPctEl.value) : 0;
                const qInvEl = document.getElementById('custom_quarterly_invoice');
                const qInv = qInvEl ? parseFloat(qInvEl.value) : 0;

                if (!isNaN(discPct) && discPct > 0) {
                    contractInfo.discounts = {
                        'Sales Hub': discPct,
                        'Service Hub': discPct,
                        'Content Hub': discPct,
                        'Marketing Hub': discPct
                    };
                }
                if (!isNaN(qInv) && qInv > 0) {
                    contractInfo.invoice_amount = qInv;
                }
            }

            const payload = {
                token: tokenVal,
                plans: {
                    'Marketing Hub': mktTier,
                    'Sales Hub': salesTier,
                    'Service Hub': serviceTier,
                    'Content Hub': contentTier,
                    'Data Hub': dataTier,
                    'Commerce Hub': revTier,
                    'Revenue Hub': revTier,
                    'Smart CRM': crmTier,
                    'Platform-wide': crmTier
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
                    resetLoadingState();
                    window.location.href = res.report_url || '/report';
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

        async function loadRecentReports() {
            try {
                const resp = await fetch('/api/reports');
                const data = await resp.json();
                if (data.success && data.reports && data.reports.length > 0) {
                    const container = document.getElementById('recentReportsContainer');
                    const list = document.getElementById('recentReportsList');
                    const badge = document.getElementById('reportCountBadge');
                    if (container && list) {
                        container.style.display = 'block';
                        if (badge) badge.textContent = `${data.reports.length} Portals Audited`;
                        list.innerHTML = data.reports.slice(0, 5).map(r => `
                            <div style="display: flex; justify-content: space-between; align-items: center; background: #f8fafc; padding: 10px 14px; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 13px;">
                                <div>
                                    <strong style="color: #0f172a;">${r.company_name}</strong> <span style="color: #64748b;">(Portal ${r.portal_id || 'N/A'})</span>
                                    <span style="font-size: 11px; color: #94a3b8; margin-left: 8px;">${r.date_str}</span>
                                </div>
                                <div style="display: flex; gap: 8px; align-items: center;">
                                    <a href="${r.url}" target="_blank" style="background: white; border: 1px solid #cbd5e1; color: #ff5c35; font-weight: 600; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;">Open Report ↗</a>
                                </div>
                            </div>
                        `).join('');
                    }
                }
            } catch(e) {}
        }

        document.addEventListener('DOMContentLoaded', function() {
            loadRecentReports();
            const token = document.getElementById('token').value.trim();
            if (token && token.length >= 15) {
                autoDetectPortal();
            } else {
                setPlansLocked(true);
            }
        });
        window.addEventListener('pageshow', function() {
            loadRecentReports();
        });
    </script>
</body>
</html>
"""

class AuditServerHandler(BaseHTTPRequestHandler):
    def _send_no_report_page(self, custom_msg: str = None):
        self.send_response(404 if custom_msg else 200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        title = "Report Not Found" if custom_msg else "No Audit Report Generated Yet"
        body_msg = custom_msg or "Please connect your HubSpot Private App token and select your plans to run a live portal audit."
        fallback_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #0f172a; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .box {{ background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 40px; text-align: center; max-width: 480px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }}
        h2 {{ margin-bottom: 12px; }}
        p {{ color: #64748b; margin-bottom: 24px; font-size: 15px; }}
        a {{ display: inline-block; background: #ff5c35; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; }}
        a:hover {{ background: #e0441e; }}
    </style>
</head>
<body>
    <div class="box">
        <h2>{title}</h2>
        <p>{body_msg}</p>
        <a href="/">Go to Portal Analyzer</a>
    </div>
</body>
</html>"""
        self.wfile.write(fallback_html.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/health", "/healthz", "/ping"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b"OK")

        elif parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(INDEX_HTML.encode("utf-8"))

        elif parsed.path == "/api/reports":
            reports = []
            seen_portals = set()
            if os.path.isdir(REPORTS_DIR):
                file_list = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")]
                file_list.sort(key=lambda x: os.path.getmtime(os.path.join(REPORTS_DIR, x)), reverse=True)
                for f in file_list:
                    fpath = os.path.join(REPORTS_DIR, f)
                    mtime = os.path.getmtime(fpath)
                    rid = f[:-5]
                    parts = rid.split("-")
                    portal_id = parts[-1] if len(parts) > 1 and parts[-1].isdigit() else ""
                    if not portal_id and len(parts) > 2 and parts[-2].isdigit():
                        portal_id = parts[-2]
                    
                    comp_name = parts[0].replace("_", " ").title() if len(parts) > 0 else "Portal"
                    p_key = portal_id if portal_id else rid
                    if p_key in seen_portals:
                        continue
                    seen_portals.add(p_key)

                    reports.append({
                        "report_id": rid,
                        "url": f"/report/{rid}",
                        "company_name": comp_name,
                        "portal_id": portal_id,
                        "timestamp": mtime,
                        "date_str": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
                    })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "reports": reports}).encode("utf-8"))

        elif parsed.path in ["/report", "/report/"]:
            if os.path.exists(LATEST_REPORT_PATH):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(LATEST_REPORT_PATH, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._send_no_report_page()

        elif parsed.path.startswith("/report/"):
            report_slug = parsed.path[len("/report/"):].strip("/")
            if report_slug.endswith(".html"):
                report_slug = report_slug[:-5]

            report_file = None
            cand = os.path.join(REPORTS_DIR, f"{report_slug}.html")
            if os.path.isfile(cand):
                report_file = cand
            else:
                if os.path.isdir(REPORTS_DIR):
                    matches = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html") and report_slug in f]
                    if matches:
                        matches.sort(key=lambda x: os.path.getmtime(os.path.join(REPORTS_DIR, x)), reverse=True)
                        report_file = os.path.join(REPORTS_DIR, matches[0])

            if report_file and os.path.isfile(report_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(report_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._send_no_report_page(custom_msg=f"Audit report for '{report_slug}' not found.")

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/detect":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)
            try:
                import math
                req_data = json.loads(post_body.decode("utf-8"))
                token = req_data.get("token")
                collector = HubSpotCollector(token)
                acc = collector.collect_account_info()
                seats = collector.collect_users_and_seats()
                contacts = collector.collect_contacts_quota()
                auto = collector.collect_automation()
                calls = collector.collect_calls()
                cms = collector.collect_marketing_and_cms()

                mkt_cnt = contacts.get("marketing_contacts") or contacts.get("total_contacts", 0)
                tot_cnt = contacts.get("total_contacts", 0)

                # Infer Marketing plan based on portal automation
                detected_mkt_tier = "Professional" if auto.get("active_workflows", 0) > 0 else ("Starter" if mkt_cnt > 0 else "Free")

                # Detect Sales & Service tiers from live user seat assignments (User Provisioning API)
                detected_sales_tier = seats.get("detected_sales_tier") or "Free"
                detected_service_tier = seats.get("detected_service_tier") or "Free"
                detected_revenue_tier = seats.get("detected_revenue_tier") or "Free"

                # Detect Content Hub based on blog/landing pages volume
                detected_content_tier = "Professional" if cms.get("blog_posts_count", 0) > 10 else "Free"
                detected_data_tier = "Free"
                detected_crm_tier = "Free"

                # Calculate official HubSpot marketing contact tier ceiling:
                if detected_mkt_tier == "Professional":
                    detected_contact_tier = 2000 + (math.ceil((mkt_cnt - 2000) / 5000) * 5000) if mkt_cnt > 2000 else 2000
                elif detected_mkt_tier == "Enterprise":
                    detected_contact_tier = 10000 + (math.ceil((mkt_cnt - 10000) / 10000) * 10000) if mkt_cnt > 10000 else 10000
                else:
                    detected_contact_tier = max(1000, math.ceil(max(1, mkt_cnt) / 1000) * 1000)

                portal_id = str(acc.get("portal_id", ""))
                # Dynamic AI credits based on detected subscription tiers (NO hardcoded portal IDs or counts)
                has_pro_or_ent = any(t in ["Professional", "Enterprise"] for t in [
                    detected_mkt_tier,
                    detected_sales_tier,
                    detected_service_tier,
                    detected_revenue_tier,
                    detected_content_tier
                ])
                total_credits = 3000 if has_pro_or_ent else 0
                used_credits = 0  # Dynamic default; user enters live usage from portal in the dashboard

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "portal_id": portal_id,
                    "company_name": acc.get("company_name"),
                    "currency": acc.get("currency", "USD"),
                    "detected_mkt_tier": detected_mkt_tier,
                    "detected_sales_tier": detected_sales_tier,
                    "detected_service_tier": detected_service_tier,
                    "detected_content_tier": detected_content_tier,
                    "detected_revenue_tier": detected_revenue_tier,
                    "detected_data_tier": detected_data_tier,
                    "detected_crm_tier": detected_crm_tier,
                    "paid_sales_seats": seats.get("paid_sales_seats", 0),
                    "paid_service_seats": seats.get("paid_service_seats", 0),
                    "paid_revenue_seats": seats.get("paid_revenue_seats", 0),
                    "core_seats_used": seats.get("core_seats_used", 0),
                    "total_users": seats.get("total_users", 0),
                    "total_contacts": tot_cnt,
                    "marketing_contacts": mkt_cnt,
                    "detected_contact_tier": detected_contact_tier,
                    "total_credits": total_credits,
                    "used_credits": used_credits,
                    "total_workflows": auto.get("total_workflows", 0),
                    "active_workflows": auto.get("active_workflows", 0),
                    "total_sequences": auto.get("total_sequences", 0),
                    "total_calls": calls.get("total_calls", 0)
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        elif parsed.path == "/api/audit":
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

                # Generate permanent account-specific report URL
                portal_id = str(audit_result.get("account", {}).get("portal_id", "portal"))
                company_name = audit_result.get("account", {}).get("company_name", "account")
                clean_slug = re.sub(r'[^a-zA-Z0-9]+', '-', company_name.lower()).strip('-') or "portal"

                # Permanent account report ID: e.g. "geciproducts-50849936"
                report_id = f"{clean_slug}-{portal_id}"
                unique_report_path = os.path.join(REPORTS_DIR, f"{report_id}.html")
                rg.generate_html(unique_report_path)

                # Also save a timestamped archive snapshot, e.g. "geciproducts-50849936-20261124_172030.html"
                time_tag = time.strftime("%Y%m%d_%H%M%S")
                archive_path = os.path.join(REPORTS_DIR, f"{clean_slug}-{portal_id}-{time_tag}.html")
                rg.generate_html(archive_path)

                report_url = f"/report/{report_id}"

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "report_id": report_id,
                    "report_url": report_url,
                    "company_name": company_name,
                    "portal_id": portal_id
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port: int = None, host: str = "0.0.0.0"):
    if port is None:
        port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8080))
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, AuditServerHandler)
    print("==================================================================")
    print(f" HubSpot Plan Analyzer Web Server Running on: http://{host}:{port}")
    print(f" Listening on {host}:{port} (PORT env={os.environ.get('PORT', 'default 8080')})")
    print(" Press Ctrl+C to stop.")
    print("==================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    port_arg = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port_arg = int(sys.argv[1])
    run_server(port=port_arg)
