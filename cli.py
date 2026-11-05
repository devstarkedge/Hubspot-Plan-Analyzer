"""
HubSpot Plan & Feature Utilization Analyzer - Command Line Interface
Usage:
  # 1. Interactive mode (prompts user to enter token and select plans)
  python cli.py -i
  python cli.py --interactive

  # 2. Command-line flags with live token:
  python cli.py --token <YOUR_TOKEN> --mkt-plan Starter --sales-plan Professional --sales-seats 2 --content-plan Professional
"""

import sys
import os
import argparse
sys.stdout.reconfigure(encoding='utf-8')

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.catalog_parser import HubSpotCatalog
from src.hubspot_collector import HubSpotCollector
from src.analyzer import PlanAnalyzer
from src.report_generator import ReportGenerator

TIERS = ["Free", "Starter", "Professional", "Enterprise"]

def prompt_select(prompt_text, choices, default):
    print(f"\n{prompt_text}")
    for idx, c in enumerate(choices, 1):
        marker = " (Default)" if c == default else ""
        print(f"  [{idx}] {c}{marker}")
    while True:
        choice = input(f"Select 1-{len(choices)} [Enter for {default}]: ").strip()
        if not choice:
            return default
        if choice.isdigit() and 1 <= int(choice) <= len(choices):
            return choices[int(choice) - 1]
        print("Invalid choice, please try again.")

def prompt_int(prompt_text, default):
    val = input(f"{prompt_text} [Default: {default}]: ").strip()
    if not val:
        return default
    try:
        return max(0, int(val))
    except ValueError:
        return default

