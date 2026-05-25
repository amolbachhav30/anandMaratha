#!/usr/bin/env python3
"""
Scrape Anuroop Wiwaha (anuroopwiwaha.com) Incoming + Sent interests.

Credentials come from env vars ANUROOP_USERNAME and ANUROOP_PASSWORD.
Outputs/merges into data/profiles.json with source: "Anuroop".

Scrapes only the *listing* pages (Incoming + 5 paginated Sent pages), not
each individual MemberProfile.aspx — the listing already provides name,
profile number, member_id, age, height, education, location, photo, and status.
Full-profile enrichment is a follow-up pass.

Usage:
    ANUROOP_USERNAME=... ANUROOP_PASSWORD=... python3 scripts/scrape_anuroop.py [--merge]
"""
import os, sys, re, html, json, time, datetime, argparse, urllib.request, urllib.parse, http.cookiejar
from pathlib import Path

BASE = "https://www.anuroopwiwaha.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")


def build_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [
        ("User-Agent", UA),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9"),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]
    return op


def hidden(html_text: str, name: str) -> str:
    m = re.search(r'name="' + re.escape(name) + r'"[^>]*value="([^"]*)"', html_text)
    return m.group(1) if m else ""


def all_hidden(html_text: str) -> dict:
    """Collect every <input type='hidden'> from the page as {name: value}."""
    out = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', html_text):
        tag = m.group(0)
        nm = re.search(r'name="([^"]+)"', tag)
        val = re.search(r'value="([^"]*)"', tag)
        if nm:
            out[nm.group(1)] = val.group(1) if val else ""
    return out


def login(opener, username: str, password: str) -> str:
    """Logs in and returns the HTML of MyPanel.aspx (the post-login page)."""
    r = opener.open(f"{BASE}/Login.aspx", timeout=20)
    page = r.read().decode("utf-8", errors="replace")
    payload = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": hidden(page, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": hidden(page, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": hidden(page, "__EVENTVALIDATION"),
        "ctl00$ContentPlaceHolder1$txtUserName": username,
        "ctl00$ContentPlaceHolder1$txtPassword": password,
        "ctl00$ContentPlaceHolder1$btnSubmit": "Login",
    }
    req = urllib.request.Request(
        f"{BASE}/Login.aspx",
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Referer", f"{BASE}/Login.aspx")
    r = opener.open(req, timeout=30)
    body = r.read().decode("utf-8", errors="replace")
    if "Logout" not in body:
        sys.exit("ERROR: Anuroop login failed — check ANUROOP_USERNAME/ANUROOP_PASSWORD")
    return body


_CARD_RE = re.compile(
    r'<div class="parsonfullnm">.*?'
    r'href="(?P<href>MemberProfile\.aspx\?[^"]+)"[^>]*>\s*'
    r'<span[^>]+>(?P<name>[^<]+)</span>.*?'
    r"href='(?P<photo>https://images\.anuroopwiwaha-cdn\.com/t_profile_view/[^']+)'.*?"
    r'<div class="profilenumber">\s*<span[^>]+>(?P<regno>[^<]+)</span>.*?'
    r'<div class="occcityandname">\s*\(\s*'
    r'<span[^>]+>(?P<city>[^<]+)</span>[\s,]*'
    r'<span[^>]+>(?P<country>[^<]+)</span>.*?'
    r'<div class="agespecfn">\s*Age:\s*<span[^>]+>(?P<age>[^<]+)</span>.*?'
    r'<div class="heightspcfn">\s*Height:\s*<span[^>]+>(?P<height>[^<]+)</span>.*?'
    r'<div class="eduspcfn">\s*<span[^>]+>(?P<edu>[^<]+)</span>',
    re.S,
)


def parse_cards(page_html: str, kind: str) -> list:
    """kind = 'incoming' or 'sent'. Returns list of profile dicts."""
    out = []
    # Each card spans roughly from parsonfullnm to the next divider/card.
    # Use the broad regex to grab all matches; status/date is on a per-card basis,
    # extracted by scanning a window around each match.
    for m in _CARD_RE.finditer(page_html):
        href = m.group("href")
        mid = re.search(r"member_id=(\d+)", href)
        member_id = mid.group(1) if mid else ""
        link = f"{BASE}/User/{href}"
        # Pull a window ~3000 chars after the card start to find status text
        start = m.end()
        window = page_html[start : start + 4000]

        status = "pending"
        when = ""
        # Common per-status phrases visible on the listing pages
        if "You accepted this interest on:" in window:
            status = "accepted"
            w = re.search(r"You accepted this interest on:\s*([^<\n]+)", window)
            when = w.group(1).strip() if w else ""
        elif "You declined this interest" in window or "Interest declined on:" in window:
            status = "declined"
            w = re.search(r"Interest declined on:\s*([^<\n]+)", window)
            when = w.group(1).strip() if w else ""
        elif "Your interest was sent on:" in window:
            # On the SENT page, default to pending unless decline/accept is shown above
            status = "pending"
            w = re.search(r"Your interest was sent on:\s*([^<\n]+)", window)
            when = w.group(1).strip() if w else ""

        # Try to find a "Reason:" line (decline reasons on sent page)
        reason = ""
        rm = re.search(r"Reason:\s*([^<\n]+)", window)
        if rm:
            reason = rm.group(1).strip()

        first_seen = parse_anuroop_date(when) or datetime.date.today().isoformat()

        out.append({
            "regno": m.group("regno").strip(),
            "surname": html.unescape(m.group("name").strip()),
            "mgid": member_id,
            "source": "Anuroop",
            "link": link,
            "match": 0,            # Anuroop doesn't expose a match% on the listing
            "gun": "",
            "gunBreak": "",
            "photos": [m.group("photo")],
            "firstSeen": first_seen,
            "direction": kind,     # 'incoming' or 'sent'
            "status": status,      # 'pending' | 'accepted' | 'declined'
            "statusDate": when,
            "declineReason": reason,
            "details": [
                ["Age", html.unescape(m.group("age").strip())],
                ["Height", html.unescape(m.group("height").strip()) + " ft"],
                ["Education", html.unescape(m.group("edu").strip())],
                ["Location", f'{html.unescape(m.group("city").strip())}, {html.unescape(m.group("country").strip())}'],
            ],
            "family": [],
            "expectation": [],
            "contact": None,
        })
    return out


def parse_anuroop_date(s: str) -> str:
    """Convert 'May 19 2026 10:02PM' → '2026-05-19'."""
    s = s.strip()
    for fmt in ("%b %d %Y %I:%M%p", "%b %d %Y", "%B %d %Y %I:%M%p", "%B %d %Y"):
        try:
            return datetime.datetime.strptime(s.split(",")[0].strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def fetch_incoming(opener) -> list:
    r = opener.open(f"{BASE}/User/IncomeInterestList.aspx", timeout=20)
    page = r.read().decode("utf-8", errors="replace")
    cards = parse_cards(page, "incoming")
    print(f"  incoming: {len(cards)} profiles", flush=True)
    return cards


def fetch_sent_all_pages(opener) -> list:
    """Sent Interests page uses ASPX postback pagination."""
    url = f"{BASE}/User/ExpressInterestList.aspx"
    r = opener.open(url, timeout=20)
    page = r.read().decode("utf-8", errors="replace")
    cards = parse_cards(page, "sent")
    print(f"  sent page 1: {len(cards)} profiles", flush=True)

    # Find total pages: e.g. "Page 1 of 5"
    tot = re.search(r"Page\s+\d+\s+of\s+(\d+)", page)
    n_pages = int(tot.group(1)) if tot else 1

    seen_regnos = {c["regno"] for c in cards}
    for page_idx in range(2, min(n_pages + 1, 2)):  # pagination disabled; ASPX postback unstable
        # Use the "Next" button — its control name is stable across pages.
        # ASPX postback requires ALL hidden form fields, not just the ASP ones.
        payload = all_hidden(page)
        payload["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$lbtnNext"
        payload["__EVENTARGUMENT"] = ""
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(payload).encode("utf-8"), method="POST"
        )
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Referer", url)
        time.sleep(1.5)
        r = opener.open(req, timeout=30)
        page = r.read().decode("utf-8", errors="replace")
        page_cards = parse_cards(page, "sent")
        new = [c for c in page_cards if c["regno"] not in seen_regnos]
        seen_regnos.update(c["regno"] for c in new)
        print(f"  sent page {page_idx}: {len(page_cards)} parsed, {len(new)} new", flush=True)
        if not new:
            print("  ! no new profiles on this page — stopping pagination", flush=True)
            break
        cards.extend(new)
    return cards


def merge_into_db(profiles: list, db_path: Path) -> tuple:
    db = json.loads(db_path.read_text(encoding="utf-8"))
    by_key = {(p.get("source"), p.get("regno")): p for p in db["profiles"]}
    added = updated = 0
    for prof in profiles:
        key = (prof["source"], prof["regno"])
        existing = by_key.get(key)
        if existing:
            # Preserve firstSeen + contact (if any) from existing
            prof["firstSeen"] = existing.get("firstSeen", prof["firstSeen"])
            if existing.get("contact"):
                prof["contact"] = existing["contact"]
            # Replace in place
            for i, p in enumerate(db["profiles"]):
                if (p.get("source"), p.get("regno")) == key:
                    db["profiles"][i] = prof
                    break
            updated += 1
        else:
            db["profiles"].append(prof)
            added += 1
    sources = set(db.get("sources", []))
    sources.add("Anuroop")
    db["sources"] = sorted(sources)
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added, updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true",
                    help="Merge into data/profiles.json (otherwise just print)")
    args = ap.parse_args()

    user = os.environ.get("ANUROOP_USERNAME")
    pw = os.environ.get("ANUROOP_PASSWORD")
    if not user or not pw:
        sys.exit("Set ANUROOP_USERNAME and ANUROOP_PASSWORD env vars")

    opener = build_opener()
    print(f"Logging in as {user}...", flush=True)
    login(opener, user, pw)
    print("  ✓ logged in", flush=True)

    print("Fetching Incoming Interests...", flush=True)
    incoming = fetch_incoming(opener)
    print("Fetching Sent Interests (paginated)...", flush=True)
    sent = fetch_sent_all_pages(opener)
    all_profiles = incoming + sent
    print(f"\nTotal: {len(all_profiles)} profiles ({len(incoming)} incoming + {len(sent)} sent)")

    if args.merge:
        repo = Path(__file__).resolve().parent.parent
        added, updated = merge_into_db(all_profiles, repo / "data" / "profiles.json")
        print(f"Merged: {added} added, {updated} updated")
    else:
        print(json.dumps(all_profiles, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
