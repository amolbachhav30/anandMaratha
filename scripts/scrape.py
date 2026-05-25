#!/usr/bin/env python3
"""
Scrape interested profiles from anandmaratha.com and update data/profiles.json.

Credentials come from env vars AM_USERNAME and AM_PASSWORD.
Designed to run unattended in GitHub Actions.

STATUS: scaffold. The HTTP/HTML particulars of anandmaratha.com (login form
field names, interested-list URL, per-profile detail parsing) are NOT yet
filled in. Mark each FIXME below with the real selectors before relying on
this in production.
"""
import os, sys, json, re, datetime, time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright not installed. Run: pip install playwright && playwright install chromium")

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "profiles.json"

BASE = "https://www.anandmaratha.com"
LOGIN_URL = f"{BASE}/login.php"          # FIXME verify
INTERESTED_URL = f"{BASE}/interested.php" # FIXME verify — page that lists profiles who marked interest

USERNAME = os.environ.get("AM_USERNAME")
PASSWORD = os.environ.get("AM_PASSWORD")
MY_PROFILE_ID = os.environ.get("AM_MY_PROFILE_ID", "201913")
GENERATED_FOR = os.environ.get("AM_GENERATED_FOR", "AMOL BACHHAV (MB112528)")


def load_existing():
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {"generatedFor": GENERATED_FOR, "myProfileId": MY_PROFILE_ID, "profiles": []}


def login(page):
    if not USERNAME or not PASSWORD:
        sys.exit("AM_USERNAME / AM_PASSWORD env vars are required")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    # FIXME: replace selectors below with real form fields
    page.fill('input[name="username"]', USERNAME)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("networkidle")
    if "logout" not in page.content().lower():
        sys.exit("Login appears to have failed — check selectors and credentials")


def fetch_interested(page):
    """Return list of (regno, mgid, detail_url) tuples for profiles that marked interest in me."""
    page.goto(INTERESTED_URL, wait_until="networkidle")
    # FIXME: replace with the real listing parse
    out = []
    for a in page.query_selector_all('a[href*="details.php"]'):
        href = a.get_attribute("href") or ""
        m = re.search(r"mgid=(\d+)", href)
        if not m:
            continue
        mgid = m.group(1)
        regno_el = a.query_selector(".regno")  # FIXME
        regno = regno_el.inner_text().strip() if regno_el else f"MG{mgid}"
        out.append((regno, mgid, href if href.startswith("http") else BASE + "/" + href.lstrip("/")))
    return out


def parse_profile(page, url):
    """Open a profile detail page and return the profile dict matching profiles.json schema."""
    page.goto(url, wait_until="networkidle")
    html = page.content()
    # FIXME: real parsing. The schema we need:
    #   regno, surname, mgid, link, match, gun, gunBreak,
    #   photos[], firstSeen,
    #   details[ [k,v]... ], family[ [k,v]... ], expectation[ [k,v]... ],
    #   contact: { name, address, phones, email } | null
    today = datetime.date.today().isoformat()
    return {
        "regno": "",
        "surname": "",
        "mgid": "",
        "link": url,
        "match": 0,
        "gun": "",
        "gunBreak": "",
        "photos": [],
        "firstSeen": today,
        "details": [],
        "family": [],
        "expectation": [],
        "contact": None,
    }


def merge(existing_db, scraped_profiles):
    """Preserve firstSeen for profiles we've already seen; overlay everything else."""
    by_mgid = {p.get("mgid"): p for p in existing_db.get("profiles", [])}
    for p in scraped_profiles:
        prior = by_mgid.get(p["mgid"])
        if prior and prior.get("firstSeen"):
            p["firstSeen"] = prior["firstSeen"]
    existing_db["profiles"] = scraped_profiles
    return existing_db


def main():
    existing = load_existing()
    scraped = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (compatible; AnandMarathaSync/1.0)")
        page = context.new_page()
        login(page)
        listings = fetch_interested(page)
        print(f"Found {len(listings)} listings", flush=True)
        for regno, mgid, url in listings:
            try:
                prof = parse_profile(page, url)
                if prof.get("mgid"):
                    scraped.append(prof)
                time.sleep(1)
            except Exception as e:
                print(f"  ! skip {regno}: {e}", flush=True)
        browser.close()

    if not scraped:
        sys.exit("Scraper returned 0 profiles — refusing to overwrite. Check selectors.")

    merged = merge(existing, scraped)
    DATA_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {DATA_PATH} with {len(merged['profiles'])} profiles")


if __name__ == "__main__":
    main()
