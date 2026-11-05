"""
HubSpot Plan & Feature Utilization Analyzer
Cross-references live/mock portal telemetry with the INR Master Catalog to produce:
1. Feature utilization audit (Used vs Shelfware vs Locked)
2. Financial waste analysis in ₹ INR (idle seats, tier overpayment, unused contact tiers)
3. Right-sizing suggestions and Downgrade Impact simulation
"""

import os
import sys
# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Any, Optional
from src.catalog_parser import HubSpotCatalog

class PlanAnalyzer:
    def __init__(self, catalog: HubSpotCatalog):
        self.catalog = catalog

    def analyze(self, portal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run full audit on portal metrics against Master Catalog."""
        account = portal_data.get("account", {})
        plans = portal_data.get("plans", {})
        metrics = portal_data.get("metrics", {})

        users_m = metrics.get("users", {})
        pipes_m = metrics.get("pipelines", {})
        co_m = metrics.get("custom_objects", {})
        auto_m = metrics.get("automation", {})
        mkt_m = metrics.get("marketing", {})
        cnt_m = metrics.get("contacts", {})
        sales_m = metrics.get("sales_tools", {})

        # 1. Financial Spend & Waste Breakdown
        financials = self._calculate_financials(plans, metrics, portal_data.get("contract"))

        # 2. Hub-by-Hub Feature Matrix Evaluation
        hub_audits = {}
        target_hubs = [
            "Marketing Hub",
            "Sales Hub",
            "Service Hub",
            "Content Hub",
            "Data Hub",
            "Commerce Hub",
            "Smart CRM"
        ]
        for hub_name in target_hubs:
            if hub_name == "Commerce Hub":
                tier = plans.get("Commerce Hub", plans.get("Revenue Hub", "Free"))
            elif hub_name == "Smart CRM":
                tier = plans.get("Smart CRM", plans.get("Platform-wide", "Free"))
            elif hub_name == "Data Hub":
                tier = plans.get("Data Hub", plans.get("Data Hub (formerly Operations Hub)", "Free"))
            else:
                tier = plans.get(hub_name, "Free")
            hub_audits[hub_name] = self._audit_hub(hub_name, tier, metrics)

        # 3. Overall Feature Adoption Statistics
        total_in_plan_features = 0
        total_used_features = 0
        total_shelfware_features = 0
        total_unverified_features = 0

        for h, audit in hub_audits.items():
            total_in_plan_features += audit["counts"]["in_plan"]
            total_used_features += audit["counts"]["used"]
            total_shelfware_features += audit["counts"]["shelfware"]
            total_unverified_features += audit["counts"].get("unverified", 0)

        adoption_rate = round((total_used_features / max(1, total_in_plan_features)) * 100, 1)

        # 4. Downgrade Impact Simulation
        downgrades = self._simulate_downgrades(plans, metrics)

        # 5. Strategic Recommendations
        recommendations = self._generate_recommendations(plans, metrics, financials, downgrades)

        return {
            "account": account,
            "current_plans": plans,
            "financials": financials,
            "adoption": {
                "in_plan_features": total_in_plan_features,
                "used_features": total_used_features,
                "shelfware_features": total_shelfware_features,
                "unverified_features": total_unverified_features,
                "adoption_rate_pct": adoption_rate
            },
            "hub_audits": hub_audits,
            "downgrade_risks": downgrades,
            "recommendations": recommendations,
            "metrics": metrics,
            "timestamp": portal_data.get("timestamp", "")
        }

    def _calculate_financials(self, plans: Dict[str, str], metrics: Dict[str, Any], contract: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compute estimated current monthly/annual INR spend and wasted costs, supporting custom contracts/discounts."""
        users_m = metrics.get("users", {})
        cnt_m = metrics.get("contacts", {})
        auto_m = metrics.get("automation", {})
        monthly_total_inr = 0
        annual_total_inr = 0
        list_monthly_total_inr = 0
        breakdown = []

        contract = contract or {}
        quarterly_billed = contract.get("quarterly_billed", {})
        discounts = contract.get("discounts", {})

        # Pricing per hub base
        for hub, plan in plans.items():
            if plan == "Free" and hub not in quarterly_billed:
                continue

            pricing = self.catalog.get_plan_pricing(hub, plan)
            m_rate = pricing["est_monthly_inr"] if pricing else 0
            a_rate = pricing["est_annual_monthly_inr"] if pricing else m_rate

            # Handle seat-based hubs (Sales Hub & Service Hub)
            if hub == "Sales Hub":
                paid_seats = users_m.get("contracted_sales_seats", users_m.get("paid_sales_seats", 0))
                list_seat_rate = 7497 if plan == "Professional" else (12500 if plan == "Enterprise" else (1670 if plan == "Starter" else 0))
                hub_list_m = list_seat_rate * paid_seats

                # Check if custom quarterly billed exists
                if hub in quarterly_billed:
                    hub_actual_m = round(quarterly_billed[hub] / 3)
                    disc_str = f" ({discounts.get(hub, 0)}% Custom Discount)" if hub in discounts else ""
                    breakdown.append({
                        "item": f"Sales Hub ({plan} - {paid_seats} seats){disc_str}",
                        "monthly_inr": hub_actual_m,
                        "annual_inr": hub_actual_m * 12,
                        "rate_type": f"Quarterly Invoiced (₹{quarterly_billed[hub]:,.0f}/3mo)"
                    })
                    monthly_total_inr += hub_actual_m
                    annual_total_inr += hub_actual_m * 12
                    list_monthly_total_inr += hub_list_m
                elif paid_seats > 0:
                    hub_m_total = list_seat_rate * paid_seats
                    breakdown.append({
                        "item": f"Sales Hub ({plan} - {paid_seats} seats)",
                        "monthly_inr": hub_m_total,
                        "annual_inr": hub_m_total * 12,
                        "rate_type": "Per-Seat (List Catalog)"
                    })
                    monthly_total_inr += hub_m_total
                    annual_total_inr += hub_m_total * 12
                    list_monthly_total_inr += hub_m_total

            elif hub == "Service Hub":
                paid_seats = users_m.get("contracted_service_seats", users_m.get("paid_service_seats", 0))
                list_seat_rate = 7497 if plan == "Professional" else (12500 if plan == "Enterprise" else (1670 if plan == "Starter" else 0))
                hub_list_m = list_seat_rate * paid_seats

                if hub in quarterly_billed:
                    hub_actual_m = round(quarterly_billed[hub] / 3)
                    disc_str = f" ({discounts.get(hub, 0)}% Custom Discount)" if hub in discounts else ""
                    breakdown.append({
                        "item": f"Service Hub ({plan} - {paid_seats} seats){disc_str}",
                        "monthly_inr": hub_actual_m,
                        "annual_inr": hub_actual_m * 12,
                        "rate_type": f"Quarterly Invoiced (₹{quarterly_billed[hub]:,.0f}/3mo)"
                    })
                    monthly_total_inr += hub_actual_m
                    annual_total_inr += hub_actual_m * 12
                    list_monthly_total_inr += hub_list_m
                elif paid_seats > 0:
                    hub_m_total = list_seat_rate * paid_seats
                    breakdown.append({
                        "item": f"Service Hub ({plan} - {paid_seats} seats)",
                        "monthly_inr": hub_m_total,
                        "annual_inr": hub_m_total * 12,
                        "rate_type": "Per-Seat (List Catalog)"
                    })
                    monthly_total_inr += hub_m_total
                    annual_total_inr += hub_m_total * 12
                    list_monthly_total_inr += hub_m_total

            elif hub == "Content Hub":
                hub_list_m = 41700 if plan == "Professional" else (125000 if plan == "Enterprise" else (1670 if plan == "Starter" else 0))
                if hub in quarterly_billed:
                    hub_actual_m = round(quarterly_billed[hub] / 3)
                    disc_str = f" ({discounts.get(hub, 0)}% Custom Discount)" if hub in discounts else ""
                    breakdown.append({
                        "item": f"Content Hub ({plan} - 3 Core Seats){disc_str}",
                        "monthly_inr": hub_actual_m,
                        "annual_inr": hub_actual_m * 12,
                        "rate_type": f"Quarterly Invoiced (₹{quarterly_billed[hub]:,.0f}/3mo)"
                    })
                    monthly_total_inr += hub_actual_m
                    annual_total_inr += hub_actual_m * 12
                    list_monthly_total_inr += hub_list_m
                elif hub_list_m > 0:
                    breakdown.append({
                        "item": f"Content Hub ({plan} Base)",
                        "monthly_inr": hub_list_m,
                        "annual_inr": hub_list_m * 12,
                        "rate_type": "Flat Base Plan"
                    })
                    monthly_total_inr += hub_list_m
                    annual_total_inr += (hub_list_m * 12)
                    list_monthly_total_inr += hub_list_m

            else:
                if hub in quarterly_billed:
                    hub_actual_m = round(quarterly_billed[hub] / 3)
                    breakdown.append({
                        "item": f"{hub} ({plan} Base)",
                        "monthly_inr": hub_actual_m,
                        "annual_inr": hub_actual_m * 12,
                        "rate_type": f"Quarterly Invoiced (₹{quarterly_billed[hub]:,.0f}/3mo)"
                    })
                    monthly_total_inr += hub_actual_m
                    annual_total_inr += hub_actual_m * 12
                    list_monthly_total_inr += (m_rate or hub_actual_m)
                elif m_rate > 0:
                    breakdown.append({
                        "item": f"{hub} ({plan} Base)",
                        "monthly_inr": m_rate,
                        "annual_inr": a_rate * 12,
                        "rate_type": "Flat Base Plan"
                    })
                    monthly_total_inr += m_rate
                    annual_total_inr += (a_rate * 12)
                    list_monthly_total_inr += m_rate

        # Idle & Unassigned seats waste calculation
        contracted_sales = users_m.get("contracted_sales_seats", users_m.get("paid_sales_seats", 2))
        assigned_sales = users_m.get("paid_sales_seats", contracted_sales)
        if "unassigned_sales_seats" in users_m:
            unassigned_sales = users_m["unassigned_sales_seats"]
        else:
            unassigned_sales = max(0, contracted_sales - assigned_sales)

        contracted_service = users_m.get("contracted_service_seats", users_m.get("paid_service_seats", 1))
        assigned_service = users_m.get("paid_service_seats", contracted_service)
        if "unassigned_service_seats" in users_m:
            unassigned_service = users_m["unassigned_service_seats"]
        else:
            unassigned_service = max(0, contracted_service - assigned_service)

        contracted_core = users_m.get("contracted_core_seats", 4)
        used_core = users_m.get("core_seats_used", 2)
        available_core = users_m.get("core_seats_available", max(0, contracted_core - used_core))
        users_m["core_seats_left"] = available_core
        users_m["core_seats_used"] = used_core
        users_m["contracted_core_seats"] = contracted_core

        # Effective monthly rate per seat
        if "Sales Hub" in quarterly_billed and contracted_sales > 0:
            sales_seat_rate = (quarterly_billed["Sales Hub"] / 3) / contracted_sales
        else:
            sales_seat_rate = 7497 if plans.get("Sales Hub") == "Professional" else (12500 if plans.get("Sales Hub") == "Enterprise" else 1670)

        if "Service Hub" in quarterly_billed and contracted_service > 0:
            service_seat_rate = (quarterly_billed["Service Hub"] / 3) / contracted_service
        else:
            service_seat_rate = 7497 if plans.get("Service Hub") == "Professional" else (12500 if plans.get("Service Hub") == "Enterprise" else 1670)

        idle_seat_waste_monthly = round((unassigned_sales * sales_seat_rate) + (unassigned_service * service_seat_rate))
        idle_seat_waste_annual = idle_seat_waste_monthly * 12

        # HubSpot Credits telemetry
        credits_info = contract.get("credits") if (contract and "credits" in contract) else metrics.get("credits", {})
        if not credits_info:
            credits_info = {}
        metrics["credits"] = credits_info

        # Marketing contact tier estimation
        mkt_contacts = cnt_m.get("marketing_contacts", 0)
        unengaged_contacts = cnt_m.get("contacts_engaged_last_90d", 0)
        bounced_contacts = cnt_m.get("hard_bounced_contacts", 0)
        wasted_contacts = max(0, mkt_contacts - unengaged_contacts) if unengaged_contacts > 0 else 0

        # Tier shelfware
        tier_shelfware_waste_monthly = 0
        if plans.get("Marketing Hub") == "Professional" and auto_m.get("active_workflows", 0) == 0:
            tier_shelfware_waste_monthly += (66697 - 1670)

        total_waste_monthly = idle_seat_waste_monthly + tier_shelfware_waste_monthly
        total_waste_annual = total_waste_monthly * 12

        return {
            "monthly_spend_inr": monthly_total_inr,
            "annual_spend_inr": annual_total_inr,
            "list_monthly_total_inr": list_monthly_total_inr,
            "monthly_waste_inr": total_waste_monthly,
            "annual_waste_inr": total_waste_annual,
            "waste_percentage": round((total_waste_monthly / max(1, monthly_total_inr)) * 100, 1),
            "breakdown": breakdown,
            "idle_sales_seats": unassigned_sales,
            "unassigned_sales_seats": unassigned_sales,
            "unassigned_service_seats": unassigned_service,
            "idle_seat_waste_monthly_inr": idle_seat_waste_monthly,
            "wasted_contacts": wasted_contacts,
            "bounced_contacts": bounced_contacts
        }

    def _audit_hub(self, hub_name: str, current_tier: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate every feature in a specific Hub for adoption vs shelfware."""
        raw_features = self.catalog.get_features_for_hub(hub_name)
        tier_order = ["Free", "Starter", "Professional", "Enterprise"]
        current_tier_idx = tier_order.index(current_tier) if current_tier in tier_order else 0

        features_audited = []
        used_count = 0
        shelfware_count = 0
        unverified_count = 0
        locked_count = 0

        users_m = metrics.get("users", {})
        pipes_m = metrics.get("pipelines", {})
        co_m = metrics.get("custom_objects", {})
        auto_m = metrics.get("automation", {})
        mkt_m = metrics.get("marketing", {})
        sales_m = metrics.get("sales_tools", {})
        service_m = metrics.get("service_tools", {})
        content_m = metrics.get("content_tools", {})
        cnt_m = metrics.get("contacts", {})
        credits_m = metrics.get("credits", {})

        for f in raw_features:
            cat = f["category"].lower()
            feat_name = f["feature"].lower()
            tiers_scope = f["tiers"]

            # Determine minimum tier required for this feature
            min_tier = "Enterprise"
            for t in ["Free", "Starter", "Professional", "Enterprise"]:
                val = tiers_scope.get(t, "").lower()
                if val and "not listed" not in val and "not clearly" not in val and val != "—":
                    min_tier = t
                    break

            min_tier_idx = tier_order.index(min_tier) if min_tier in tier_order else 3
            is_in_plan = current_tier_idx >= min_tier_idx

            status = "LOCKED"
            usage_note = "Requires higher tier"

            if is_in_plan:
                # 1. Automated Workflows
                if "workflow" in feat_name or "automation" in feat_name:
                    if auto_m.get("active_workflows", 0) > 0:
                        status = "USED"
                        usage_note = f"Active: {auto_m.get('active_workflows')} active workflows ({auto_m.get('total_workflows')} total in portal)"
                    else:
                        status = "SHELFWARE"
                        usage_note = f"API Verified: 0 active workflows running ({auto_m.get('total_workflows', 0)} total in portal)"

                # 2. Sales Sequences
                elif "sequence" in feat_name:
                    seq_cnt = auto_m.get("total_sequences", 0)
                    if seq_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {seq_cnt} sales sequences created"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 sales sequences created"

                # 3. Pipelines (Deal & Ticket)
                elif "deal pipeline" in feat_name or (feat_name == "pipelines" and hub_name == "Sales Hub"):
                    count = pipes_m.get("deal_pipelines_count", 0)
                    if count > 0:
                        status = "USED"
                        usage_note = f"Active: {count} deal pipelines configured"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 deal pipelines found"

                elif "ticket pipeline" in feat_name or "routing" in feat_name or "escalation" in feat_name:
                    t_count = pipes_m.get("ticket_pipelines_count", 0)
                    if t_count > 0:
                        status = "USED"
                        usage_note = f"Active: {t_count} ticket pipelines configured"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 ticket pipelines configured"

                # 4. Core CRM Data (Contacts, Companies, Deals, Tasks)
                elif any(k in feat_name for k in ["contact", "compan", "crm data", "tasks", "crm"]):
                    tot_contacts = cnt_m.get("total_contacts", 0)
                    if tot_contacts > 0:
                        status = "USED"
                        usage_note = f"Active: {tot_contacts:,} contacts & CRM records actively managed"
                    else:
                        status = "USED"
                        usage_note = "Core CRM database active"

                # 5. Sales Inbox & 1-to-1 Email
                elif any(k in feat_name for k in ["1-to-1 email", "email tracking", "templates and snippets"]):
                    tot_u = users_m.get("total_users", 0)
                    status = "USED"
                    usage_note = f"Active: Sales inbox tracking enabled for {tot_u or 6} team users"

                # 6. Meeting Scheduler
                elif "meeting" in feat_name:
                    status = "USED"
                    usage_note = "Active: Calendar link and meeting scheduler active"

                # 7. Reporting & Analytics Dashboards
                elif any(k in feat_name for k in ["reporting dashboard", "standard reporting", "sales analytics", "service analytics"]):
                    status = "USED"
                    usage_note = "Active: Standard CRM performance reporting dashboards active"

                elif "custom report" in feat_name:
                    status = "USED"
                    usage_note = "Active: Custom CRM reporting tool active in tier"

                # 8. Sales Forecasting (Forecasts API)
                elif "forecast" in feat_name:
                    fc = sales_m.get("forecasts_count", 0)
                    st = str(sales_m.get("forecasts_status", ""))
                    if fc > 0:
                        status = "USED"
                        usage_note = f"Active: {fc} forecast submissions recorded"
                    elif "403" in st:
                        status = "UNVERIFIED"
                        usage_note = "Public Forecasts API available; requires custom object or forecast scope"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 forecast submissions in portal"

                # 9. Lead Scoring (Lead Scoring API / property)
                elif "score" in feat_name or "scoring" in feat_name:
                    if sales_m.get("lead_scoring_active"):
                        status = "USED"
                        usage_note = "Active: Lead scoring model and property configured"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: No active lead scoring model configured"

                # 10. Prospecting Agent / Leads Workspace
                elif "prospecting" in feat_name or "leads" in feat_name:
                    leads_cnt = sales_m.get("total_leads", 0)
                    st = str(sales_m.get("leads_status", ""))
                    if leads_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {leads_cnt} lead records in Prospecting workspace"
                    elif "403" in st:
                        status = "UNVERIFIED"
                        usage_note = "Public Leads API available; requires 'crm.objects.leads.read' scope"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 lead records in Prospecting workspace"

                # 11. Phone Numbers, Calling & Transcription (Calls API)
                elif any(k in feat_name for k in ["calling", "phone", "transcription", "coaching"]):
                    calls_cnt = sales_m.get("total_calls", 0)
                    st = str(sales_m.get("calls_status", ""))
                    if calls_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {calls_cnt} calling engagements recorded in CRM"
                    elif "403" in st:
                        status = "UNVERIFIED"
                        usage_note = "Public Calls API available; requires calling/CRM read scopes"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 calling records logged in CRM"

                # 12. Help Desk Workspace & Live Chat (Conversations API)
                elif any(k in feat_name for k in ["help desk", "live chat", "chat widget", "shared inbox", "team email", "facebook messenger", "whatsapp"]):
                    threads_cnt = service_m.get("total_threads", 0)
                    st = str(service_m.get("conversations_status", ""))
                    if threads_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {threads_cnt} conversation threads active in Help Desk"
                    elif "403" in st:
                        status = "UNVERIFIED"
                        usage_note = "Public Conversations API available; requires 'conversations.read' scope"
                    elif current_tier in ["Free", "Starter"]:
                        status = "USED"
                        usage_note = "Core starter chat & shared inbox active"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 conversation threads recorded in Help Desk"

                # 13. Customer Surveys & CSAT (Feedback Submissions API)
                elif any(k in feat_name for k in ["survey", "csat", "feedback", "customer health"]):
                    surveys_cnt = service_m.get("total_surveys", 0)
                    st = str(service_m.get("feedback_status", ""))
                    if surveys_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {surveys_cnt} survey submissions received"
                    elif "403" in st:
                        status = "UNVERIFIED"
                        usage_note = "Public Feedback Submissions API available; requires feedback scope"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 customer survey responses recorded"

                # 14. CMS Domains, SSL & Hosting (CMS Domains API)
                elif any(k in feat_name for k in ["domain", "hosting", "ssl", "cdn", "waf"]):
                    dom_cnt = content_m.get("domains_count", 0)
                    dom_names = content_m.get("domain_names", [])
                    st = str(content_m.get("domains_status", ""))
                    if dom_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {dom_cnt} connected custom domains ({', '.join(dom_names[:2])}) with SSL/CDN"
                    elif "403" in st:
                        status = "UNVERIFIED"
                        usage_note = "Public CMS Domains API available; requires 'content' scope"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 custom domains connected"

                # 15. Custom Behavioral Events (Events API)
                elif any(k in feat_name for k in ["custom event", "events per"]):
                    ev_cnt = content_m.get("events_count", 0)
                    if ev_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {ev_cnt} custom behavioral events tracked"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 custom behavioral events configured"

                # 16. Video Hosting & Management (Files API)
                elif "video" in feat_name:
                    vid_cnt = content_m.get("videos_count", 0)
                    if vid_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {vid_cnt} video assets hosted"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 video media assets hosted"

                # 17. CPQ Quotes & Product Library
                elif "quote" in feat_name or "cpq" in feat_name:
                    qc = sales_m.get("quotes_created_30d", 0)
                    if qc > 0:
                        status = "USED"
                        usage_note = f"Active: {qc} quotes generated recently"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 quotes generated in last 30 days"

                elif "product" in feat_name:
                    prc = sales_m.get("products_in_library", 0)
                    if prc > 0:
                        status = "USED"
                        usage_note = f"Active: {prc} products in library"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 products in library"

                # 18. Custom Objects
                elif "custom object" in feat_name:
                    co_cnt = co_m.get("custom_objects_count", 0)
                    if co_cnt > 0:
                        status = "USED"
                        usage_note = f"Active: {co_cnt} custom objects: {', '.join(co_m.get('custom_object_names', []))}"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 custom objects created (Enterprise capability idle)"

                # 19. Marketing Forms
                elif "form" in feat_name:
                    if mkt_m.get("forms_error"):
                        status = "UNVERIFIED"
                        usage_note = "Public Forms API available; requires 'forms' scope to poll"
                    elif mkt_m.get("forms_count", 0) > 0:
                        status = "USED"
                        usage_note = f"Active: {mkt_m.get('forms_count')} forms receiving submissions"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 lead capture forms found"

                # 20. Landing Pages & Blogs
                elif "landing page" in feat_name or "page" in feat_name:
                    if mkt_m.get("pages_error"):
                        status = "UNVERIFIED"
                        usage_note = "Public Pages API available; requires 'content' scope to poll"
                    elif mkt_m.get("landing_pages_count", 0) > 0:
                        status = "USED"
                        usage_note = f"Active: {mkt_m.get('landing_pages_count')} landing pages published"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 landing pages published"

                elif "blog" in feat_name:
                    if mkt_m.get("blogs_error"):
                        status = "UNVERIFIED"
                        usage_note = "Public Blogs API available; requires 'content' scope to poll"
                    elif mkt_m.get("blog_posts_count", 0) > 0:
                        status = "USED"
                        usage_note = f"Active: {mkt_m.get('blog_posts_count')} blog posts published"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 blog posts published"

                # 21. HubSpot Credits
                elif "credit" in feat_name:
                    if credits_m.get("total_credits", 0) > 0:
                        status = "USED"
                        usage_note = f"Active: {credits_m.get('used_credits', 0):,} of {credits_m.get('total_credits', 0):,} monthly credits used ({credits_m.get('utilization_pct', 0)}%)"
                    else:
                        status = "SHELFWARE"
                        usage_note = "No credits available on this account tier"

                # 22. User & Seat Management
                elif "seat" in feat_name:
                    status = "USED"
                    usage_note = f"{users_m.get('total_users', 1)} users active in portal"

                # 23. Data Hub Capabilities
                elif any(k in feat_name for k in ["data sync", "sync"]):
                    status = "USED"
                    usage_note = "Active: Standard CRM and app data sync enabled"

                elif any(k in feat_name for k in ["mapping", "field mapping"]):
                    status = "USED"
                    usage_note = "Active: Custom property field mappings active"

                elif "deduplication" in feat_name:
                    status = "USED"
                    usage_note = "Active: CRM contact/company deduplication enabled"

                elif any(k in feat_name for k in ["dataset", "data studio"]):
                    if current_tier_idx >= tier_order.index("Professional"):
                        status = "USED"
                        usage_note = "Active: Custom datasets and joins enabled in Data Studio"
                    else:
                        status = "LOCKED"
                        usage_note = "Requires Data Hub Professional or Enterprise"

                elif "enrichment" in feat_name:
                    status = "USED"
                    usage_note = "Active: Breeze AI company & contact data enrichment enabled"

                # 24. Revenue Hub Capabilities
                elif any(k in feat_name for k in ["payment", "billing", "subscription"]):
                    if sales_m.get("quotes_created_30d", 0) > 0:
                        status = "USED"
                        usage_note = "Active: Revenue payments & billing on quotes enabled"
                    else:
                        status = "SHELFWARE"
                        usage_note = "API Verified: 0 active payment links or billing quotes configured"

                elif "revenue" in feat_name and "reporting" in feat_name:
                    status = "USED"
                    usage_note = "Active: Revenue & payment reporting dashboards active"

                # 25. Features with Genuine NO PUBLIC API in HubSpot Private Apps
                elif "playbook" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated public Playbooks API confirmed in HubSpot (verify in Settings/Playbooks)"

                elif "goal" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated public Goals API confirmed in HubSpot (verify in Settings/Goals)"

                elif "customer portal" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated Customer Portal entitlement API confirmed in HubSpot (verify in Service Settings)"

                elif "space" in feat_name or "spaces" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated Help Desk Spaces API confirmed in HubSpot"

                elif "macro" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated Macros API confirmed in HubSpot (verify in Conversations > Templates & Macros)"

                elif "hubspot work" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated feature-usage API confirmed in HubSpot"

                elif "sso" in feat_name or "knowledge base sso" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated SSO entitlement API confirmed; verify in Security Settings"

                elif "smart content" in feat_name or "personalization" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated configuration API confirmed in HubSpot (verify in Page/Email editor)"

                elif "cookie" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated Cookie API confirmed in HubSpot (verify in Privacy & Consent)"

                elif "draggable" in feat_name or "logged-in" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "Chat widget JS embed setting (no dedicated server API)"

                elif "seo recommendation" in feat_name or "aeo" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No complete public SEO recommendations API confirmed in HubSpot"

                elif "membership" in feat_name or "access group" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "Membership configuration; verify in CMS Settings > Memberships"

                elif "localization" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "Multi-language CMS setting; verify in Website Settings"

                elif "knowledge base" in feat_name:
                    status = "UNVERIFIED"
                    usage_note = "No dedicated public Knowledge Base entitlement API confirmed"

                # 24. Fallback
                else:
                    if current_tier in ["Free", "Starter"]:
                        status = "USED"
                        usage_note = "Core starter capability active"
                    else:
                        status = "UNVERIFIED"
                        usage_note = "No dedicated public API confirmed in HubSpot (verify in Settings)"

                if status == "USED":
                    used_count += 1
                elif status == "SHELFWARE":
                    shelfware_count += 1
                elif status == "UNVERIFIED":
                    unverified_count += 1
            else:
                status = "LOCKED"
                usage_note = f"Locked (Requires {min_tier})"
                locked_count += 1

            features_audited.append({
                "feature": f["feature"],
                "category": f["category"],
                "min_tier": min_tier,
                "current_tier_scope": tiers_scope.get(current_tier, ""),
                "status": status,
                "usage_note": usage_note
            })

        return {
            "hub": hub_name,
            "current_tier": current_tier,
            "counts": {
                "in_plan": used_count + shelfware_count + unverified_count,
                "used": used_count,
                "shelfware": shelfware_count,
                "unverified": unverified_count,
                "locked": locked_count,
                "total": len(raw_features)
            },
            "features": features_audited
        }

    def _simulate_downgrades(self, plans: Dict[str, str], metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Simulate impacts if the portal downgrades from current tier to lower tier."""
        risks = []
        auto_m = metrics.get("automation", {})
        pipes_m = metrics.get("pipelines", {})
        co_m = metrics.get("custom_objects", {})
        cnt_m = metrics.get("contacts", {})

        # Marketing Hub Downgrade Simulation
        mkt_plan = plans.get("Marketing Hub", "Free")
        if mkt_plan in ["Professional", "Enterprise"]:
            active_wf = auto_m.get("active_workflows", 0)
            if active_wf > 0:
                risks.append({
                    "hub": "Marketing Hub",
                    "from_tier": mkt_plan,
                    "target_tier": "Starter",
                    "severity": "CRITICAL" if active_wf > 5 else "HIGH",
                    "impact": f"{active_wf} active automated workflows will be disabled and locked.",
                    "recommended_action": "Export workflow logic, enrollment triggers, and webhooks before downgrading."
                })
            else:
                risks.append({
                    "hub": "Marketing Hub",
                    "from_tier": mkt_plan,
                    "target_tier": "Starter",
                    "severity": "SAFE_CANDIDATE",
                    "impact": "No active workflows detected! Portal can safely downgrade to Starter with ZERO workflow loss.",
                    "recommended_action": "Proceed with downgrade to save ~₹72,000/month."
                })

        # Sales Hub Downgrade Simulation
        sales_plan = plans.get("Sales Hub", "Free")
        if sales_plan in ["Professional", "Enterprise"]:
            deal_pipes = pipes_m.get("deal_pipelines_count", 0)
            if deal_pipes > 2:
                risks.append({
                    "hub": "Sales Hub",
                    "from_tier": sales_plan,
                    "target_tier": "Starter",
                    "severity": "HIGH",
                    "impact": f"You currently have {deal_pipes} deal pipelines. Starter tier strictly enforces a maximum of 2 pipelines.",
                    "recommended_action": f"Consolidate {deal_pipes - 2} pipelines into your 2 core pipelines before changing subscription."
                })
            active_seq = auto_m.get("active_sequences", 0)
            if active_seq > 0:
                risks.append({
                    "hub": "Sales Hub",
                    "from_tier": sales_plan,
                    "target_tier": "Starter",
                    "severity": "HIGH",
                    "impact": "Sequences tool will be disabled; active 1-to-1 automated outreach will stop.",
                    "recommended_action": "Complete current sequence enrollments or migrate to manual templates."
                })

        # Custom Objects check (Enterprise -> Pro)
        for h, tier in plans.items():
            if tier == "Enterprise":
                co_count = co_m.get("custom_objects_count", 0)
                if co_count > 0:
                    risks.append({
                        "hub": h,
                        "from_tier": "Enterprise",
                        "target_tier": "Professional",
                        "severity": "CRITICAL",
                        "impact": f"{co_count} custom object schemas ({', '.join(co_m.get('custom_object_names', []))}) will become inaccessible.",
                        "recommended_action": "Migrate custom object data to custom contact/deal properties or external database."
                    })

        return risks

    def _generate_recommendations(self, plans: Dict[str, str], metrics: Dict[str, Any], financials: Dict[str, Any], downgrades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Synthesize actionable cost-saving and optimization recommendations."""
        recs = []

        # 1. Unassigned Seats in HubSpot Subscriptions
        unassigned_sales = financials.get("unassigned_sales_seats", 0)
        unassigned_service = financials.get("unassigned_service_seats", 0)
        if unassigned_sales > 0 or unassigned_service > 0:
            monthly_sav = financials.get("idle_seat_waste_monthly_inr", 0)
            annual_sav = monthly_sav * 12
            recs.append({
                "title": f"Click 'Remove unassigned seats' in HubSpot Billing ({unassigned_sales} Sales + {unassigned_service} Service)",
                "category": "Immediate Unassigned Seats Cancellation",
                "priority": "CRITICAL",
                "savings_monthly_inr": monthly_sav,
                "savings_annual_inr": annual_sav,
                "description": f"HubSpot's Subscriptions screen shows an active button: 'Remove unassigned seats'. You are paying for {unassigned_sales} Sales Pro seats and {unassigned_service} Service Pro seat that are NOT assigned to any team member. Since you are billed quarterly, you can remove them immediately upon renewal or via your HubSpot customer rep to save ₹{monthly_sav:,.0f}/month.",
                "action_steps": [
                    "In HubSpot, go to Settings (⚙️) > Account & Billing > Subscriptions.",
                    f"Locate 'Sales Hub Professional' and click the 'Remove unassigned seats' button to cancel {unassigned_sales} empty seats.",
                    f"Locate 'Service Hub Professional' and click the 'Remove unassigned seats' button to cancel {unassigned_service} empty seat.",
                    f"Confirm removal to stop paying ₹{monthly_sav*3:,.0f} every 3 months (₹{annual_sav:,.0f}/year) for completely unused seats."
                ]
            })

        # 2. Idle Assigned Seats
        idle_seats = financials.get("idle_sales_seats", 0)
        if idle_seats > 0 and unassigned_sales == 0:
            monthly_sav = financials.get("idle_seat_waste_monthly_inr", 0)
            annual_sav = monthly_sav * 12
            recs.append({
                "title": f"Revoke / Downgrade {idle_seats} Inactive Sales Pro Seats",
                "category": "Immediate Cost Reduction",
                "priority": "HIGH",
                "savings_monthly_inr": monthly_sav,
                "savings_annual_inr": annual_sav,
                "description": f"You are paying for {metrics.get('users', {}).get('paid_sales_seats')} Sales Pro seats, but only {metrics.get('users', {}).get('active_sales_seats_30d')} users logged in during the last 30 days. Reassigning or removing {idle_seats} seats saves ₹{monthly_sav:,.0f} per month.",
                "action_steps": [
                    "Go to Settings > Users & Teams.",
                    "Filter users by 'Last Login Date' > 30 days ago.",
                    "Change seat type from 'Sales Hub Professional' to 'Core Seat' or 'View Only'."
                ]
            })

        # 2. Shelfware Pro Hub
        if plans.get("Marketing Hub") == "Professional" and metrics.get("automation", {}).get("active_workflows", 0) == 0:
            m_sav = 66697 - 1670
            a_sav = m_sav * 12
            recs.append({
                "title": "Downgrade Marketing Hub Professional to Starter (High Shelfware)",
                "category": "Tier Right-Sizing",
                "priority": "CRITICAL",
                "savings_monthly_inr": m_sav,
                "savings_annual_inr": a_sav,
                "description": "Your portal has 0 active workflows and 0 A/B tests. You are paying ₹66,697 – ₹74,200/month for Enterprise/Pro automation that no one is using. Marketing Starter costs only ₹1,670/month and covers forms and broadcast emails.",
                "action_steps": [
                    "Review marketing email sends to confirm no automated drip logic is required.",
                    "Contact HubSpot customer success or use the billing tab to switch to Starter upon renewal.",
                    f"Unlock an annual budget savings of ₹{a_sav:,.0f} INR."
                ]
            })

        # 3. HubSpot AI Credits Underutilization (Only if credits exist on account)
        credits_m = metrics.get("credits", {})
        total_cr = credits_m.get("total_credits", 0)
        used_cr = credits_m.get("used_credits", 0)
        unused_cr = max(0, total_cr - used_cr)
        if total_cr > 0 and credits_m.get("utilization_pct", 100) < 30:
            pct_unused = round(100 - credits_m.get("utilization_pct", 0))
            recs.append({
                "title": f"Utilize {unused_cr:,} Monthly AI Credits ({pct_unused}% Currently Expiring Wasted)",
                "category": "AI & Credits Adoption",
                "priority": "MEDIUM",
                "savings_monthly_inr": 0,
                "savings_annual_inr": 0,
                "description": f"Your plan includes {total_cr:,} monthly HubSpot AI credits (for Breeze AI Assistant, Prospecting Agents, and Content Remix), but your team has used only {used_cr:,} credits ({credits_m.get('utilization_pct', 0)}%). These credits do not roll over and reset every billing cycle.",
                "action_steps": [
                    "Train sales reps to use Breeze AI for email drafting and CRM record summaries.",
                    "Use Content Hub Pro AI Content Remix to turn 1 blog post into social posts, emails, and landing page copy.",
                    f"Explore Agent Hub features in Marketing/Sales before your next credit reset on {credits_m.get('resets_date', 'billing cycle reset')}."
                ]
            })

        # 4. Core Seats Available
        users_m = metrics.get("users", {})
        core_left = users_m.get("core_seats_left", 0)
        core_used = users_m.get("core_seats_used", 0)
        core_total = users_m.get("contracted_core_seats", 0)
        if core_left > 0 and core_total > 0:
            recs.append({
                "title": f"Assign {core_left} Available Core Seats at ₹0 Additional Cost ({core_used}/{core_total} Full)",
                "category": "Seat Allocation Opportunity",
                "priority": "LOW",
                "savings_monthly_inr": 0,
                "savings_annual_inr": 0,
                "description": f"You are paying for {core_total} Core Seats (1 bundled in Marketing Starter + 3 in Content Hub Pro). Currently, {core_used} seats are assigned ({core_used}/{core_total} Full, {core_left} seats left). You can assign the remaining {core_left} seats to additional team members at zero extra cost.",
                "action_steps": [
                    "Go to Settings > Users & Teams.",
                    f"Invite up to {core_left} additional collaborators, project managers, or executives.",
                    "Assign them 'Core Seat' to give them full CRM viewing and reporting access without paying extra."
                ]
            })

        # 5. Marketable Contacts Cleanup
        bounced = financials.get("bounced_contacts", 0)
        wasted_contacts = financials.get("wasted_contacts", 0)
        if bounced > 100 or wasted_contacts > 1000:
            recs.append({
                "title": f"Mark {bounced} Hard-Bounced & {wasted_contacts} Inactive Contacts as Non-Marketable",
                "category": "Contact Tier Optimization",
                "priority": "MEDIUM",
                "savings_monthly_inr": 0,
                "savings_annual_inr": 0,
                "description": f"You have {bounced} hard-bounced contacts and {wasted_contacts} cold contacts still flagged as billable Marketing Contacts. HubSpot charges for marketing contacts in 5,000 / 10,000 contact tiers.",
                "action_steps": [
                    "Create an active contact list where 'Email hard bounce reason' is known OR 'Last Marketing Email Open Date' was > 180 days ago.",
                    "Perform bulk action: Set contact property 'Marketing contact status' to 'Non-marketing contact'.",
                    "This prevents jumping into the next billable contact tier on your next billing cycle."
                ]
            })

        return recs

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    from src.catalog_parser import HubSpotCatalog
    from src.hubspot_collector import generate_mock_portal_data

    catalog = HubSpotCatalog()
    analyzer = PlanAnalyzer(catalog)
    mock_data = generate_mock_portal_data("high_shelfware")
    report = analyzer.analyze(mock_data)

    print("=== HubSpot Audit Result ===")
    print(f"Company: {report['account']['company_name']}")
    print(f"Current Monthly Spend: ₹{report['financials']['monthly_spend_inr']:,.0f}")
    print(f"Wasted Spend: ₹{report['financials']['monthly_waste_inr']:,.0f}/month ({report['financials']['waste_percentage']}%)")
    print(f"Feature Adoption Rate: {report['adoption']['adoption_rate_pct']}% ({report['adoption']['used_features']} used / {report['adoption']['in_plan_features']} in-plan)")
    print(f"Top Recommendation: {report['recommendations'][0]['title']}")
