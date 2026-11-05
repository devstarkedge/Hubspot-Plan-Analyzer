"""
HubSpot Master Catalog Parser
Extracts structured pricing, feature matrices, plan limits, and downgrade rules
from 'HubSpot_All_Hubs_INR_Master_Catalog_Verified_29Oct2026.xlsx'.
Supports both openpyxl and a built-in zero-dependency zipfile/XML reader.
"""
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

CATALOG_FILENAME = "HubSpot_All_Hubs_INR_Master_Catalog_Verified_29Oct2026.xlsx"

def clean_text(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()

def extract_inr_number(text: str) -> Optional[int]:
    """Extract numeric INR value from text like '₹74,200/month' or '₹66,697'."""
    if not text:
        return None
    m = re.search(r'[₹]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)', text)
    if m:
        try:
            return int(m.group(1).replace(',', ''))
        except ValueError:
            return None
    return None

def _read_sheet_via_zip(excel_path: str, sheet_name: str) -> List[List[str]]:
    """Zero-dependency fallback reader using Python standard library zipfile + xml."""
    try:
        with zipfile.ZipFile(excel_path, 'r') as z:
            sst = []
            if 'xl/sharedStrings.xml' in z.namelist():
                sroot = ET.fromstring(z.read('xl/sharedStrings.xml'))
                for si in sroot.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                    text = ''.join(t.text for t in si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t') if t.text)
                    sst.append(text)
            
            wb_rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
            rel_map = {r.attrib['Id']: r.attrib['Target'].lstrip('/') for r in wb_rels}
            wb = ET.fromstring(z.read('xl/workbook.xml'))
            target_path = None
            for s in wb.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
                if s.attrib['name'] == sheet_name:
                    rId = s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
                    t = rel_map[rId]
                    target_path = t if t.startswith('xl/') else 'xl/' + t
                    break
            if not target_path:
                return []
            
            sxml = ET.fromstring(z.read(target_path))
            rows = []
            for r in sxml.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                row_vals = []
                for c in r.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                    t = c.attrib.get('t')
                    if t == 'inlineStr':
                        t_el = c.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                        val = t_el.text if t_el is not None else ''
                    else:
                        v_el = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                        val = v_el.text if v_el is not None else ''
                        if t == 's' and val.isdigit() and sst:
                            val = sst[int(val)]
                    row_vals.append(val)
                rows.append(row_vals)
            return rows
    except Exception:
        return []

class HubSpotCatalog:
    def __init__(self, excel_path: str = CATALOG_FILENAME):
        self.excel_path = excel_path
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"Master Catalog file not found: {excel_path}")
        
        self.wb = None
        if HAS_OPENPYXL:
            try:
                self.wb = openpyxl.load_workbook(excel_path, data_only=True)
            except Exception:
                self.wb = None

        self.pricing_cards: List[Dict[str, Any]] = []
        self.feature_matrix: List[Dict[str, Any]] = []
        self.plan_limits: List[Dict[str, Any]] = []
        self.downgrade_impacts: List[Dict[str, Any]] = []
        self.seats_billing: List[Dict[str, Any]] = []
        self._load_all()

    def _get_sheet_rows(self, sheet_name: str) -> List[List[Any]]:
        if self.wb is not None and sheet_name in self.wb.sheetnames:
            ws = self.wb[sheet_name]
            return list(ws.iter_rows(values_only=True))
        # Fallback to zero-dependency zipfile reader
        return _read_sheet_via_zip(self.excel_path, sheet_name)

    def _load_all(self):
        self._load_pricing()
        self._load_features()
        self._load_limits()
        self._load_downgrades()
        self._load_seats_billing()

    def _load_pricing(self):
        rows = self._get_sheet_rows('Pricing Cards - INR')
        if not rows:
            return
        
        header_idx = -1
        for i, row in enumerate(rows[:5]):
            row_strs = [clean_text(c).lower() for c in row if c is not None]
            if any('hub' in s for s in row_strs) and any('plan' in s for s in row_strs):
                header_idx = i
                break
        if header_idx == -1:
            header_idx = 2

        for row in rows[header_idx + 1:]:
            if not row or not any(row):
                continue
            hub = clean_text(row[0])
            plan = clean_text(row[1])
            if not hub or not plan:
                continue
            price_shown = clean_text(row[2])
            list_price = clean_text(row[3]) if len(row) > 3 else ""
            pay_monthly = clean_text(row[4]) if len(row) > 4 else ""
            pay_annually = clean_text(row[5]) if len(row) > 5 else ""
            
            monthly_rate = extract_inr_number(pay_monthly) or extract_inr_number(price_shown) or 0
            annual_rate = extract_inr_number(pay_annually) or monthly_rate

            self.pricing_cards.append({
                "hub": hub,
                "plan": plan,
                "price_shown": price_shown,
                "list_price": list_price,
                "pay_monthly": pay_monthly,
                "pay_annually": pay_annually,
                "est_monthly_inr": monthly_rate,
                "est_annual_monthly_inr": annual_rate
            })

    def _load_features(self):
        rows = self._get_sheet_rows('Full Feature Matrix')
        if not rows:
            return
        
        for row in rows[1:]:
            if not row or len(row) < 3 or not row[0] or not row[2]:
                continue
            hub = clean_text(row[0])
            category = clean_text(row[1])
            feature = clean_text(row[2])
            free_scope = clean_text(row[3]) if len(row) > 3 else ""
            starter_scope = clean_text(row[4]) if len(row) > 4 else ""
            pro_scope = clean_text(row[5]) if len(row) > 5 else ""
            ent_scope = clean_text(row[6]) if len(row) > 6 else ""
            notes = clean_text(row[7]) if len(row) > 7 else ""

            self.feature_matrix.append({
                "hub": hub,
                "category": category,
                "feature": feature,
                "tiers": {
                    "Free": free_scope,
                    "Starter": starter_scope,
                    "Professional": pro_scope,
                    "Enterprise": ent_scope
                },
                "notes": notes
            })

    def _load_limits(self):
        rows = self._get_sheet_rows('Plan Limits & Quotas')
        if not rows:
            return
        
        for row in rows[1:]:
            if not row or len(row) < 2 or not row[0]:
                continue
            area = clean_text(row[0])
            limit_name = clean_text(row[1])
            free_lim = clean_text(row[2]) if len(row) > 2 else ""
            starter_lim = clean_text(row[3]) if len(row) > 3 else ""
            pro_lim = clean_text(row[4]) if len(row) > 4 else ""
            ent_lim = clean_text(row[5]) if len(row) > 5 else ""

            self.plan_limits.append({
                "area": area,
                "limit_name": limit_name,
                "Free": free_lim,
                "Starter": starter_lim,
                "Professional": pro_lim,
                "Enterprise": ent_lim
            })

    def _load_downgrades(self):
        rows = self._get_sheet_rows('Downgrade Impact')
        if not rows:
            return
        
        start_idx = 0
        for i, row in enumerate(rows[:5]):
            if row and any("potential impact" in clean_text(c).lower() for c in row if c is not None):
                start_idx = i + 1
                break
        for row in rows[start_idx:]:
            if not row or not any(row) or not row[0]:
                continue
            asset = clean_text(row[0])
            impact = clean_text(row[1]) if len(row) > 1 else ""
            action = clean_text(row[2]) if len(row) > 2 else ""
            self.downgrade_impacts.append({
                "asset": asset,
                "impact": impact,
                "action": action
            })

    def _load_seats_billing(self):
        rows = self._get_sheet_rows('Seats, Credits & Billing')
        if not rows:
            return
        
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            item = clean_text(row[0])
            meaning = clean_text(row[1]) if len(row) > 1 else ""
            free_val = clean_text(row[2]) if len(row) > 2 else ""
            starter_val = clean_text(row[3]) if len(row) > 3 else ""
            pro_val = clean_text(row[4]) if len(row) > 4 else ""
            ent_val = clean_text(row[5]) if len(row) > 5 else ""

            self.seats_billing.append({
                "item": item,
                "meaning": meaning,
                "Free": free_val,
                "Starter": starter_val,
                "Professional": pro_val,
                "Enterprise": ent_val
            })

    def normalize_hub(self, hub: str) -> str:
        """Normalize various Hub aliases to Master Catalog canonical names."""
        h = (hub or "").strip().lower()
        if "commerce" in h or "revenue" in h:
            return "Revenue Hub"
        if "data" in h or "operations" in h or "ops" in h:
            return "Data Hub"
        if "crm" in h or "platform" in h:
            return "Platform-wide"
        if "market" in h:
            return "Marketing Hub"
        if "sales" in h:
            return "Sales Hub"
        if "service" in h:
            return "Service Hub"
        if "content" in h or "cms" in h:
            return "Content Hub"
        return hub

    def get_plan_pricing(self, hub: str, plan: str) -> Optional[Dict[str, Any]]:
        norm_hub = self.normalize_hub(hub)
        plan_lower = (plan or "").lower()

        # Platform-wide / Smart CRM Free foundation
        if norm_hub == "Platform-wide" or "crm" in (hub or "").lower():
            return {
                "hub": "Smart CRM",
                "plan": plan or "Free",
                "price_shown": "₹0/month",
                "list_price": "₹0/month",
                "pay_monthly": "₹0/month",
                "pay_annually": "₹0/month",
                "est_monthly_inr": 0,
                "est_annual_monthly_inr": 0
            }

        hub_lower = norm_hub.lower().replace(" hub", "")
        for p in self.pricing_cards:
            p_hub_lower = self.normalize_hub(p["hub"]).lower().replace(" hub", "")
            p_plan_lower = p["plan"].lower()
            if p_hub_lower == hub_lower:
                if p_plan_lower == plan_lower or (plan_lower == "free" and "free" in p_plan_lower):
                    return p
        return None

    def get_features_for_hub(self, hub: str) -> List[Dict[str, Any]]:
        norm_hub = self.normalize_hub(hub)
        return [f for f in self.feature_matrix if self.normalize_hub(f["hub"]) == norm_hub]

    def get_summary_stats(self) -> Dict[str, Any]:
        return {
            "total_pricing_cards": len(self.pricing_cards),
            "total_features": len(self.feature_matrix),
            "total_plan_limits": len(self.plan_limits),
            "total_downgrade_rules": len(self.downgrade_impacts),
            "hubs_covered": list(set(f["hub"] for f in self.feature_matrix))
        }

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    cat = HubSpotCatalog()
    stats = cat.get_summary_stats()
    print("Catalog Loaded Successfully!")
    print(f"Engine: {'openpyxl' if HAS_OPENPYXL and cat.wb else 'Standard ZipFile XML (Zero Dependency)'}")
    print(f"Features: {stats['total_features']}")
    print(f"Pricing Cards: {stats['total_pricing_cards']}")
    print(f"Plan Limits: {stats['total_plan_limits']}")
    print(f"Downgrade Rules: {stats['total_downgrade_rules']}")
    print(f"Hubs: {stats['hubs_covered']}")
