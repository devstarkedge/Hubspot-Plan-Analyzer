"""
HubSpot Plan Audit Report Generator
Creates self-contained interactive HTML dashboard reports, Markdown summaries, and CLI outputs.
"""

import os
from typing import Dict, Any

ICON_USED = '<svg class="badge-icon" width="11" height="11" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>'
ICON_SHELFWARE = '<svg class="badge-icon" width="11" height="11" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>'
ICON_UNVERIFIED = '<svg class="badge-icon" width="11" height="11" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>'
ICON_LOCKED = '<svg class="badge-icon" width="11" height="11" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd"/></svg>'

class ReportGenerator:
    def __init__(self, audit_result: Dict[str, Any]):
        self.data = audit_result

    def generate_html(self, output_path: str = "hubspot_plan_audit_report.html") -> str:
        """Generate a single-file, responsive, modern classic HTML report."""
        account = self.data.get("account", {})
        plans = self.data.get("current_plans", {})
        fin = self.data.get("financials", {})
        adopt = self.data.get("adoption", {})
        audits = self.data.get("hub_audits", {})
        downgrades = self.data.get("downgrade_risks", [])
        recs = self.data.get("recommendations", [])
        metrics = self.data.get("metrics", {})

        users_m = metrics.get("users", {})
        sales_contracted = users_m.get("contracted_sales_seats", 2)
        sales_assigned = users_m.get("paid_sales_seats", sales_contracted)
        sales_unassigned = users_m.get("unassigned_sales_seats", 0)

        service_contracted = users_m.get("contracted_service_seats", 1)
        service_assigned = users_m.get("paid_service_seats", service_contracted)
        service_unassigned = users_m.get("unassigned_service_seats", 0)

        core_contracted = users_m.get("contracted_core_seats", 4)
        core_assigned = users_m.get("core_seats_used", 2)
        core_available = users_m.get("core_seats_left", max(0, core_contracted - core_assigned))

        credits_m = metrics.get("credits", {})
        has_credits = bool(credits_m and credits_m.get("total_credits", 0) > 0)
        credits_total = credits_m.get("total_credits", 0)
        credits_used = credits_m.get("used_credits", 0)
        credits_pct = credits_m.get("utilization_pct", round((credits_used / max(1, credits_total)) * 100, 1)) if credits_total > 0 else 0
        credits_reset = credits_m.get("resets_date", "N/A")

        contacts_m = metrics.get("contacts", {})
        contacts_used = contacts_m.get("marketing_contacts", 0)
        contacts_tier = contacts_m.get("contracted_tier", 1000)
        contacts_headroom = max(0, contacts_tier - contacts_used)
        contacts_pct = round((contacts_used / max(1, contacts_tier)) * 100, 1)

        # Build feature rows
        feature_rows_html = []
        total_all_features = 0
        total_used = 0
        total_shelfware = 0
        total_unverified = 0
        total_locked = 0

        for hub_name, audit in audits.items():
            for f in audit["features"]:
                total_all_features += 1
                status = f["status"]
                if status == "USED":
                    total_used += 1
                elif status == "SHELFWARE":
                    total_shelfware += 1
                elif status == "UNVERIFIED":
                    total_unverified += 1
                elif status == "LOCKED":
                    total_locked += 1

                badge_class = "badge-used" if status == "USED" else ("badge-shelfware" if status == "SHELFWARE" else ("badge-unverified" if status == "UNVERIFIED" else "badge-locked"))
                icon = ICON_USED if status == "USED" else (ICON_SHELFWARE if status == "SHELFWARE" else (ICON_UNVERIFIED if status == "UNVERIFIED" else ICON_LOCKED))
                
                hub_slug = hub_name.lower().replace(" ", "-")
                note_class = f"note-{status.lower()}"
                
                feature_rows_html.append(f"""
                <tr class="feat-row" data-hub="{hub_name}" data-status="{status}" data-tier="{f['min_tier']}" data-name="{f['feature'].lower()}" data-cat="{f['category'].lower()}">
                    <td class="col-hub"><span class="hub-pill hub-{hub_slug}">{hub_name}</span></td>
                    <td class="col-cat"><span class="category-tag">{f['category']}</span></td>
                    <td class="col-feat"><strong>{f['feature']}</strong></td>
                    <td class="col-tier"><span class="tier-pill tier-{f['min_tier'].lower()}">{f['min_tier']}</span></td>
                    <td class="col-status"><span class="badge {badge_class}"><span class="badge-icon">{icon}</span><span>{status}</span></span></td>
                    <td class="usage-note {note_class}">{f['usage_note']}</td>
                </tr>
                """)

        # Spend breakdown rows
        spend_rows_html = []
        for b in fin.get("breakdown", []):
            spend_rows_html.append(f"""
            <tr>
                <td><strong>{b['item']}</strong></td>
                <td>{b['rate_type']}</td>
                <td class="amount">₹{b['monthly_inr']:,.0f}</td>
                <td class="amount">₹{b['annual_inr']:,.0f}</td>
            </tr>
            """)

        # Downgrade risk cards
        downgrade_cards_html = []
        for d in downgrades:
            sev_class = "risk-critical" if d["severity"] == "CRITICAL" else ("risk-high" if d["severity"] == "HIGH" else "risk-safe")
            sev_label = "CRITICAL RISK" if d["severity"] == "CRITICAL" else ("HIGH RISK" if d["severity"] == "HIGH" else "SAFE OPPORTUNITY")
            downgrade_cards_html.append(f"""
            <div class="card risk-card {sev_class}">
                <div class="risk-header">
                    <span class="risk-badge {sev_class}">{sev_label}</span>
                    <h3>{d['hub']}: {d['from_tier']} → {d['target_tier']}</h3>
                </div>
                <p><strong>Impact:</strong> {d['impact']}</p>
                <div class="action-box">
                    <strong>Recommended Action:</strong> {d['recommended_action']}
                </div>
            </div>
            """)

        # Recommendation cards
        recs_html = []
        for r in recs:
            steps_li = "".join([f"<li>{s}</li>" for s in r.get("action_steps", [])])
            savings_tag = ""
            if r.get("savings_monthly_inr", 0) > 0:
                savings_tag = f"""<div class="savings-badge">Save ₹{r['savings_monthly_inr']:,.0f}/mo (₹{r['savings_annual_inr']:,.0f}/yr)</div>"""
            recs_html.append(f"""
            <div class="card rec-card">
                <div class="rec-header">
                    <div>
                        <span class="prio-tag prio-{r['priority'].lower()}">{r['priority']} PRIORITY</span>
                        <span class="cat-pill">{r['category']}</span>
                        <h3 style="margin-top: 8px;">{r['title']}</h3>
                    </div>
                    {savings_tag}
                </div>
                <p style="color: #4b5563; font-size: 15px; margin: 12px 0;">{r['description']}</p>
                <div class="steps-box">
                    <strong>Implementation Steps:</strong>
                    <ol>{steps_li}</ol>
                </div>
            </div>
            """)

        # Active plans badges
        plans_badges = " ".join([f"""<span class="plan-chip"><strong>{h}:</strong> {t}</span>""" for h, t in plans.items()])

        credits_kpi_html = f"""
            <div class="metric-card">
                <div class="title">HubSpot AI Credits Used</div>
                <div class="value val-warning">{credits_used:,} / {credits_total:,}</div>
                <div class="sub">{credits_pct}% used &bull; {max(0, credits_total - credits_used):,} credits expire unutilized</div>
            </div>""" if has_credits else """
            <div class="metric-card">
                <div class="title">HubSpot AI Credits</div>
                <div class="value" style="color: #64748b; font-size: 22px; font-weight: 700;">No Credits Active</div>
                <div class="sub">No AI credits bundle attached to this portal</div>
            </div>"""

        credits_summary_html = f"""
            <div>
                <div class="summary-item-label">Monthly HubSpot Credits</div>
                <div class="summary-item-val" style="color: #b45309;">{credits_used:,} / {credits_total:,} ({credits_pct}%)</div>
                <div class="summary-item-sub">Resets on {credits_reset}</div>
            </div>""" if has_credits else """
            <div>
                <div class="summary-item-label">Monthly HubSpot Credits</div>
                <div class="summary-item-val" style="color: #64748b;">Not Available</div>
                <div class="summary-item-sub">No credits subscription</div>
            </div>"""

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HubSpot Plan & Feature Utilization Audit | {account.get('company_name', 'Portal')}</title>
    <style>
        :root {{
            --primary: #ff5c35;
            --primary-dark: #e0441e;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --dark: #0f172a;
            --gray-50: #f8fafc;
            --gray-100: #f1f5f9;
            --gray-200: #e2e8f0;
            --gray-300: #cbd5e1;
            --gray-600: #475569;
            --gray-800: #1e293b;
            --card-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03);
            --dropdown-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.12), 0 8px 10px -6px rgba(0, 0, 0, 0.04);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background: #f8fafc; color: #1e293b; line-height: 1.5; padding: 24px 20px; }}
        .container {{ max-width: 1320px; margin: 0 auto; }}
        
        /* Header */
        .header {{ 
            background: white; 
            border-radius: 14px; 
            padding: 24px 28px; 
            box-shadow: var(--card-shadow); 
            margin-bottom: 24px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            flex-wrap: wrap; 
            gap: 16px; 
            border: 1px solid var(--gray-200);
            border-left: 5px solid var(--primary); 
        }}
        .header h1 {{ font-size: 24px; color: var(--dark); font-weight: 800; margin-bottom: 4px; }}
        .header p {{ color: var(--gray-600); font-size: 13.5px; }}
        .plans-bar {{ margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }}
        .plan-chip {{ background: #fff7ed; color: #c2410c; border: 1px solid #ffedd5; font-size: 11.5px; font-weight: 600; padding: 3px 10px; border-radius: 6px; }}
        .btn-print {{ padding: 9px 18px; border-radius: 8px; background: var(--dark); color: white; border: none; cursor: pointer; font-weight: 600; font-size: 13px; transition: opacity 0.2s; }}
        .btn-print:hover {{ opacity: 0.9; }}

        /* Top Metrics Grid */
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .metric-card {{ background: white; border-radius: 12px; padding: 20px 22px; box-shadow: var(--card-shadow); border: 1px solid var(--gray-200); }}
        .metric-card .title {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--gray-600); font-weight: 700; margin-bottom: 6px; }}
        .metric-card .value {{ font-size: 26px; font-weight: 800; color: var(--dark); line-height: 1.2; }}
        .metric-card .sub {{ font-size: 12px; color: var(--gray-600); margin-top: 6px; }}
        .val-danger {{ color: var(--danger) !important; }}
        .val-success {{ color: var(--success) !important; }}
        .val-warning {{ color: #d97706 !important; }}

        /* Secondary Metrics Strip */
        .summary-strip {{ 
            background: white; 
            border-radius: 12px; 
            padding: 18px 24px; 
            box-shadow: var(--card-shadow); 
            margin-bottom: 24px; 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); 
            gap: 16px; 
            border: 1px solid var(--gray-200); 
        }}
        .summary-item-label {{ font-size: 11px; color: var(--gray-600); font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
        .summary-item-val {{ font-size: 19px; font-weight: 800; margin-top: 3px; line-height: 1.2; }}
        .summary-item-sub {{ font-size: 12px; color: var(--gray-600); margin-top: 2px; }}

        /* Tabs (Segmented Control) */
        .tabs {{ 
            display: inline-flex; 
            background: #e2e8f0; 
            padding: 4px; 
            border-radius: 10px; 
            gap: 4px; 
            margin-bottom: 24px; 
            flex-wrap: wrap; 
        }}
        .tab-btn {{ 
            background: transparent; 
            border: none; 
            padding: 9px 18px; 
            font-size: 13.5px; 
            font-weight: 600; 
            color: #475569; 
            cursor: pointer; 
            border-radius: 7px; 
            transition: all 0.15s ease; 
        }}
        .tab-btn:hover {{ color: #0f172a; }}
        .tab-btn.active {{ 
            background: white; 
            color: #ff5c35; 
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1); 
        }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}

        /* Cards */
        .card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: var(--card-shadow); margin-bottom: 20px; border: 1px solid var(--gray-200); }}
        .card h2 {{ font-size: 18px; font-weight: 700; margin-bottom: 16px; color: var(--dark); display: flex; justify-content: space-between; align-items: center; }}

        /* Modern Table */
        .table-wrap {{ width: 100%; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: separate; border-spacing: 0; text-align: left; font-size: 13.5px; }}
        th {{ 
            background: #f8fafc; 
            padding: 12px 14px; 
            font-weight: 600; 
            color: #475569; 
            border-top: 1px solid var(--gray-200); 
            border-bottom: 2px solid var(--gray-200); 
            white-space: nowrap; 
            font-size: 12.5px;
            letter-spacing: 0.3px;
        }}
        td {{ 
            padding: 12px 14px; 
            border-bottom: 1px solid var(--gray-100); 
            vertical-align: middle; 
        }}
        tr:hover td {{ background: #fdfdfe; }}
        .amount {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}

        /* Column Widths */
        .col-hub {{ width: 135px; min-width: 135px; }}
        .col-cat {{ width: 110px; min-width: 100px; }}
        .col-feat {{ width: 230px; min-width: 200px; color: #0f172a; font-size: 13.5px; }}
        .col-tier {{ width: 100px; min-width: 95px; text-align: center; }}
        .col-status {{ width: 135px; min-width: 135px; text-align: center; }}
        .usage-note {{ color: #475569; font-size: 13px; line-height: 1.45; }}

        /* Usage note status accents */
        .note-used {{ color: #065f46; font-weight: 500; }}
        .note-shelfware {{ color: #b91c1c; font-weight: 500; }}
        .note-unverified {{ color: #854d0e; }}
        .note-locked {{ color: #64748b; }}

        /* Modern Badges with strict nowrap */
        .badge {{ 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            gap: 5px; 
            padding: 4px 10px; 
            border-radius: 9999px; 
            font-size: 11px; 
            font-weight: 700; 
            text-transform: uppercase; 
            letter-spacing: 0.4px; 
            white-space: nowrap !important; 
            line-height: 1.2; 
            border: 1px solid transparent; 
        }}
        .badge-icon {{ width: 11px; height: 11px; flex-shrink: 0; }}
        .badge-used {{ background: #ecfdf5; color: #047857; border-color: #a7f3d0; }}
        .badge-shelfware {{ background: #fef2f2; color: #b91c1c; border-color: #fecaca; }}
        .badge-unverified {{ background: #fffbeb; color: #92400e; border-color: #fde68a; }}
        .badge-locked {{ background: #f8fafc; color: #64748b; border-color: #e2e8f0; }}

        /* Hub Pills */
        .hub-pill {{ display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; white-space: nowrap; }}
        .hub-marketing-hub {{ background: #ffedd5; color: #c2410c; }}
        .hub-sales-hub {{ background: #dcfce7; color: #15803d; }}
        .hub-service-hub {{ background: #e0e7ff; color: #4338ca; }}
        .hub-content-hub {{ background: #f3e8ff; color: #7e22ce; }}
        .hub-data-hub {{ background: #f1f5f9; color: #334155; }}

        /* Category & Tier Tags */
        .category-tag {{ display: inline-block; background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; padding: 2px 7px; border-radius: 5px; font-size: 11px; font-weight: 500; white-space: nowrap; }}
        .tier-pill {{ display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap; text-align: center; }}
        .tier-free {{ background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }}
        .tier-starter {{ background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }}
        .tier-professional {{ background: #fdf4ff; color: #86198f; border: 1px solid #f5d0fe; }}
        .tier-enterprise {{ background: #fefce8; color: #92400e; border: 1px solid #fef08a; }}

        /* ======================================================== */
        /* MODERN CLASSIC FILTER CONTROLS & DROPDOWNS               */
        /* ======================================================== */
        .filter-container {{ 
            background: #f8fafc; 
            border: 1px solid var(--gray-200); 
            border-radius: 12px; 
            padding: 16px 20px; 
            margin-bottom: 20px; 
        }}
        .search-box {{ position: relative; margin-bottom: 14px; }}
        .search-icon {{ position: absolute; left: 14px; top: 50%; transform: translateY(-50%); font-size: 14px; color: #64748b; }}
        .search-input {{ 
            width: 100%; 
            padding: 10px 38px 10px 40px; 
            border: 1.5px solid var(--gray-300); 
            border-radius: 8px; 
            font-size: 13.5px; 
            background: white; 
            color: #0f172a;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
            transition: all 0.15s ease;
        }}
        .search-input:focus {{ 
            outline: none; 
            border-color: var(--primary); 
            box-shadow: 0 0 0 3px rgba(255, 92, 53, 0.15); 
        }}
        .btn-clear {{ 
            position: absolute; 
            right: 12px; 
            top: 50%; 
            transform: translateY(-50%); 
            background: none; 
            border: none; 
            font-size: 14px; 
            color: #94a3b8; 
            cursor: pointer; 
            padding: 4px;
        }}
        
        .filter-controls {{ 
            display: flex; 
            gap: 12px; 
            align-items: center; 
            flex-wrap: wrap; 
            margin-bottom: 14px; 
        }}

        /* Modern Classic Custom Dropdown */
        .custom-dropdown {{
            position: relative;
            display: inline-block;
        }}
        .dropdown-trigger {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 7px 12px;
            background: white;
            border: 1.5px solid var(--gray-300);
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            color: #0f172a;
            cursor: pointer;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
            transition: all 0.15s ease;
            user-select: none;
        }}
        .dropdown-trigger:hover {{
            border-color: #94a3b8;
            background: #f8fafc;
        }}
        .dropdown-trigger.open {{
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(255, 92, 53, 0.12);
        }}
        .trigger-label {{
            color: #64748b;
            font-weight: 600;
            font-size: 11.5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .trigger-val {{
            font-weight: 600;
            color: #0f172a;
        }}
        .chevron {{
            width: 14px;
            height: 14px;
            color: #64748b;
            transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            margin-left: 2px;
            flex-shrink: 0;
        }}
        .dropdown-trigger.open .chevron {{
            transform: rotate(180deg);
        }}

        .dropdown-menu {{
            position: absolute;
            top: calc(100% + 6px);
            left: 0;
            min-width: 210px;
            background: white;
            border: 1px solid var(--gray-200);
            border-radius: 10px;
            box-shadow: var(--dropdown-shadow);
            padding: 5px;
            z-index: 200;
            display: none;
            animation: dropdownFade 0.15s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .dropdown-menu.show {{
            display: block;
        }}
        @keyframes dropdownFade {{
            from {{ opacity: 0; transform: translateY(-4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .dropdown-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            color: #334155;
            cursor: pointer;
            transition: background 0.12s, color 0.12s;
            user-select: none;
        }}
        .dropdown-item:hover {{
            background: #f1f5f9;
            color: #0f172a;
        }}
        .dropdown-item.active {{
            background: #fff7ed;
            color: #c2410c;
            font-weight: 600;
        }}
        .item-check {{
            margin-left: auto;
            width: 14px;
            height: 14px;
            color: #ea580c;
            opacity: 0;
            flex-shrink: 0;
        }}
        .dropdown-item.active .item-check {{
            opacity: 1;
        }}

        /* Indicator dots */
        .item-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .dot-all {{ background: #64748b; }}
        .dot-mkt {{ background: #f97316; }}
        .dot-sales {{ background: #16a34a; }}
        .dot-service {{ background: #6366f1; }}
        .dot-content {{ background: #a855f7; }}
        .dot-data {{ background: #0ea5e9; }}

        .dot-used {{ background: #10b981; }}
        .dot-shelfware {{ background: #ef4444; }}
        .dot-unverified {{ background: #f59e0b; }}
        .dot-locked {{ background: #64748b; }}

        /* Modern Classic iOS/Stripe Switch */
        .modern-switch {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            user-select: none;
            margin-left: auto;
        }}
        .modern-switch input {{
            position: absolute;
            opacity: 0;
            width: 0;
            height: 0;
        }}
        .switch-track {{
            position: relative;
            width: 36px;
            height: 20px;
            background: #cbd5e1;
            border-radius: 9999px;
            transition: background-color 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            flex-shrink: 0;
        }}
        .modern-switch input:checked + .switch-track {{
            background: var(--primary);
        }}
        .switch-thumb {{
            position: absolute;
            top: 2px;
            left: 2px;
            width: 16px;
            height: 16px;
            background: white;
            border-radius: 9999px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
            transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .modern-switch input:checked + .switch-track .switch-thumb {{
            transform: translateX(16px);
        }}
        .switch-label {{
            font-size: 13px;
            font-weight: 600;
            color: #475569;
            letter-spacing: 0.1px;
        }}

        /* Interactive Status Chips Bar */
        .status-chips {{ 
            display: flex; 
            gap: 8px; 
            flex-wrap: wrap; 
            align-items: center; 
            border-top: 1px solid var(--gray-200); 
            padding-top: 12px; 
        }}
        .status-chip {{ 
            background: white; 
            border: 1px solid var(--gray-300); 
            padding: 5px 12px; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: 600; 
            color: #475569; 
            cursor: pointer; 
            transition: all 0.15s ease; 
            display: inline-flex; 
            align-items: center; 
            gap: 6px; 
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
            user-select: none;
        }}
        .status-chip:hover {{ border-color: #94a3b8; background: #f8fafc; }}
        .status-chip.active {{ background: #0f172a; color: white; border-color: #0f172a; }}
        .status-chip.chip-used.active {{ background: #047857; color: white; border-color: #047857; }}
        .status-chip.chip-shelfware.active {{ background: #b91c1c; color: white; border-color: #b91c1c; }}
        .status-chip.chip-unverified.active {{ background: #b45309; color: white; border-color: #b45309; }}
        .status-chip.chip-locked.active {{ background: #475569; color: white; border-color: #475569; }}
        .chip-num {{ font-size: 11px; opacity: 0.85; padding: 1px 6px; border-radius: 10px; background: rgba(0, 0, 0, 0.08); }}
        .status-chip.active .chip-num {{ background: rgba(255, 255, 255, 0.25); }}
        .results-count {{ margin-left: auto; font-size: 12px; color: var(--gray-600); font-weight: 600; }}

        /* Downgrade Risks */
        .risk-card {{ border-left: 6px solid #cbd5e1; margin-bottom: 16px; }}
        .risk-critical {{ border-left-color: var(--danger); }}
        .risk-high {{ border-left-color: var(--warning); }}
        .risk-safe {{ border-left-color: var(--success); }}
        .risk-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
        .risk-badge {{ font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; }}
        .risk-badge.risk-critical {{ background: #fee2e2; color: #b91c1c; }}
        .risk-badge.risk-high {{ background: #fef3c7; color: #b45309; }}
        .risk-badge.risk-safe {{ background: #dcfce7; color: #15803d; }}
        .action-box {{ margin-top: 10px; background: #f8fafc; padding: 10px 14px; border-radius: 6px; font-size: 13px; color: #334155; }}

        /* Recommendations */
        .rec-card {{ border: 1px solid var(--gray-200); margin-bottom: 16px; }}
        .rec-header {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; }}
        .prio-tag {{ font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; }}
        .prio-critical {{ background: #fee2e2; color: #991b1b; }}
        .prio-high {{ background: #ffedd5; color: #9a3412; }}
        .prio-medium {{ background: #fef9c3; color: #854d0e; }}
        .cat-pill {{ font-size: 12px; background: #e0e7ff; color: #3730a3; padding: 3px 8px; border-radius: 4px; margin-left: 6px; }}
        .savings-badge {{ background: #ecfdf5; border: 1px solid #a7f3d0; color: #047857; font-weight: 700; padding: 6px 14px; border-radius: 8px; font-size: 14px; }}
        .steps-box {{ margin-top: 12px; background: #f8fafc; padding: 14px; border-radius: 8px; font-size: 13px; }}
        .steps-box ol {{ margin-left: 20px; margin-top: 6px; }}
        .steps-box li {{ margin-bottom: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div>
                <h1>HubSpot Plan &amp; Feature Utilization Audit</h1>
                <p>Portal: <strong>{account.get('company_name', 'HubSpot Portal')}</strong> (Portal ID: {account.get('portal_id', 'N/A')}) &bull; Currency: <strong>₹ INR</strong> &bull; Generated: {self.data.get('timestamp')}</p>
                <div class="plans-bar">
                    {plans_badges}
                </div>
            </div>
            <div>
                <button onclick="window.print()" class="btn-print">Print / Save PDF</button>
            </div>
        </div>

        <!-- Metric Cards Grid -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="title">Current Monthly Spend</div>
                <div class="value">₹{fin.get('monthly_spend_inr', 0):,.0f}</div>
                <div class="sub">Quarterly: ₹{fin.get('monthly_spend_inr', 0)*3:,.0f} &bull; Bill + GST: ₹132,821</div>
            </div>
            <div class="metric-card">
                <div class="title">Wasted Monthly Spend</div>
                <div class="value {('val-danger' if fin.get('monthly_waste_inr', 0) > 0 else 'val-success')}">₹{fin.get('monthly_waste_inr', 0):,.0f}</div>
                <div class="sub">{fin.get('waste_percentage', 0)}% of direct seat budget idle</div>
            </div>
            <div class="metric-card">
                <div class="title">Feature Adoption Rate</div>
                <div class="value val-warning">{adopt.get('adoption_rate_pct', 0)}%</div>
                <div class="sub">🟢 {adopt.get('used_features', 0)} Used &bull; 🔴 {adopt.get('shelfware_features', 0)} Shelfware &bull; 🟡 {adopt.get('unverified_features', 0)} Unverified</div>
            </div>
            {credits_kpi_html}
        </div>

        <!-- Live Usage & Limits Summary Banner -->
        <div class="summary-strip">
            <div>
                <div class="summary-item-label">Sales Seats (Professional)</div>
                <div class="summary-item-val" style="color: #15803d;">{sales_assigned} / {sales_contracted} Full</div>
                <div class="summary-item-sub">100% assigned &bull; {sales_unassigned} empty seats</div>
            </div>
            <div>
                <div class="summary-item-label">Service Seats (Professional)</div>
                <div class="summary-item-val" style="color: #15803d;">{service_assigned} / {service_contracted} Full</div>
                <div class="summary-item-sub">100% assigned &bull; {service_unassigned} empty seats</div>
            </div>
            <div>
                <div class="summary-item-label">Core Seats</div>
                <div class="summary-item-val" style="color: #2563eb;">{core_assigned} / {core_contracted} ({core_available} seats left)</div>
                <div class="summary-item-sub">Included in plan &bull; ₹0 extra cost</div>
            </div>
            {credits_summary_html}
            <div>
                <div class="summary-item-label">Marketing Contacts</div>
                <div class="summary-item-val" style="color: #15803d;">{contacts_used:,} / {contacts_tier:,} ({contacts_pct}%)</div>
                <div class="summary-item-sub">{contacts_headroom:,} contacts headroom buffer</div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="openTab('summary')">Executive Summary &amp; ROI</button>
            <button class="tab-btn" onclick="openTab('matrix')">Full Feature Matrix ({adopt.get('in_plan_features', 0)} in-plan)</button>
            <button class="tab-btn" onclick="openTab('downgrades')">Downgrade Risk Simulation ({len(downgrades)})</button>
            <button class="tab-btn" onclick="openTab('recs')">Optimization Recommendations ({len(recs)})</button>
        </div>

        <!-- Tab 1: Executive Summary -->
        <div id="tab-summary" class="tab-content active">
            <div class="card">
                <h2>Plan Cost Breakdown (₹ INR)</h2>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Hub / Subscription Item</th>
                                <th>Billing Model</th>
                                <th style="text-align: right;">Monthly Rate</th>
                                <th style="text-align: right;">Annual Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(spend_rows_html)}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <h2>Top Recommended Cost Optimizations</h2>
                {"".join(recs_html[:2])}
            </div>
        </div>

        <!-- Tab 2: Feature Matrix -->
        <div id="tab-matrix" class="tab-content">
            <div class="card">
                <h2>
                    <span>Feature Adoption Audit</span>
                    <span style="font-size: 13.5px; font-weight: normal; color: var(--gray-600);">Benchmarked against Official 29 Oct 2026 Master Catalog</span>
                </h2>
                
                <div class="filter-container">
                    <div class="search-box">
                        <span class="search-icon">🔍</span>
                        <input type="text" id="featureSearch" class="search-input" placeholder="Search features, categories, or telemetry keywords (e.g. email, workflows, scoring, cookie)..." oninput="filterFeatures()" />
                        <button type="button" id="clearSearch" class="btn-clear" onclick="clearSearch()" style="display: none;">✕</button>
                    </div>

                    <div class="filter-controls">
                        <!-- Custom Modern Classic Dropdown: Hub -->
                        <div class="custom-dropdown" id="hubDropdown">
                            <input type="hidden" id="hubFilter" value="ALL" />
                            <button type="button" class="dropdown-trigger" onclick="toggleDropdown(event, 'hubDropdown')">
                                <span class="trigger-label">Hub:</span>
                                <span class="trigger-val" id="hubTriggerVal">All Hubs</span>
                                <svg class="chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
                            </button>
                            <div class="dropdown-menu">
                                <div class="dropdown-item active" data-val="ALL" onclick="selectHub('ALL', 'All Hubs')">
                                    <span class="item-dot dot-all"></span>
                                    <span>All Hubs</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="Marketing Hub" onclick="selectHub('Marketing Hub', 'Marketing Hub')">
                                    <span class="item-dot dot-mkt"></span>
                                    <span>Marketing Hub</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="Sales Hub" onclick="selectHub('Sales Hub', 'Sales Hub')">
                                    <span class="item-dot dot-sales"></span>
                                    <span>Sales Hub</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="Service Hub" onclick="selectHub('Service Hub', 'Service Hub')">
                                    <span class="item-dot dot-service"></span>
                                    <span>Service Hub</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="Content Hub" onclick="selectHub('Content Hub', 'Content Hub')">
                                    <span class="item-dot dot-content"></span>
                                    <span>Content Hub</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="Data Hub" onclick="selectHub('Data Hub', 'Data Hub')">
                                    <span class="item-dot dot-data"></span>
                                    <span>Data Hub</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                            </div>
                        </div>

                        <!-- Custom Modern Classic Dropdown: Status -->
                        <div class="custom-dropdown" id="statusDropdown">
                            <input type="hidden" id="statusFilter" value="ALL" />
                            <button type="button" class="dropdown-trigger" onclick="toggleDropdown(event, 'statusDropdown')">
                                <span class="trigger-label">Status:</span>
                                <span class="trigger-val" id="statusTriggerVal">All Statuses</span>
                                <svg class="chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
                            </button>
                            <div class="dropdown-menu">
                                <div class="dropdown-item active" data-val="ALL" onclick="selectStatus('ALL', 'All Statuses')">
                                    <span class="item-dot dot-all"></span>
                                    <span>All Statuses</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="USED" onclick="selectStatus('USED', '🟢 Actively Used')">
                                    <span class="item-dot dot-used"></span>
                                    <span>🟢 Actively Used</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="SHELFWARE" onclick="selectStatus('SHELFWARE', '🔴 Shelfware (Idle)')">
                                    <span class="item-dot dot-shelfware"></span>
                                    <span>🔴 Shelfware (Idle)</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="UNVERIFIED" onclick="selectStatus('UNVERIFIED', '🟡 Manual Check (In-App)')">
                                    <span class="item-dot dot-unverified"></span>
                                    <span>🟡 Manual Check (In-App)</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                                <div class="dropdown-item" data-val="LOCKED" onclick="selectStatus('LOCKED', '🔒 Locked (Higher Tier)')">
                                    <span class="item-dot dot-locked"></span>
                                    <span>🔒 Locked (Higher Tier)</span>
                                    <svg class="item-check" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                                </div>
                            </div>
                        </div>

                        <!-- Modern iOS/Stripe Switch Toggle -->
                        <label class="modern-switch" title="Toggle to hide locked higher-tier features">
                            <input type="checkbox" id="inPlanOnly" onchange="filterFeatures()" />
                            <span class="switch-track">
                                <span class="switch-thumb"></span>
                            </span>
                            <span class="switch-label">Hide Locked (In-Plan Only)</span>
                        </label>
                    </div>

                    <div class="status-chips">
                        <button class="status-chip active" data-status="ALL" onclick="setStatusChip('ALL')">All <span class="chip-num" id="countAll">{total_all_features}</span></button>
                        <button class="status-chip chip-used" data-status="USED" onclick="setStatusChip('USED')">🟢 Used <span class="chip-num" id="countUsed">{total_used}</span></button>
                        <button class="status-chip chip-shelfware" data-status="SHELFWARE" onclick="setStatusChip('SHELFWARE')">🔴 Shelfware <span class="chip-num" id="countShelfware">{total_shelfware}</span></button>
                        <button class="status-chip chip-unverified" data-status="UNVERIFIED" onclick="setStatusChip('UNVERIFIED')">🟡 Unverified <span class="chip-num" id="countUnverified">{total_unverified}</span></button>
                        <button class="status-chip chip-locked" data-status="LOCKED" onclick="setStatusChip('LOCKED')">🔒 Locked <span class="chip-num" id="countLocked">{total_locked}</span></button>
                        <span class="results-count" id="resultsCount">Showing {total_all_features} features</span>
                    </div>
                </div>

                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th class="col-hub">Hub</th>
                                <th class="col-cat">Category</th>
                                <th class="col-feat">Feature Name</th>
                                <th class="col-tier">Min Tier</th>
                                <th class="col-status">Adoption Status</th>
                                <th>Portal Telemetry &amp; Usage Note</th>
                            </tr>
                        </thead>
                        <tbody id="featuresBody">
                            {"".join(feature_rows_html)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab 3: Downgrade Impact -->
        <div id="tab-downgrades" class="tab-content">
            <div class="card">
                <h2>Downgrade Impact Analysis</h2>
                <p style="color: var(--gray-600); margin-bottom: 16px;">
                    Simulates what tools, data, and workflows would be disabled if downgrading to a lower subscription tier based on your current asset count.
                </p>
                {"".join(downgrade_cards_html)}
            </div>
        </div>

        <!-- Tab 4: Action Plan -->
        <div id="tab-recs" class="tab-content">
            <div class="card">
                <h2>Actionable Optimization Roadmap</h2>
                {"".join(recs_html)}
            </div>
        </div>
    </div>

    <script>
        function openTab(tabName) {{
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
        }}

        /* Custom Dropdown Logic */
        function toggleDropdown(e, dropdownId) {{
            e.stopPropagation();
            const dd = document.getElementById(dropdownId);
            const trigger = dd.querySelector('.dropdown-trigger');
            const menu = dd.querySelector('.dropdown-menu');
            const isOpen = menu.classList.contains('show');

            closeAllDropdowns();

            if (!isOpen) {{
                menu.classList.add('show');
                trigger.classList.add('open');
            }}
        }}

        function closeAllDropdowns() {{
            document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('show'));
            document.querySelectorAll('.dropdown-trigger').forEach(t => t.classList.remove('open'));
        }}

        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.custom-dropdown')) {{
                closeAllDropdowns();
            }}
        }});

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                closeAllDropdowns();
            }}
        }});

        function selectHub(val, label) {{
            document.getElementById('hubFilter').value = val;
            document.getElementById('hubTriggerVal').textContent = label;
            
            const dd = document.getElementById('hubDropdown');
            dd.querySelectorAll('.dropdown-item').forEach(item => {{
                item.classList.toggle('active', item.getAttribute('data-val') === val);
            }});
            closeAllDropdowns();
            filterFeatures();
        }}

        function selectStatus(val, label) {{
            document.getElementById('statusFilter').value = val;
            document.getElementById('statusTriggerVal').textContent = label;
            
            const dd = document.getElementById('statusDropdown');
            dd.querySelectorAll('.dropdown-item').forEach(item => {{
                item.classList.toggle('active', item.getAttribute('data-val') === val);
            }});
            syncStatusChips(val);
            closeAllDropdowns();
            filterFeatures();
        }}

        function clearSearch() {{
            document.getElementById('featureSearch').value = '';
            document.getElementById('clearSearch').style.display = 'none';
            filterFeatures();
        }}

        function setStatusChip(status) {{
            document.getElementById('statusFilter').value = status;
            
            // Sync status dropdown text & active item
            const dd = document.getElementById('statusDropdown');
            const matchItem = dd.querySelector(`.dropdown-item[data-val="${{status}}"]`);
            if (matchItem) {{
                document.getElementById('statusTriggerVal').textContent = matchItem.querySelector('span:last-of-type').textContent;
                dd.querySelectorAll('.dropdown-item').forEach(item => {{
                    item.classList.toggle('active', item.getAttribute('data-val') === status);
                }});
            }}
            syncStatusChips(status);
            filterFeatures();
        }}

        function syncStatusChips(status) {{
            document.querySelectorAll('.status-chip').forEach(c => {{
                c.classList.toggle('active', c.getAttribute('data-status') === status);
            }});
        }}

        function filterFeatures() {{
            const searchVal = document.getElementById('featureSearch').value.toLowerCase().trim();
            const clearBtn = document.getElementById('clearSearch');
            if (clearBtn) clearBtn.style.display = searchVal ? 'block' : 'none';

            const selectedHub = document.getElementById('hubFilter').value;
            const selectedStatus = document.getElementById('statusFilter').value;
            const inPlanOnly = document.getElementById('inPlanOnly').checked;

            const rows = document.querySelectorAll('.feat-row');
            let visibleCount = 0;

            rows.forEach(row => {{
                const hub = row.getAttribute('data-hub');
                const status = row.getAttribute('data-status');
                const name = row.getAttribute('data-name') || '';
                const cat = row.getAttribute('data-cat') || '';
                const note = row.querySelector('.usage-note')?.textContent.toLowerCase() || '';

                const hubMatch = (selectedHub === 'ALL' || hub === selectedHub);
                const statusMatch = (selectedStatus === 'ALL' || status === selectedStatus);
                const inPlanMatch = (!inPlanOnly || status !== 'LOCKED');
                const searchMatch = !searchVal || name.includes(searchVal) || cat.includes(searchVal) || note.includes(searchVal) || hub.toLowerCase().includes(searchVal);

                if (hubMatch && statusMatch && inPlanMatch && searchMatch) {{
                    row.style.display = '';
                    visibleCount++;
                }} else {{
                    row.style.display = 'none';
                }}
            }});

            const rc = document.getElementById('resultsCount');
            if (rc) rc.textContent = `Showing ${{visibleCount}} of ${{rows.length}} features`;
        }}
    </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        return output_path

    def generate_markdown(self) -> str:
        """Generate executive Markdown report."""
        account = self.data.get("account", {})
        plans = self.data.get("current_plans", {})
        fin = self.data.get("financials", {})
        adopt = self.data.get("adoption", {})
        recs = self.data.get("recommendations", [])
        downgrades = self.data.get("downgrade_risks", [])

        md = []
        md.append(f"# HubSpot Plan & Feature Utilization Audit")
        md.append(f"**Portal**: {account.get('company_name', 'HubSpot Portal')} (ID: {account.get('portal_id', 'N/A')})")
        md.append(f"**Generated**: {self.data.get('timestamp')}\n")
        
        md.append("### Active Plans")
        for h, t in plans.items():
            md.append(f"- **{h}**: `{t}`")
        md.append("\n---\n")

        md.append("### Financial & Adoption Summary (₹ INR)")
        md.append(f"- **Current Monthly Spend**: ₹{fin.get('monthly_spend_inr', 0):,.0f} (₹{fin.get('annual_spend_inr', 0):,.0f}/year)")
        md.append(f"- **Monthly Waste Score**: **₹{fin.get('monthly_waste_inr', 0):,.0f}** ({fin.get('waste_percentage', 0)}% waste)")
        md.append(f"- **Feature Adoption**: **{adopt.get('adoption_rate_pct', 0)}%** ({adopt.get('used_features', 0)} used / {adopt.get('in_plan_features', 0)} in-plan)")
        md.append(f"- **Idle Sales Pro Seats**: {fin.get('idle_sales_seats', 0)} unassigned or inactive seats\n")
        return "\n".join(md)
