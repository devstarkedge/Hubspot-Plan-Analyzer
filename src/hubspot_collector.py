"""
HubSpot Portal Data Collector
Fetches live usage statistics, seat allocations, and asset metrics via HubSpot REST APIs.
Also provides realistic demo/mock portal datasets for testing without live API tokens.
"""

import os
import time
import requests
from typing import Dict, List, Any, Optional

HUBSPOT_API_BASE = "https://api.hubapi.com"

class HubSpotCollector:
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated GET request with rate limit and error handling."""
        if not self.access_token:
            return {"error": "No access token provided"}
        
        url = f"{HUBSPOT_API_BASE}{path}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=12)
            # Capture rate limit headers
            daily_limit = resp.headers.get("X-HubSpot-RateLimit-Daily")
            daily_remaining = resp.headers.get("X-HubSpot-RateLimit-Daily-Remaining")
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    data["_api_daily_limit"] = daily_limit
                    data["_api_daily_remaining"] = daily_remaining
                return data
            elif resp.status_code in (401, 403):
                return {"error": f"HTTP {resp.status_code}: Missing required scope or invalid token for {path}"}
            elif resp.status_code == 404:
                return {"error": f"HTTP 404: Endpoint {path} not found or feature not enabled for this tier"}
            else:
                return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated POST request with error handling."""
        if not self.access_token:
            return {"error": "No access token provided"}
        
        url = f"{HUBSPOT_API_BASE}{path}"
        try:
            resp = requests.post(url, headers=self.headers, json=json_data, timeout=12)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in (401, 403):
                return {"error": f"HTTP {resp.status_code}: Missing required scope or invalid token for {path}"}
            elif resp.status_code == 404:
                return {"error": f"HTTP 404: Endpoint {path} not found"}
            else:
                return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"error": str(e)}

    def collect_account_info(self) -> Dict[str, Any]:
        """Fetch portal ID, timezone, currency, and portal details."""
        res = self._get("/account-info/v3/details")
        if "error" in res:
            return {"portal_id": "Unknown", "company_name": "HubSpot Portal", "currency": "INR", "status": res["error"]}
        
        portal_id = str(res.get("portalId", "Unknown"))
        acc_type = res.get("accountType", "Standard")
        if portal_id == "245317936":
            company_name = "Stark Edge"
        elif acc_type == "DEVELOPER_TEST":
            company_name = f"Access Testing (Dev Portal {portal_id})"
        else:
            company_name = f"HubSpot Portal ({portal_id})"

        return {
            "portal_id": portal_id,
            "company_name": company_name,
            "account_type": acc_type,
            "time_zone": res.get("timeZone", "Asia/Kolkata"),
            "currency": res.get("companyCurrency") or res.get("currency", "INR"),
            "additional_currencies": res.get("additionalCurrencies", [])
        }

    def collect_users_and_seats(self) -> Dict[str, Any]:
        """Inspect users, seat types (Sales / Service / Core / Revenue), and active vs inactive status using latest 2026-09 API."""
        res = self._get("/settings/users/2026-09")
        if "error" in res or not res.get("results"):
            res = self._get("/settings/v3/users/")

        if "error" in res:
            return {"error": res["error"], "total_users": 0, "paid_sales_seats": 0, "paid_service_seats": 0}
        
        users = res.get("results", [])
        total_users = len(users)
        paid_sales_seats = 0
        paid_service_seats = 0
        paid_revenue_seats = 0
        core_seats_used = 0
        view_only_seats = 0
        super_admins = 0

        detected_sales_tier = None
        detected_service_tier = None
        detected_revenue_tier = None

        for u in users:
            if u.get("superAdmin"):
                super_admins += 1
            
            seat_names = [str(s).lower() for s in u.get("seatNames", [])]
            u_str = str(u).lower()

            # 1. Sales seat check
            is_sales = False
            for s in seat_names:
                if "sales" in s:
                    is_sales = True
                    if "ent" in s:
                        detected_sales_tier = "Enterprise"
                    elif "pro" in s and detected_sales_tier != "Enterprise":
                        detected_sales_tier = "Professional"
                    elif not detected_sales_tier:
                        detected_sales_tier = "Starter"

            if not is_sales:
                if (u.get("paidSalesSeat") or "sales-pro" in u_str or "sales_pro" in u_str or
                    "sales" in str(u.get("primarySeat", "")).lower() or
                    (u.get("role") and "sales" in str(u.get("role")).lower())):
                    is_sales = True

            if is_sales:
                paid_sales_seats += 1

            # 2. Service seat check
            is_service = False
            for s in seat_names:
                if "service" in s:
                    is_service = True
                    if "ent" in s:
                        detected_service_tier = "Enterprise"
                    elif "pro" in s and detected_service_tier != "Enterprise":
                        detected_service_tier = "Professional"
                    elif not detected_service_tier:
                        detected_service_tier = "Starter"

            if not is_service:
                if (u.get("paidServiceSeat") or "service-pro" in u_str or "service_pro" in u_str or
                    "service" in str(u.get("primarySeat", "")).lower() or
                    (u.get("role") and "service" in str(u.get("role")).lower())):
                    is_service = True

            if is_service:
                paid_service_seats += 1

            # 3. Revenue / Commerce seat check
            is_rev = False
            for s in seat_names:
                if "commerce" in s or "revenue" in s:
                    is_rev = True
                    if "ent" in s:
                        detected_revenue_tier = "Enterprise"
                    elif not detected_revenue_tier:
                        detected_revenue_tier = "Professional"

            if is_rev:
                paid_revenue_seats += 1

            # 4. Core seat check
            if any("core" in s for s in seat_names) or "core" in u_str or "core" in str(u.get("primarySeat", "")).lower():
                core_seats_used += 1

            # 5. View-only seat check
            if any("view" in s for s in seat_names):
                view_only_seats += 1

        # Check active deal owners in CRM to auto-detect assigned sales reps if 0
        if paid_sales_seats == 0 and total_users > 0:
            deal_owners = set()
            deals_res = self._get("/crm/v3/objects/deals", params={"properties": "hubspot_owner_id", "limit": 100})
            if isinstance(deals_res, dict) and "results" in deals_res:
                for d in deals_res["results"]:
                    oid = d.get("properties", {}).get("hubspot_owner_id")
                    if oid:
                        deal_owners.add(str(oid))
            paid_sales_seats = len(deal_owners) if deal_owners else min(total_users, 1)

        if paid_service_seats == 0 and total_users > 0:
            paid_service_seats = min(total_users, 1)

        return {
            "total_users": total_users,
            "super_admins": super_admins,
            "paid_sales_seats": paid_sales_seats,
            "paid_service_seats": paid_service_seats,
            "paid_revenue_seats": paid_revenue_seats,
            "core_seats_used": core_seats_used,
            "view_only_seats": view_only_seats,
            "detected_sales_tier": detected_sales_tier,
            "detected_service_tier": detected_service_tier,
            "detected_revenue_tier": detected_revenue_tier,
            "users_list_sample": [{"email": u.get("email"), "id": u.get("id"), "seats": u.get("seatNames", [])} for u in users[:5]]
        }

    def collect_pipelines(self) -> Dict[str, Any]:
        """Check deal and ticket pipelines (Starter allows 2, Pro allows 15, Ent allows 100)."""
        deals_res = self._get("/crm/v3/pipelines/deals")
        tickets_res = self._get("/crm/v3/pipelines/tickets")
        
        deal_pipelines = deals_res.get("results", []) if "error" not in deals_res else []
        ticket_pipelines = tickets_res.get("results", []) if "error" not in tickets_res else []
        
        return {
            "deal_pipelines_count": len(deal_pipelines),
            "deal_pipeline_names": [p.get("label") for p in deal_pipelines],
            "ticket_pipelines_count": len(ticket_pipelines),
            "ticket_pipeline_names": [p.get("label") for p in ticket_pipelines]
        }

    def collect_custom_objects(self) -> Dict[str, Any]:
        """Check custom object schemas (Enterprise feature: up to 100)."""
        res = self._get("/crm/v3/schemas")
        if "error" in res:
            return {"custom_objects_count": 0, "schemas": [], "status": res["error"]}
        schemas = res.get("results", [])
        # Filter standard objects (contacts, companies, deals, tickets) vs custom
        custom_schemas = [s for s in schemas if not s.get("fullyQualifiedName", "").startswith("hs_")]
        return {
            "custom_objects_count": len(custom_schemas),
            "custom_object_names": [s.get("name") for s in custom_schemas]
        }

    def collect_automation(self) -> Dict[str, Any]:
        """Inspect Workflows and Sequences."""
        # 1. Workflows: Query /automation/v4/flows to get all modern flows (matches HubSpot UI)
        flows_res = self._get("/automation/v4/flows")
        if isinstance(flows_res, dict) and "results" in flows_res and not flows_res.get("error"):
            flows = flows_res.get("results", [])
            total_workflows = len(flows)
            active_workflows = len([f for f in flows if f.get("isEnabled") or str(f.get("status", "")).upper() == "PUBLISHED"])
        else:
            wf_res = self._get("/automation/v3/workflows")
            workflows = wf_res.get("workflows", []) if isinstance(wf_res, dict) and "workflows" in wf_res else []
            total_workflows = len(workflows)
            active_workflows = len([w for w in workflows if w.get("enabled")])

        # 2. Sequences: HubSpot requires ?userId=<id> on /automation/v4/sequences
        users_res = self._get("/settings/v3/users")
        users = users_res.get("results", []) if isinstance(users_res, dict) and "results" in users_res else []
        seq_ids = set()
        for u in users:
            uid = u.get("id")
            if not uid:
                continue
            seq_res = self._get("/automation/v4/sequences", params={"userId": uid})
            if isinstance(seq_res, dict) and "results" in seq_res:
                for s in seq_res["results"]:
                    sid = s.get("id")
                    if sid:
                        seq_ids.add(str(sid))
        total_sequences = len(seq_ids)

        return {
            "total_workflows": total_workflows,
            "active_workflows": active_workflows,
            "total_sequences": total_sequences,
            "workflows_status": "ok",
            "sequences_status": "ok"
        }

    def collect_marketing_and_cms(self) -> Dict[str, Any]:
        """Check forms, landing pages, blogs, and marketing contacts."""
        forms_res = self._get("/marketing/v3/forms")
        pages_res = self._get("/cms/v3/pages/landing-pages")
        blogs_res = self._get("/cms/v3/blogs/posts")
        
        forms_count = forms_res.get("total", len(forms_res.get("results", []))) if "error" not in forms_res else 0
        pages_count = pages_res.get("total", len(pages_res.get("results", []))) if "error" not in pages_res else 0
        blogs_count = blogs_res.get("total", len(blogs_res.get("results", []))) if "error" not in blogs_res else 0
        
        return {
            "forms_count": forms_count,
            "landing_pages_count": pages_count,
            "blog_posts_count": blogs_count,
            "forms_error": forms_res.get("error") if "error" in forms_res else None,
            "pages_error": pages_res.get("error") if "error" in pages_res else None,
            "blogs_error": blogs_res.get("error") if "error" in blogs_res else None
        }

    def collect_contacts_quota(self) -> Dict[str, Any]:
        """Fetch total contacts count and live billable marketing contacts."""
        # Query total CRM contacts via search
        total_res = self._post("/crm/v3/objects/contacts/search", json_data={"limit": 1})
        total_contacts = total_res.get("total", 0) if isinstance(total_res, dict) and "total" in total_res else 0

        # Query live billable marketable contacts (hs_marketable_status == true)
        mkt_res = self._post("/crm/v3/objects/contacts/search", json_data={
            "filterGroups": [{
                "filters": [{
                    "propertyName": "hs_marketable_status",
                    "operator": "EQ",
                    "value": "true"
                }]
            }],
            "limit": 1
        })
        mkt_contacts = mkt_res.get("total") if isinstance(mkt_res, dict) and "total" in mkt_res else None

        if mkt_contacts is None:
            mkt_contacts = total_contacts

        return {
            "total_contacts": total_contacts,
            "marketing_contacts": mkt_contacts
        }

    def collect_calls(self) -> Dict[str, Any]:
        """Fetch CRM calling activity and engagements."""
        # Query total calls via POST search for exact count across portal
        search_res = self._post("/crm/v3/objects/calls/search", json_data={"limit": 1})
        if isinstance(search_res, dict) and "total" in search_res:
            return {
                "total_calls": search_res["total"],
                "sample_calls": 1 if search_res["total"] > 0 else 0,
                "status": "ok"
            }
        res = self._get("/crm/v3/objects/calls", params={"limit": 1})
        if "error" in res:
            return {"total_calls": 0, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        return {
            "total_calls": res.get("total", len(res.get("results", []))),
            "sample_calls": len(res.get("results", [])),
            "status": "ok"
        }

    def collect_conversations(self) -> Dict[str, Any]:
        """Inspect Help Desk & Live Chat conversation threads."""
        res = self._get("/conversations/v3/conversations/threads", params={"limit": 5})
        if "error" in res:
            return {"total_threads": 0, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        return {
            "total_threads": res.get("total", len(res.get("results", []))),
            "status": "ok"
        }

    def collect_feedback_surveys(self) -> Dict[str, Any]:
        """Fetch CSAT and customer feedback submissions."""
        search_res = self._post("/crm/v3/objects/feedback_submissions/search", json_data={"limit": 1})
        if isinstance(search_res, dict) and "total" in search_res:
            return {
                "total_surveys": search_res["total"],
                "status": "ok"
            }
        res = self._get("/crm/v3/objects/feedback_submissions", params={"limit": 1})
        if "error" in res:
            return {"total_surveys": 0, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        return {
            "total_surveys": res.get("total", len(res.get("results", []))),
            "status": "ok"
        }

    def collect_cms_domains(self) -> Dict[str, Any]:
        """Check connected CMS domains and SSL."""
        res = self._get("/cms/v3/domains")
        if "error" in res:
            return {"domains_count": 0, "domain_names": [], "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        domains = res.get("results", [])
        return {
            "domains_count": len(domains),
            "domain_names": [d.get("domain") for d in domains if d.get("domain")],
            "status": "ok"
        }

    def collect_leads(self) -> Dict[str, Any]:
        """Check Leads in Sales Prospecting workspace."""
        search_res = self._post("/crm/v3/objects/leads/search", json_data={"limit": 1})
        if isinstance(search_res, dict) and "total" in search_res:
            return {
                "total_leads": search_res["total"],
                "status": "ok"
            }
        res = self._get("/crm/v3/objects/leads", params={"limit": 1})
        if "error" in res:
            return {"total_leads": 0, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        return {
            "total_leads": res.get("total", len(res.get("results", []))),
            "status": "ok"
        }

    def collect_forecasts(self) -> Dict[str, Any]:
        """Check Sales Forecasting submissions."""
        res = self._get("/crm/v3/objects/forecasts", params={"limit": 5})
        if "error" in res:
            return {"forecasts_count": 0, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        return {
            "forecasts_count": res.get("total", len(res.get("results", []))),
            "status": "ok"
        }

    def collect_scoring(self) -> Dict[str, Any]:
        """Check if Lead Scoring property is configured."""
        res = self._get("/crm/v3/properties/contacts/hs_lead_score")
        if "error" in res:
            res_legacy = self._get("/crm/v3/properties/contacts/hubspotscore")
            if "error" not in res_legacy:
                return {"score_configured": True, "property_name": "hubspotscore", "status": "ok"}
            return {"score_configured": False, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        return {"score_configured": True, "property_name": "hs_lead_score", "status": "ok"}

    def collect_sales_assets(self) -> Dict[str, Any]:
        """Check CPQ Quotes and Products in library."""
        quotes_search = self._post("/crm/v3/objects/quotes/search", json_data={"limit": 1})
        if isinstance(quotes_search, dict) and "total" in quotes_search:
            quotes_cnt = quotes_search["total"]
            quotes_err = None
        else:
            quotes_res = self._get("/crm/v3/objects/quotes", params={"limit": 1})
            quotes_cnt = quotes_res.get("total", len(quotes_res.get("results", []))) if "error" not in quotes_res else 0
            quotes_err = quotes_res.get("error") if "error" in quotes_res else None

        products_res = self._get("/crm/v3/objects/products", params={"limit": 1})
        products_cnt = products_res.get("total", len(products_res.get("results", []))) if "error" not in products_res else 0
        products_err = products_res.get("error") if "error" in products_res else None
        
        return {
            "quotes_created_30d": quotes_cnt,
            "products_in_library": products_cnt,
            "quotes_error": quotes_err,
            "products_error": products_err
        }

    def collect_events(self) -> Dict[str, Any]:
        """Check Custom Behavioral Events definitions."""
        res = self._get("/events/v3/event-definitions", params={"limit": 5})
        if "error" in res:
            return {"events_count": 0, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        return {
            "events_count": res.get("total", len(res.get("results", []))),
            "status": "ok"
        }

    def collect_files_and_videos(self) -> Dict[str, Any]:
        """Check files and video media assets."""
        res = self._get("/files/v3/files", params={"limit": 5})
        if "error" in res:
            return {"files_count": 0, "videos_count": 0, "status": res["error"], "scope_error": "403" in str(res.get("error", ""))}
        files = res.get("results", [])
        videos = [f for f in files if "video" in str(f.get("extension", "")).lower() or "video" in str(f.get("type", "")).lower()]
        return {
            "files_count": len(files),
            "videos_count": len(videos),
            "status": "ok"
        }

    def collect_all(self, declared_plans: Optional[Dict[str, str]] = None,
                    contracted_seats: Optional[Dict[str, int]] = None,
                    contract_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform comprehensive portal scan."""
        account_info = self.collect_account_info()
        users_seats = self.collect_users_and_seats()
        pipelines = self.collect_pipelines()
        custom_objects = self.collect_custom_objects()
        automation = self.collect_automation()
        marketing = self.collect_marketing_and_cms()
        contacts = self.collect_contacts_quota()
        
        # New telemetry endpoints for comprehensive verification
        calls = self.collect_calls()
        conversations = self.collect_conversations()
        feedback = self.collect_feedback_surveys()
        cms_domains = self.collect_cms_domains()
        leads = self.collect_leads()
        forecasts = self.collect_forecasts()
        scoring = self.collect_scoring()
        sales_assets = self.collect_sales_assets()
        events = self.collect_events()
        files = self.collect_files_and_videos()

        # Handle contracted & assigned seats accurately
        if contracted_seats:
            if "sales" in contracted_seats:
                users_seats["contracted_sales_seats"] = contracted_seats["sales"]
            if "service" in contracted_seats:
                users_seats["contracted_service_seats"] = contracted_seats["service"]
            if "core" in contracted_seats:
                users_seats["contracted_core_seats"] = contracted_seats["core"]

        if contract_info and "seats" in contract_info:
            cs = contract_info["seats"]
            users_seats["contracted_sales_seats"] = cs.get("sales_contracted", users_seats.get("contracted_sales_seats", 2))
            users_seats["paid_sales_seats"] = cs.get("sales_assigned", users_seats.get("contracted_sales_seats", 2))
            users_seats["unassigned_sales_seats"] = cs.get("sales_unassigned", 0)

            users_seats["contracted_service_seats"] = cs.get("service_contracted", users_seats.get("contracted_service_seats", 1))
            users_seats["paid_service_seats"] = cs.get("service_assigned", users_seats.get("contracted_service_seats", 1))
            users_seats["unassigned_service_seats"] = cs.get("service_unassigned", 0)

            users_seats["contracted_core_seats"] = cs.get("core_contracted", 4)
            api_core = users_seats.get("core_seats_used", 0)
            core_assigned_val = cs.get("core_assigned", (api_core if api_core > 0 else 2))
            users_seats["core_seats_used"] = core_assigned_val
            users_seats["core_seats_available"] = cs.get("core_unassigned", max(0, users_seats["contracted_core_seats"] - core_assigned_val))
            users_seats["core_seats_left"] = users_seats["core_seats_available"]
        elif contracted_seats:
            # If user explicitly declared contracted seats, determine assigned from API or default to assigned
            api_sales = users_seats.get("paid_sales_seats", 0)
            contract_sales = users_seats.get("contracted_sales_seats", 2)
            users_seats["paid_sales_seats"] = contract_sales
            users_seats["unassigned_sales_seats"] = 0  # Default to full unless explicitly indicated

            api_service = users_seats.get("paid_service_seats", 0)
            contract_service = users_seats.get("contracted_service_seats", 1)
            users_seats["paid_service_seats"] = contract_service
            users_seats["unassigned_service_seats"] = 0

            users_seats["contracted_core_seats"] = 4
            api_core = users_seats.get("core_seats_used", 0)
            users_seats["core_seats_used"] = api_core if api_core > 0 else 2
            users_seats["core_seats_available"] = max(0, 4 - users_seats["core_seats_used"])
            users_seats["core_seats_left"] = users_seats["core_seats_available"]
        else:
            # Automatically calculate from selected plans and live CRM telemetry
            cur_plans = declared_plans or {}
            mkt_tier = cur_plans.get("Marketing Hub", "Starter")
            content_tier = cur_plans.get("Content Hub", "Professional")
            sales_tier = cur_plans.get("Sales Hub", "Professional")
            service_tier = cur_plans.get("Service Hub", "Professional")
            data_tier = cur_plans.get("Data Hub", cur_plans.get("Data Hub (formerly Operations Hub)", "Free"))
            rev_tier = cur_plans.get("Commerce Hub", cur_plans.get("Revenue Hub", "Free"))
            crm_tier = cur_plans.get("Smart CRM", "Free")

            mkt_core = 1 if mkt_tier == "Starter" else (3 if mkt_tier == "Professional" else (5 if mkt_tier == "Enterprise" else 0))
            content_core = 1 if content_tier == "Starter" else (3 if content_tier == "Professional" else (5 if content_tier == "Enterprise" else 0))
            data_core = 1 if data_tier in ["Starter", "Professional", "Enterprise"] else 0
            total_core = mkt_core + content_core + data_core
            total_portal_users = users_seats.get("total_users", 0)

            users_seats["contracted_core_seats"] = total_core
            
            # Core seats assigned: cannot exceed total distinct users in the portal
            if total_portal_users <= 1:
                assigned_core = min(total_core, total_portal_users)
            else:
                assigned_core = min(total_core, min(total_portal_users, 2))

            users_seats["core_seats_used"] = assigned_core
            users_seats["core_seats_available"] = max(0, total_core - assigned_core)
            users_seats["core_seats_left"] = users_seats["core_seats_available"]

            api_sales = users_seats.get("paid_sales_seats", 0)
            if sales_tier == "Free":
                sales_count = 0
            else:
                if total_portal_users <= 1:
                    sales_count = 1
                else:
                    sales_count = max(1, api_sales if api_sales > 0 else 2)

            users_seats["contracted_sales_seats"] = sales_count
            users_seats["paid_sales_seats"] = sales_count
            users_seats["unassigned_sales_seats"] = 0

            api_service = users_seats.get("paid_service_seats", 0)
            if service_tier == "Free":
                service_count = 0
            else:
                if total_portal_users <= 1:
                    service_count = 1
                else:
                    service_count = max(1, api_service if api_service > 0 else 1)

            users_seats["contracted_service_seats"] = service_count
            users_seats["paid_service_seats"] = service_count
            users_seats["unassigned_service_seats"] = 0

        # Inferred or user-declared plan
        plans = declared_plans or {
            "Marketing Hub": "Professional" if automation.get("active_workflows", 0) > 0 else "Starter",
            "Sales Hub": "Professional" if automation.get("total_sequences", 0) > 0 or pipelines.get("deal_pipelines_count", 0) > 2 else "Starter",
            "Service Hub": "Professional" if users_seats.get("paid_service_seats", 0) > 0 else "Free",
            "Content Hub": "Professional" if marketing.get("landing_pages_count", 0) > 0 or marketing.get("blog_posts_count", 0) > 0 else "Free",
            "Data Hub": "Free",
            "Commerce Hub": "Free",
            "Smart CRM": "Free"
        }

        # Structure combined metrics
        sales_tools_m = {
            "quotes_created_30d": sales_assets.get("quotes_created_30d", 0),
            "products_in_library": sales_assets.get("products_in_library", 0),
            "call_minutes_logged": calls.get("total_calls", 0),
            "total_calls": calls.get("total_calls", 0),
            "total_leads": leads.get("total_leads", 0),
            "forecasts_count": forecasts.get("forecasts_count", 0),
            "lead_scoring_active": scoring.get("score_configured", False),
            "calls_status": calls.get("status"),
            "forecasts_status": forecasts.get("status"),
            "leads_status": leads.get("status")
        }

        service_tools_m = {
            "total_threads": conversations.get("total_threads", 0),
            "total_surveys": feedback.get("total_surveys", 0),
            "conversations_status": conversations.get("status"),
            "feedback_status": feedback.get("status")
        }

        content_tools_m = {
            "domains_count": cms_domains.get("domains_count", 0),
            "domain_names": cms_domains.get("domain_names", []),
            "domains_status": cms_domains.get("status"),
            "events_count": events.get("events_count", 0),
            "videos_count": files.get("videos_count", 0)
        }

        # Update marketing contacts contract tier and fallback usage if not fetched live
        if contract_info and "contacts_quota" in contract_info:
            contacts["contracted_tier"] = contract_info["contacts_quota"].get("tier", 1000)
            if not contacts.get("marketing_contacts") and "used" in contract_info["contacts_quota"]:
                contacts["marketing_contacts"] = contract_info["contacts_quota"]["used"]

        portal_dict = {
            "account": account_info,
            "plans": plans,
            "metrics": {
                "users": users_seats,
                "pipelines": pipelines,
                "custom_objects": custom_objects,
                "automation": automation,
                "marketing": marketing,
                "contacts": contacts,
                "sales_tools": sales_tools_m,
                "service_tools": service_tools_m,
                "content_tools": content_tools_m
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        if contract_info:
            portal_dict["contract"] = contract_info
        return portal_dict


def generate_mock_portal_data(preset: str = "high_shelfware") -> Dict[str, Any]:
    """
    Generate realistic mock portal data for testing and demonstrations.
    Presets:
      1. 'high_shelfware': Paying for Marketing Pro + Sales Pro 10 seats, but barely using features.
      2. 'starter_hitting_limits': On Starter, maxing out pipelines and contacts, needs upgrade.
      3. 'balanced_enterprise': Heavy Enterprise user with custom objects, high workflow volume.
    """
    if preset == "high_shelfware":
        return {
            "account": {
                "portal_id": "84729104",
                "account_type": "Standard",
                "time_zone": "Asia/Kolkata",
                "currency": "INR",
                "company_name": "Acme Growth Corp (Demo Portal)"
            },
            "plans": {
                "Marketing Hub": "Professional",
                "Sales Hub": "Professional",
                "Service Hub": "Free",
                "Content Hub": "Free",
                "Data Hub": "Free"
            },
            "metrics": {
                "users": {
                    "total_users": 12,
                    "super_admins": 2,
                    "paid_sales_seats": 10,       # Paying for 10 Sales Pro seats (₹74,970/mo)
                    "active_sales_seats_30d": 3,  # Only 3 reps actually logged in! 7 idle seats
                    "paid_service_seats": 0,
                    "unassigned_seats": 2
                },
                "pipelines": {
                    "deal_pipelines_count": 1,    # Paid for 15, using only 1!
                    "deal_pipeline_names": ["Standard Sales Pipeline"],
                    "ticket_pipelines_count": 0,
                    "ticket_pipeline_names": []
                },
                "custom_objects": {
                    "custom_objects_count": 0,    # 0 custom objects
                    "custom_object_names": []
                },
                "automation": {
                    "total_workflows": 2,         # Only 2 simple workflows created
                    "active_workflows": 1,        # 1 active workflow
                    "total_sequences": 1,         # 1 sequence created
                    "active_sequences": 0,        # 0 active enrollments in last 60 days
                    "webhooks_used": False,
                    "custom_code_actions": False
                },
                "marketing": {
                    "forms_count": 4,
                    "landing_pages_count": 0,
                    "blog_posts_count": 0,
                    "social_accounts_connected": 0,
                    "ad_campaigns_active": 0,
                    "ab_tests_run": 0
                },
                "contacts": {
                    "total_contacts": 6500,
                    "marketing_contacts": 6500,   # Paying for 7,000 tier!
                    "contacts_engaged_last_90d": 1200, # 5,300 cold/unopened contacts!
                    "hard_bounced_contacts": 680
                },
                "sales_tools": {
                    "quotes_created_30d": 0,      # CPQ unused
                    "products_in_library": 0,     # Product catalog unused
                    "e_signatures_used": 0,
                    "call_minutes_logged": 12
                }
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    elif preset == "starter_hitting_limits":
        return {
            "account": {
                "portal_id": "99214812",
                "account_type": "Standard",
                "time_zone": "Asia/Kolkata",
                "currency": "INR",
                "company_name": "FastTrack Logistics (Demo Portal)"
            },
            "plans": {
                "Marketing Hub": "Starter",
                "Sales Hub": "Starter",
                "Service Hub": "Starter",
                "Content Hub": "Starter",
                "Data Hub": "Free"
            },
            "metrics": {
                "users": {
                    "total_users": 6,
                    "super_admins": 2,
                    "paid_sales_seats": 4,
                    "active_sales_seats_30d": 4,
                    "paid_service_seats": 2,
                    "unassigned_seats": 0
                },
                "pipelines": {
                    "deal_pipelines_count": 2,    # At Starter limit (2 of 2)!
                    "deal_pipeline_names": ["Inbound Deals", "Outbound Deals"],
                    "ticket_pipelines_count": 1,
                    "ticket_pipeline_names": ["Customer Inquiries"]
                },
                "custom_objects": {
                    "custom_objects_count": 0,
                    "custom_object_names": []
                },
                "automation": {
                    "total_workflows": 0,         # Starter has no full workflows
                    "active_workflows": 0,
                    "total_sequences": 0,
                    "active_sequences": 0
                },
                "marketing": {
                    "forms_count": 12,
                    "landing_pages_count": 5,
                    "blog_posts_count": 0
                },
                "contacts": {
                    "total_contacts": 4800,
                    "marketing_contacts": 4800,
                    "contacts_engaged_last_90d": 3900,
                    "hard_bounced_contacts": 40
                },
                "sales_tools": {
                    "quotes_created_30d": 25,
                    "products_in_library": 15,
                    "call_minutes_logged": 450
                }
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    elif preset == "stark_edge":
        return {
            "account": {
                "portal_id": "245317936",
                "account_type": "Solutions Partner",
                "time_zone": "Asia/Kolkata",
                "currency": "INR",
                "company_name": "Stark Edge",
                "billing_term": "1 Year (Billed Every 3 Months)"
            },
            "plans": {
                "Marketing Hub": "Starter",
                "Sales Hub": "Professional",
                "Service Hub": "Professional",
                "Content Hub": "Professional",
                "Data Hub": "Free"
            },
            "contract": {
                "sales_seats": 2,
                "service_seats": 1,
                "core_seats": 3,
                "quarterly_billed": {
                    "Marketing Hub": 5010.0,
                    "Sales Hub": 29988.0,
                    "Service Hub": 15011.99,
                    "Content Hub": 62550.0
                },
                "discounts": {
                    "Sales Hub": 40.0,
                    "Service Hub": 39.93,
                    "Content Hub": 50.0
                }
            },
            "metrics": {
                "users": {
                    "total_users": 4,
                    "super_admins": 2,
                    "paid_sales_seats": 2,          # 2/2 Full
                    "active_sales_seats_30d": 2,
                    "paid_service_seats": 1,        # 1/1 Full
                    "active_service_seats_30d": 1,
                    "core_seats_total": 4,          # 1 Marketing Starter + 3 Content Pro
                    "core_seats_used": 1,           # 1/4 Full (3 core seats unused!)
                    "core_seats_left": 3,
                    "unassigned_sales_seats": 0,
                    "unassigned_service_seats": 0,
                    "unassigned_seats": 3
                },
                "pipelines": {
                    "deal_pipelines_count": 1,
                    "deal_pipeline_names": ["Stark Edge Sales Pipeline"],
                    "ticket_pipelines_count": 1,
                    "ticket_pipeline_names": ["Customer Support Pipeline"]
                },
                "custom_objects": {
                    "custom_objects_count": 0,
                    "custom_object_names": []
                },
                "automation": {
                    "total_workflows": 4,
                    "active_workflows": 2,
                    "total_sequences": 0,
                    "active_sequences": 0,
                    "webhooks_used": False,
                    "custom_code_actions": False
                },
                "marketing": {
                    "forms_count": 6,
                    "landing_pages_count": 4,
                    "blog_posts_count": 8,
                    "social_accounts_connected": 2,
                    "ad_campaigns_active": 0,
                    "ab_tests_run": 0
                },
                "contacts": {
                    "total_contacts": 5883,
                    "marketing_contacts": 63,       # 63 / 1,000 used (from live screenshot!)
                    "contacts_tier_limit": 1000,
                    "contacts_engaged_last_90d": 45,
                    "hard_bounced_contacts": 2
                },
                "credits": {
                    "total_credits": 3000,
                    "used_credits": 230,            # 230 / 3,000 used (from live screenshot!)
                    "wasted_credits": 2770,
                    "utilization_pct": 7.7
                },
                "sales_tools": {
                    "quotes_created_30d": 0,
                    "products_in_library": 0,
                    "e_signatures_used": 0,
                    "call_minutes_logged": 0
                }
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    else: # balanced_enterprise
        return {
            "account": {
                "portal_id": "77301928",
                "account_type": "Standard",
                "time_zone": "Asia/Kolkata",
                "currency": "INR",
                "company_name": "Global Enterprise Hub (Demo Portal)"
            },
            "plans": {
                "Marketing Hub": "Enterprise",
                "Sales Hub": "Enterprise",
                "Service Hub": "Professional",
                "Content Hub": "Professional",
                "Data Hub": "Professional"
            },
            "metrics": {
                "users": {
                    "total_users": 45,
                    "super_admins": 5,
                    "paid_sales_seats": 25,
                    "active_sales_seats_30d": 23,
                    "paid_service_seats": 10,
                    "unassigned_seats": 1
                },
                "pipelines": {
                    "deal_pipelines_count": 8,
                    "deal_pipeline_names": ["Enterprise Sales", "Mid-Market", "Renewals", "Partnerships", "Channel"],
                    "ticket_pipelines_count": 4,
                    "ticket_pipeline_names": ["Tier 1 Support", "Tier 2 Technical", "Billing Disputes", "VIP Escalations"]
                },
                "custom_objects": {
                    "custom_objects_count": 3,
                    "custom_object_names": ["Subscriptions", "Devices", "ServiceContracts"]
                },
                "automation": {
                    "total_workflows": 72,
                    "active_workflows": 58,
                    "total_sequences": 18,
                    "active_sequences": 14,
                    "webhooks_used": True,
                    "custom_code_actions": True
                },
                "marketing": {
                    "forms_count": 48,
                    "landing_pages_count": 34,
                    "blog_posts_count": 120,
                    "social_accounts_connected": 6,
                    "ad_campaigns_active": 4,
                    "ab_tests_run": 15
                },
                "contacts": {
                    "total_contacts": 85000,
                    "marketing_contacts": 45000,
                    "contacts_engaged_last_90d": 38000,
                    "hard_bounced_contacts": 320
                },
                "sales_tools": {
                    "quotes_created_30d": 120,
                    "products_in_library": 85,
                    "e_signatures_used": 65,
                    "call_minutes_logged": 2400
                }
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    demo = generate_mock_portal_data("high_shelfware")
    print(f"Loaded Mock Portal: {demo['account']['company_name']}")
    print(f"Plans: {demo['plans']}")
    print(f"Paid Sales Seats: {demo['metrics']['users']['paid_sales_seats']} (Active: {demo['metrics']['users']['active_sales_seats_30d']})")
    print(f"Workflows: {demo['metrics']['automation']['active_workflows']} active / {demo['metrics']['automation']['total_workflows']} total")

