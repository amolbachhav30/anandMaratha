#!/usr/bin/env python3
"""
Scrape marathashubhlagna.com (operated by Hemant Pagar) — Interests Sent + Received,
across Accepted / Declined / Pending. The listings only carry member IDs + dates +
messages; no photos or rich profile data. Each entry links to memprofile.php for
detail; that's a follow-up enrichment pass.

Credentials come from env vars HEMANT_USERNAME and HEMANT_PASSWORD.

Quirk: the listing PHP pages return "0 Message Found" unless the request includes
a Referer header pointing to mymatri.php. The scraper does a quick mymatri.php
warm-up fetch before each list request.

Usage:
    HEMANT_USERNAME=MV26675 HEMANT_PASSWORD=amol29641 \\
        python3 scripts/scrape_hemantpagar.py [--merge]
"""
import os, sys, re, html, json, time, datetime, argparse
import urllib.request, urllib.parse, http.cookiejar
from pathlib import Path

BASE = "https://www.marathashubhlagna.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")

# Six listing endpoints. The site uses different filenames per direction+status.
LISTS = [
    ("received", "accepted", "express_received_acceptedlist.php"),
    ("received", "declined", "express_received_declinedlist.php"),
    ("received", "pending",  "express_received_pendinglist.php"),
    ("sent",     "accepted", "express_sent_Acceptlist.php"),
    ("sent",     "declined", "express_sent_declinelist.php"),
    ("sent",     "pending",  "express_sent_pendinglist.php"),
]


