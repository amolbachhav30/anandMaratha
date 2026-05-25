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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    user = os.environ.get("HEMANT_USERNAME")
    pw = os.environ.get("HEMANT_PASSWORD")
    if not user or not pw:
        sys.exit("Set HEMANT_USERNAME and HEMANT_PASSWORD env vars")
    op = build_opener()
    print(f"Logging in as {user}...", flush=True)
    login(op, user, pw)
    print("  ✓ logged in", flush=True)

    all_profiles = []
    for direction, status, filename in LISTS:
        try:
            all_profiles.extend(fetch_list(op, direction, status, filename))
        except Exception as e:
            print(f"  ! {direction}-{status} failed: {e}", flush=True)
        time.sleep(0.6)

    # Dedupe by regno (keep latest)
    by_regno = {p["regno"]: p for p in all_profiles}
    all_profiles = list(by_regno.values())
    print(f"\nTotal unique: {len(all_profiles)}")

    if args.merge:
        repo = Path(__file__).resolve().parent.parent
        added, updated = merge_into_db(all_profiles, repo / "data" / "profiles.json")
        print(f"Merged: {added} added, {updated} updated")
    else:
        print(json.dumps(all_profiles[:3], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
