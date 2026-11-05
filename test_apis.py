"""
HubSpot API Diagnostic & Health Checker
Tests every API endpoint used by the analyzer to verify status, scopes, and response data.
Usage:
  python test_apis.py --token <YOUR_HUBSPOT_TOKEN>
"""

import sys
import os
import time
import requests
import argparse
sys.stdout.reconfigure(encoding='utf-8')

HUBSPOT_API_BASE = "https://api.hubapi.com"

ENDPOINTS = [
    {
        "name": "Account Details",
        "path": "/account-info/v3/details",
        "scope": "account-info.details.read",
        "description": "Portal ID, currency, time zone"
    },
    {
        "name": "Users & Seats",
        "path": "/settings/v3/users/",
        "scope": "settings.users.read",
        "description": "User accounts, paid sales/service seat assignments"
    },
    {
        "name": "Deal Pipelines",
        "path": "/crm/v3/pipelines/deals",
        "scope": "crm.objects.deals.read",
        "description": "Deal pipelines and stage counts"
    },
    {
        "name": "Ticket Pipelines",
        "path": "/crm/v3/pipelines/tickets",
        "scope": "crm.objects.deals.read / tickets",
        "description": "Service ticket pipelines"
    },
    {
        "name": "Automated Workflows",
        "path": "/automation/v3/workflows",
        "scope": "automation",
        "description": "Active vs disabled marketing/sales workflows"
    },
    {
        "name": "Sales Sequences",
        "path": "/automation/v4/sequences",
        "scope": "automation",
        "description": "Sales sequence campaigns"
    },
    {
        "name": "Contacts Quota",
        "path": "/crm/v3/objects/contacts?limit=1",
        "scope": "crm.objects.contacts.read",
        "description": "Contact database size"
    },
    {
        "name": "Custom Objects",
        "path": "/crm/v3/schemas",
        "scope": "crm.schemas.custom.read",
        "description": "Enterprise custom object definitions"
    },
    {
        "name": "Marketing Forms",
        "path": "/marketing/v3/forms",
        "scope": "forms",
        "description": "Lead generation forms"
    },
    {
        "name": "CMS Landing Pages",
        "path": "/cms/v3/pages/landing-pages",
        "scope": "content",
        "description": "Published landing pages"
    },
    {
        "name": "CMS Blog Posts",
        "path": "/cms/v3/blogs/posts",
        "scope": "content",
        "description": "Published blog posts"
    },
    {
        "name": "Sales Quotes",
        "path": "/crm/v3/objects/quotes?limit=1",
        "scope": "crm.objects.deals.read",
        "description": "CPQ quotes created"
    },
    {
        "name": "Products Library",
        "path": "/crm/v3/objects/products?limit=1",
        "scope": "crm.objects.deals.read",
        "description": "Products in line item library"
    },
    {
        "name": "Calls & Phone Log",
        "path": "/crm/v3/objects/calls?limit=1",
        "scope": "crm.objects.contacts.read / sales-email-read",
        "description": "Call records and minutes logged"
    },
    {
        "name": "Help Desk & Conversations",
        "path": "/conversations/v3/conversations/threads?limit=1",
        "scope": "conversations.read",
        "description": "Help Desk inboxes, chat & bot conversation threads"
    },
    {
        "name": "Customer Feedback & Surveys",
        "path": "/crm/v3/objects/feedback_submissions?limit=1",
        "scope": "crm.objects.feedback_submissions.read",
        "description": "CSAT, NPS, and support survey submissions"
    },
    {
        "name": "CMS Connected Domains",
        "path": "/cms/v3/domains",
        "scope": "content",
        "description": "Connected custom domains, SSL, and hosting"
    },
    {
        "name": "Sales Leads & Prospecting",
        "path": "/crm/v3/objects/leads?limit=1",
        "scope": "crm.objects.leads.read",
        "description": "Leads created in Prospecting workspace"
    },
    {
        "name": "Sales Forecasting",
        "path": "/crm/v3/objects/forecasts?limit=1",
        "scope": "crm.objects.custom.read / forecasts",
        "description": "Forecast submissions and targets"
    },
    {
        "name": "Lead Scoring Model",
        "path": "/crm/v3/properties/contacts/hs_lead_score",
        "scope": "crm.objects.contacts.read",
        "description": "Lead score property and scoring model configuration"
    },
    {
        "name": "Custom Events",
        "path": "/events/v3/event-definitions?limit=1",
        "scope": "crm.objects.custom.read / analytics",
        "description": "Custom behavioral event definitions"
    },
    {
        "name": "Files & Video Assets",
        "path": "/files/v3/files?limit=1",
        "scope": "files",
        "description": "Hosted video media assets and files"
    }
]

def check_all_apis(token: str):
    if not token:
        print("[-] Error: HubSpot Private App Token is required.")
        print("[+] Usage: python test_apis.py --token pat-na1-xxxx-xxxx")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("=" * 80)
    print(" HubSpot Live API Diagnostic & Health Check")
    print("=" * 80)
    print(f"Token: {token[:12]}...{token[-4:] if len(token) > 16 else ''}")
    print(f"Testing {len(ENDPOINTS)} endpoints...\n")

    results = []
    success_count = 0

    for ep in ENDPOINTS:
        url = f"{HUBSPOT_API_BASE}{ep['path']}"
        start_t = time.time()
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            latency_ms = round((time.time() - start_t) * 1000)
            status_code = resp.status_code
            
            data_summary = ""
            status_label = ""
            if status_code == 200:
                success_count += 1
                status_label = "🟢 200 OK"
                try:
                    j = resp.json()
                    if isinstance(j, dict):
                        if "results" in j:
                            data_summary = f"{len(j['results'])} items found"
                        elif "workflows" in j:
                            data_summary = f"{len(j['workflows'])} workflows found"
                        elif "total" in j:
                            data_summary = f"Total: {j['total']}"
                        elif "portalId" in j:
                            data_summary = f"Portal ID: {j['portalId']}"
                        else:
                            data_summary = f"{len(j)} keys"
                    else:
                        data_summary = "OK"
                except Exception:
                    data_summary = "OK"
            elif status_code in (401, 403):
                status_label = f"🔴 {status_code} FORBIDDEN"
                data_summary = f"Scope '{ep['scope']}' not granted on token"
            elif status_code == 404:
                status_label = "🟡 404 NOT FOUND"
                data_summary = "Endpoint not enabled for this hub tier"
            else:
                status_label = f"⚪ HTTP {status_code}"
                data_summary = resp.text[:60]

        except Exception as e:
            latency_ms = round((time.time() - start_t) * 1000)
            status_label = "💥 CONNECTION ERROR"
            data_summary = str(e)[:60]

        results.append({
            "name": ep["name"],
            "path": ep["path"],
            "scope": ep["scope"],
            "status": status_label,
            "latency": f"{latency_ms}ms",
            "summary": data_summary
        })

        print(f" {status_label:<18} | {latency_ms:>5}ms | {ep['name']:<22} | {data_summary}")

    print("\n" + "=" * 80)
    print(f" RESULT: {success_count} of {len(ENDPOINTS)} endpoints responding successfully (200 OK)")
    print("=" * 80)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test all HubSpot APIs with your token")
    parser.add_argument("--token", type=str, help="HubSpot Private App Access Token", default=None)
    args = parser.parse_args()

    token = args.token
    if not token:
        token = input("Enter your HubSpot Private App Token to test: ").strip()

    check_all_apis(token)