def build_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [
        ("User-Agent", UA),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9"),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]
    return op


def login(opener, user: str, pw: str) -> None:
    opener.open(f"{BASE}/", timeout=20).read()
    payload = {
        "txtusername": user,
        "txtpassword": pw,
        "Submit3.x": "10",
        "Submit3.y": "10",
    }
    req = urllib.request.Request(
        f"{BASE}/memlogin_submit1.php",
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Referer", f"{BASE}/")
    body = opener.open(req, timeout=30).read().decode("utf-8", errors="replace")
    if "Logout" not in body:
        sys.exit("ERROR: Hemant Pagar login failed — check HEMANT_USERNAME/HEMANT_PASSWORD")


def fetch_with_referer(opener, url: str, referer: str) -> str:
    req = urllib.request.Request(url)
    req.add_header("Referer", referer)
    return opener.open(req, timeout=30).read().decode("utf-8", errors="replace")


_ENTRY_RE = re.compile(
    r"Sent to\s*:\s*"
    r"(?:<a[^>]*href=['\"]memprofile\.php\?id=([^'\"&]+)[^'\"]*['\"][^>]*>)?\s*([A-Z]{2,3}\d{3,8})"
    r".*?Sent Message\s*:\s*([^<]+?)\s*<br"
    r".*?Sent On\s*:\s*(\d{4}-\d{2}-\d{2}).*?"
    r"Status\s*:\s*(\w+)",
    re.S | re.I,
)

_RECEIVED_RE = re.compile(
    r"(?:From|Received from)\s*:\s*"
    r"(?:<a[^>]*href=['\"]memprofile\.php\?id=([^'\"&]+)[^'\"]*['\"][^>]*>)?\s*([A-Z]{2,3}\d{3,8})"
    r".*?(?:Received Message|Message)\s*:\s*([^<]+?)\s*<br"
    r".*?(?:Received On|Sent On|Date)\s*:\s*(\d{4}-\d{2}-\d{2}).*?"
    r"Status\s*:\s*(\w+)",
    re.S | re.I,
)


def parse_entries(page_html: str, direction: str, status_label: str) -> list:
    """Parse a single listing page into profile entries."""
    out = []
    # Both 'sent' and 'received' pages may use the same label patterns; try both.
    patterns = [_ENTRY_RE, _RECEIVED_RE] if direction == "received" else [_ENTRY_RE]
    seen = set()
    for pat in patterns:
        for m in pat.finditer(page_html):
            regno = (m.group(2) or "").strip()
            if not regno or regno in seen:
                continue
            seen.add(regno)
            msg = html.unescape(re.sub(r"\s+", " ", m.group(3)).strip())
            sent_on = m.group(4).strip()
            status = m.group(5).strip().lower()
            out.append({
                "regno": regno,
                "surname": "",  # not provided on listing
                "mgid": regno,  # MV/MS/etc. ID is the canonical ID here
                "source": "Maratha Shubh Lagna",
                "link": f"{BASE}/memprofile.php?id={regno}&action=ei",
                "match": 0,
                "gun": "",
                "gunBreak": "",
                "photos": [],
                "firstSeen": sent_on,
                "direction": direction,
                "status": status_label,  # use label from URL, more reliable
                "statusDate": sent_on,
                "message": msg,
                "details": [],
                "family": [],
                "expectation": [],
                "contact": None,
            })
    return out


def fetch_list(opener, direction: str, status: str, filename: str) -> list:
    url0 = f"{BASE}/{filename}"
    referer = f"{BASE}/mymatri.php"
    # Warm up Referer chain — visit mymatri.php first so the session state is right
    fetch_with_referer(opener, referer, f"{BASE}/authenticate.php?Action=Success")
    page = fetch_with_referer(opener, url0, referer)
    n_match = re.search(r"(\d+)\s+Message\s+Found", page)
    total = int(n_match.group(1)) if n_match else 0
    print(f"  {direction}-{status}: {total} total", flush=True)
    if total == 0:
        return []
    # Page count text looks like "[ 2 ] ... [ 23 ] of 23&nbsp; Next" — match "of N"
    pages_match = re.search(r"\]\s*of\s+(\d+)", page, re.I)
    n_pages = int(pages_match.group(1)) if pages_match else 1
    if n_pages == 1 and total > 5:
        # Fallback: divide total messages by entries-per-page (5)
        n_pages = (total + 4) // 5

    entries = parse_entries(page, direction, status)
    for p in range(2, n_pages + 1):
        time.sleep(0.8)
        url = f"{BASE}/{filename}?page={p}"
        page = fetch_with_referer(opener, url, referer)
        new = parse_entries(page, direction, status)
        entries.extend(new)
        print(f"    page {p}: +{len(new)}", flush=True)
    return entries


DETAILS_KEYS = {
    "Name","Surname","Gender","Age","Date of Birth","Marital Status",
    "Education","Edu Details","Occupation","Employed in","Income",
    "Sub Caste","Gothram","Star","Language","Place of Birth","Moonsign",
    "Time of Birth","Manglik/Dosham","Horos Match",
    "Height","Weight","Blood Group","Body Type","Complexion","Diet","Smoke","Drink",
    "I am Looking For","Hobbies","Interest",
}
FAMILY_KEYS = {
    "Family Values","Origin","Family Status","Type","Brothers","Sisters",
    "About Sibling's","Surname of Mama","Surname of Relatives",
}
EXPECT_KEYS = {
    "Age","Looking For","Complexion","Height","Eating habits","Sub Caste",
    "Education","Country Living in","Resident Status","Preference",
}


def _parse_cells(page_html: str) -> list:
    """Return list of stripped <td> contents."""
    text = re.sub(r'<script.*?</script>', '', page_html, flags=re.S)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.S)
    cells = re.findall(r'<td[^>]*>(.*?)</td>', text, re.S)
    out = []
    for c in cells:
        t = re.sub(r'<[^>]+>', ' ', c)
        t = re.sub(r'\s+', ' ', html.unescape(t)).strip()
        out.append(t)
    return out


def enrich_profile(opener, regno: str) -> dict:
    """Fetch memprofile.php for regno and return parsed fields + photos.
    Does NOT consume daily contact-detail credit."""
    url = f"{BASE}/memprofile.php?id={regno}&action=ei"
    req = urllib.request.Request(url)
    req.add_header("Referer", f"{BASE}/express_sent_pendinglist.php")
    page = opener.open(req, timeout=20).read().decode("utf-8", errors="replace")

    cells = _parse_cells(page)
    details, family, expectation = [], [], []
    seen_in_section = {"details": set(), "family": set(), "expect": set()}
    # Track which section we're in by detecting heading markers.
    # Headings appear as cells like 'Basic Information', 'Family Details', 'Partner Preference', etc.
    section = "details"
    for i in range(len(cells)):
        c = cells[i]
        cl = c.lower()
        if "family details" in cl:
            section = "family"; continue
        if "partner preference" in cl:
            section = "expect"; continue
        if any(kw in cl for kw in ["basic information","education and occupation",
                                    "socio religious","physical status","profile description",
                                    "hobies","hobbies"]):
            section = "details"; continue
        # k/v pair: c is label, cells[i+1] == ':', cells[i+2] is value
        if i + 2 < len(cells) and cells[i+1] == ":" and c and cells[i+2]:
            label, val = c, cells[i+2]
            if not (3 <= len(label) <= 30): continue
            if len(val) > 200: continue
            if section == "details" and label in DETAILS_KEYS and label not in seen_in_section["details"]:
                details.append([label, val]); seen_in_section["details"].add(label)
            elif section == "family" and label in FAMILY_KEYS and label not in seen_in_section["family"]:
                family.append([label, val]); seen_in_section["family"].add(label)
            elif section == "expect" and label in EXPECT_KEYS and label not in seen_in_section["expect"]:
                expectation.append([label, val]); seen_in_section["expect"].add(label)

    # Photos — any /memphoto*/...jpeg referenced (skip pics/, ui icons)
    photos = []
    seen_p = set()
    for m in re.finditer(r'src=["\']((?:/)?memphoto\d*/[^"\']+\.(?:jpe?g|png))["\']', page, re.I):
        u = m.group(1)
        if u.startswith("/"):
            u = BASE + u
        elif not u.startswith("http"):
            u = f"{BASE}/{u}"
        if u not in seen_p:
            seen_p.add(u); photos.append(u)

    # First name + surname
    name = next((v for k, v in details if k == "Name"), "")
    sur = next((v for k, v in details if k == "Surname"), "")
    full_name = (name + " " + sur).strip() if (name or sur) else ""

    return {
        "surname": full_name,
        "photos": photos,
        "details": details,
        "family": family,
        "expectation": expectation,
    }


def fetch_contact_details(opener, regno: str):
    """Hit address.php?stoid=<regno> — CONSUMES one daily credit unless already viewed.
    Returns parsed contact dict, or {"_quota_exceeded": True} when daily/annual limit hit."""
    url = f"{BASE}/address.php?stoid={regno}"
    req = urllib.request.Request(url)
    req.add_header("Referer", f"{BASE}/memprofile.php?id={regno}&action=ei")
    page = opener.open(req, timeout=20).read().decode("utf-8", errors="replace")

    # Page text: walk simple "label | value" pairs
    text = re.sub(r'<script.*?</script>', '', page, flags=re.S)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.S)
    text = re.sub(r'<[^>]+>', '|', text)
    text = html.unescape(text)
    tokens = [t.strip() for t in text.split('|') if t.strip()]

    info = {}
    for i in range(len(tokens) - 1):
        # Each visible label sits immediately above its value
        info[tokens[i].lower()] = tokens[i + 1]

    # Quota exceeded? page text changes (e.g., "you have reached your daily limit")
    if any("limit" in t.lower() and ("exceed" in t.lower() or "reached" in t.lower()) for t in tokens):
        return {"_quota_exceeded": True}

    # Combine phone + mobile, drop "--"
    phones_parts = []
    for k in ("phone", "mobile", "contact number"):
        v = info.get(k, "").strip()
        if v and v != "--":
            phones_parts.append(v)
    phones = ", ".join(phones_parts)

    name_parts = []
    if info.get("name"): name_parts.append(info["name"])
    # Father name often holds the full family name
    if info.get("father name"): name_parts.append(f"(daughter of {info['father name']})")
    name = " ".join(name_parts).strip()

    quota_today = info.get("total views today", "")
    quota_total = info.get("overall contact balance", "")

    if not (name or info.get("address") or phones or info.get("email")):
        return {"_raw": page[:2000]}

    return {
        "name": name,
        "address": info.get("address", "").strip(),
        "phones": phones,
        "email": info.get("email", "").strip(),
        "_quota_today": quota_today,
        "_quota_total": quota_total,
    }