def main():
    parser = argparse.ArgumentParser(description="HubSpot Plan & Feature Utilization Analyzer (INR)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactively prompt you to enter your token and select plans")
    parser.add_argument("--token", type=str, help="HubSpot Private App Access Token", default=None)
    
    # Custom plan flags
    parser.add_argument("--mkt-plan", choices=TIERS, default=None, help="Marketing Hub tier")
    parser.add_argument("--sales-plan", choices=TIERS, default=None, help="Sales Hub tier")
    parser.add_argument("--sales-seats", type=int, default=None, help="Contracted Sales Pro seats")
    parser.add_argument("--service-plan", choices=TIERS, default=None, help="Service Hub tier")
    parser.add_argument("--service-seats", type=int, default=None, help="Contracted Service Pro seats")
    parser.add_argument("--content-plan", choices=TIERS, default=None, help="Content Hub tier")
    parser.add_argument("--data-plan", choices=TIERS, default=None, help="Data Hub tier")
    parser.add_argument("--commerce-plan", "--revenue-plan", choices=TIERS, default=None, help="Commerce Hub / Revenue Hub tier")
    parser.add_argument("--crm-plan", choices=TIERS, default=None, help="Smart CRM tier")

    parser.add_argument("--export-html", type=str, default="hubspot_audit_report.html", help="Path to save HTML report")
    parser.add_argument("--export-md", type=str, default=None, help="Path to save Markdown summary")
    parser.add_argument("--catalog", type=str, default="HubSpot_All_Hubs_INR_Master_Catalog_Verified_29Oct2026.xlsx", help="Path to Excel Catalog")
    
    args = parser.parse_args()

    print("=" * 70)
    print(" HubSpot Plan & Feature Utilization Analyzer (Live Portal Auditor)")
    print("=" * 70)

    # 1. Load Master Catalog
    if not os.path.exists(args.catalog):
        print(f"[-] Error: Master Catalog file '{args.catalog}' not found!")
        sys.exit(1)

    print(f"[+] Loading INR Master Catalog from: {args.catalog}...")
    catalog = HubSpotCatalog(args.catalog)
    cat_stats = catalog.get_summary_stats()
    print(f"[+] Catalog verified: {cat_stats['total_features']} features across {len(cat_stats['hubs_covered'])} Hubs.")

    # 2. Token & Plan Configuration
    token = args.token
    plans = {}
    seats = {}

    if args.interactive:
        print("\n--- Portal & Plan Setup ---")
        while not token:
            token = input("Enter HubSpot Private App Access Token: ").strip()
            if not token:
                print("[-] Token is required to scan your live portal. Please paste your token.")
        
        plans["Marketing Hub"] = prompt_select("Select Marketing Hub Plan:", TIERS, "Starter")
        plans["Sales Hub"] = prompt_select("Select Sales Hub Plan:", TIERS, "Professional")
        if plans["Sales Hub"] in ["Starter", "Professional", "Enterprise"]:
            seats["sales"] = prompt_int("Enter number of contracted Sales seats:", 2 if plans["Sales Hub"] == "Professional" else 1)
        
        plans["Service Hub"] = prompt_select("Select Service Hub Plan:", TIERS, "Professional")
        if plans["Service Hub"] in ["Starter", "Professional", "Enterprise"]:
            seats["service"] = prompt_int("Enter number of contracted Service seats:", 1)
            
        plans["Content Hub"] = prompt_select("Select Content Hub Plan:", TIERS, "Professional")
        plans["Data Hub"] = prompt_select("Select Data Hub (formerly Operations Hub) Plan:", TIERS, "Free")
        plans["Commerce Hub"] = prompt_select("Select Commerce Hub (Invoicing & CPQ) Plan:", ["Free", "Professional", "Enterprise"], "Free")
        plans["Smart CRM"] = prompt_select("Select Smart CRM Plan:", ["Free", "Starter", "Professional", "Enterprise"], "Free")
    else:
        if not token:
            print("\n[-] Error: HubSpot Private App Token is required.")
            print("[+] Usage: python cli.py --token <YOUR_TOKEN> or run interactively with: python cli.py -i")
            sys.exit(1)

        if args.mkt_plan:
            plans["Marketing Hub"] = args.mkt_plan
        if args.sales_plan:
            plans["Sales Hub"] = args.sales_plan
        if args.service_plan:
            plans["Service Hub"] = args.service_plan
        if args.content_plan:
            plans["Content Hub"] = args.content_plan
        if args.data_plan:
            plans["Data Hub"] = args.data_plan
        if args.commerce_plan:
            plans["Commerce Hub"] = args.commerce_plan
        if args.crm_plan:
            plans["Smart CRM"] = args.crm_plan
        
        if args.sales_seats is not None:
            seats["sales"] = args.sales_seats
        if args.service_seats is not None:
            seats["service"] = args.service_seats

    # 3. Collect Live Portal Data
    print(f"\n[+] Connecting to live HubSpot Portal via Private App Token...")
    collector = HubSpotCollector(token)
    portal_data = collector.collect_all(
        declared_plans=plans if plans else None,
        contracted_seats=seats if seats else None
    )
    portal_id = portal_data.get("account", {}).get("portal_id", "Unknown")
    print(f"[+] Live scan completed for Portal ID: {portal_id}")

    # 4. Analyze
    print("[+] Analyzing feature adoption against plan entitlement & INR rates...")
    analyzer = PlanAnalyzer(catalog)
    audit_result = analyzer.analyze(portal_data)

    # 5. Display Summary to Terminal
    fin = audit_result["financials"]
    adopt = audit_result["adoption"]
    account = audit_result["account"]

    print("\n" + "-" * 70)
    print(f" AUDIT SUMMARY: {account.get('company_name', 'Portal')} (ID: {account.get('portal_id', 'N/A')})")
    print("-" * 70)
    print(f" Current Monthly Spend   : ₹{fin['monthly_spend_inr']:>12,.0f}  (Annual: ₹{fin['annual_spend_inr']:,.0f})")
    print(f" Wasted / Idle Spend     : ₹{fin['monthly_waste_inr']:>12,.0f}  ({fin['waste_percentage']}% of total budget)")
    print(f" Feature Adoption Rate   : {adopt['adoption_rate_pct']:>11.1f}%  ({adopt['used_features']} used / {adopt['in_plan_features']} in-plan)")
    print(f" Idle Sales Pro Seats    : {fin['idle_sales_seats']:>12d}  (Waste: ₹{fin['idle_seat_waste_monthly_inr']:,.0f}/mo)")
    print("-" * 70)

    print("\n[!] Top Optimization Recommendations:")
    for i, r in enumerate(audit_result["recommendations"], 1):
        sav_str = f" [Save ₹{r['savings_monthly_inr']:,.0f}/mo]" if r.get('savings_monthly_inr', 0) > 0 else ""
        print(f"  {i}. [{r['priority']}] {r['title']}{sav_str}")
        print(f"     {r['description'][:100]}...")

    if audit_result["downgrade_risks"]:
        print("\n[!] Downgrade Impact Simulation:")
        for d in audit_result["downgrade_risks"]:
            print(f"  • [{d['severity']}] {d['hub']} ({d['from_tier']} → {d['target_tier']}): {d['impact']}")

    # 6. Export Reports
    rg = ReportGenerator(audit_result)
    html_path = rg.generate_html(args.export_html)
    print(f"\n[✓] Interactive HTML Report generated: {os.path.abspath(html_path)}")

    if args.export_md:
        md_text = rg.generate_markdown()
        with open(args.export_md, "w", encoding="utf-8") as f:
            f.write(md_text)
        print(f"[✓] Markdown Summary generated: {os.path.abspath(args.export_md)}")

    print("=" * 70)

if __name__ == "__main__":
    main()