def merge_into_db(profiles: list, db_path: Path) -> tuple:
    db = json.loads(db_path.read_text(encoding="utf-8"))
    by_key = {(p.get("source"), p.get("regno")): p for p in db["profiles"]}
    added = updated = 0
    for prof in profiles:
        key = (prof["source"], prof["regno"])
        existing = by_key.get(key)
        if existing:
            prof["firstSeen"] = existing.get("firstSeen", prof["firstSeen"])
            if existing.get("contact"):
                prof["contact"] = existing["contact"]
            for i, p in enumerate(db["profiles"]):
                if (p.get("source"), p.get("regno")) == key:
                    db["profiles"][i] = prof
                    break
            updated += 1
        else:
            db["profiles"].append(prof)
            added += 1
    sources = set(db.get("sources", []))
    sources.add("Maratha Shubh Lagna")
    db["sources"] = sorted(sources)
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added, updated


def cmd_scrape_lists(opener) -> list:
    all_profiles = []
    for direction, status, filename in LISTS:
        try:
            all_profiles.extend(fetch_list(opener, direction, status, filename))
        except Exception as e:
            print(f"  ! {direction}-{status} failed: {e}", flush=True)
        time.sleep(0.6)
    by_regno = {p["regno"]: p for p in all_profiles}
    return list(by_regno.values())


def cmd_enrich_all(opener, db_path: Path, only_missing: bool = True) -> int:
    db = json.loads(db_path.read_text(encoding="utf-8"))
    targets = [p for p in db["profiles"]
               if p.get("source") == "Maratha Shubh Lagna"
               and (not only_missing or not p.get("details"))]
    print(f"Enriching {len(targets)} profiles (only_missing={only_missing})", flush=True)
    n = 0
    for i, p in enumerate(targets, 1):
        try:
            enriched = enrich_profile(opener, p["regno"])
            # merge — keep statusDate/firstSeen/message/contact
            if enriched.get("surname"):
                p["surname"] = enriched["surname"]
            if enriched.get("photos"):
                p["photos"] = enriched["photos"]
            if enriched.get("details"):
                p["details"] = enriched["details"]
            if enriched.get("family"):
                p["family"] = enriched["family"]
            if enriched.get("expectation"):
                p["expectation"] = enriched["expectation"]
            n += 1
            if i % 10 == 0 or i == len(targets):
                print(f"  enriched {i}/{len(targets)} (last: {p['regno']} → {p['surname']})", flush=True)
        except Exception as e:
            print(f"  ! {p['regno']}: {e}", flush=True)
        time.sleep(0.6)
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def _profile_age(p: dict) -> float:
    """Extract age in years from a profile's details. Returns -1 if unknown."""
    for k, v in p.get("details", []):
        if k == "Age":
            m = re.search(r"(\d+)", v)
            if m:
                return float(m.group(1))
        if k == "Date of Birth":
            m = re.match(r"(\d{2})-(\w{3})-(\d{4})", v)
            if m:
                today = datetime.date.today()
                months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                try:
                    dob = datetime.date(int(m.group(3)), months.index(m.group(2)) + 1, int(m.group(1)))
                    return (today - dob).days / 365.25
                except ValueError:
                    pass
    return -1.0


def cmd_fetch_contacts(opener, db_path: Path, n: int) -> int:
    db = json.loads(db_path.read_text(encoding="utf-8"))
    candidates = [p for p in db["profiles"]
                  if p.get("source") == "Maratha Shubh Lagna"
                  and not p.get("contact")
                  and _profile_age(p) > 0]
    candidates.sort(key=_profile_age, reverse=True)  # oldest first
    candidates = candidates[:n]
    print(f"Fetching contacts for {len(candidates)} oldest profiles (quota cost = {len(candidates)})", flush=True)
    fetched = 0
    for p in candidates:
        try:
            c = fetch_contact_details(opener, p["regno"])
            if not c:
                print(f"  ! {p['regno']}: no contact returned", flush=True); continue
            if c.get("_quota_exceeded"):
                print(f"  ! quota exceeded at {p['regno']} — stopping", flush=True); break
            if c.get("_raw"):
                print(f"  ! {p['regno']}: unexpected page structure; saved raw[:200] = {c['_raw'][:200]!r}", flush=True); continue
            quota_today = c.get("_quota_today", "")
            quota_total = c.get("_quota_total", "")
            p["contact"] = {k: v for k, v in c.items() if not k.startswith("_")}
            p["status"] = "accepted"
            fetched += 1
            print(f"  ✓ {p['regno']} → {p['contact'].get('name','(no name)')}  [today {quota_today}, balance {quota_total}]", flush=True)
        except Exception as e:
            print(f"  ! {p['regno']}: {e}", flush=True)
        time.sleep(1.5)
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fetched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true",
                    help="Scrape listing pages + merge into profiles.json")
    ap.add_argument("--enrich", action="store_true",
                    help="Fetch memprofile.php for each entry and parse full profile (no quota cost)")
    ap.add_argument("--enrich-all", action="store_true",
                    help="Like --enrich but also re-fetch entries that already have details")
    ap.add_argument("--contacts", type=int, default=0, metavar="N",
                    help="Fetch contact details for the N oldest profiles missing contact "
                         "(CONSUMES N daily credits)")
    args = ap.parse_args()
    user = os.environ.get("HEMANT_USERNAME")
    pw = os.environ.get("HEMANT_PASSWORD")
    if not user or not pw:
        sys.exit("Set HEMANT_USERNAME and HEMANT_PASSWORD env vars")
    op = build_opener()
    print(f"Logging in as {user}...", flush=True)
    login(op, user, pw)
    print("  ✓ logged in", flush=True)
    # Warm up Referer chain once
    fetch_with_referer(op, f"{BASE}/mymatri.php", f"{BASE}/authenticate.php?Action=Success")

    repo = Path(__file__).resolve().parent.parent
    db_path = repo / "data" / "profiles.json"

    did_something = False
    if args.merge:
        profs = cmd_scrape_lists(op)
        added, updated = merge_into_db(profs, db_path)
        print(f"List scrape merged: {added} added, {updated} updated")
        did_something = True
    if args.enrich or args.enrich_all:
        n = cmd_enrich_all(op, db_path, only_missing=not args.enrich_all)
        print(f"Enriched {n} profiles")
        did_something = True
    if args.contacts > 0:
        n = cmd_fetch_contacts(op, db_path, args.contacts)
        print(f"Fetched {n} contacts (consumed {n} daily credits)")
        did_something = True
    if not did_something:
        print("Nothing to do. Pass --merge, --enrich, or --contacts N.")


if __name__ == "__main__":
    main()
