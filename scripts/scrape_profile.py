#!/usr/bin/env python3
"""
Scrape a single anandmaratha.com profile detail page.

Usage:
    python3 scripts/scrape_profile.py <profile_url>
    python3 scripts/scrape_profile.py <profile_url> --merge      # patches data/profiles.json in place

The URL is the "View Full Profile" link from anandmaratha.com emails. It carries
the user's rid in its encoded query string, so it works without a login.

Outputs JSON matching the profiles.json schema (one profile dict).
"""
import sys, re, json, html, base64, urllib.parse, urllib.request, argparse
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

DETAILS_KEYS = ["Date Of Birth","Sex","Height","Caste","Education","Occupation",
                "Blood Group / Weight","Spectacle / Lens","Complexion","Gotra & Devak",
                "Birth Place","Mangal","Diet","Horo Details"]
FAMILY_KEYS  = ["Father","Mother","Brother","Sister","Mama","Relatives",
                "Parents Residing In","Native Place","Family Wealth"]
EXPECT_KEYS  = ["Age Difference Upto","Expected Height","Education","Occupation",
                "Expected Caste","Divorcee","Mangal","Preferred City"]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_url_params(url: str) -> dict:
    """Decode the base64 'a' or 'd' query param to extract mgid, rid, p (match%), g (gun)."""
    qs = urllib.parse.urlparse(url).query
    params = urllib.parse.parse_qs(qs)
    encoded = (params.get("a") or params.get("d") or [None])[0]
    if not encoded:
        return {}
    try:
        decoded = base64.b64decode(encoded + "==").decode("utf-8", errors="replace")
    except Exception:
        return {}
    inner = urllib.parse.parse_qs(decoded.split("?", 1)[-1] if "?" in decoded else decoded)
    return {k: v[0] for k, v in inner.items()}


def section_kv(section: str, known_keys: list) -> list:
    text = re.sub(r'<script.*?</script>', ' ', section, flags=re.S)
    text = re.sub(r'<style.*?</style>', ' ', text, flags=re.S)
    text = re.sub(r'<[^>]+>', '|', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).replace('|', ' | ')
    text = re.sub(r'(\| )+', ' | ', text).strip(' |')
    parts = [p.strip() for p in text.split('|') if p.strip()]
    out, i = [], 0
    while i < len(parts):
        token = parts[i].rstrip(':').strip()
        match = next((k for k in known_keys if k.lower() == token.lower()), None)
        if match and i + 1 < len(parts):
            val = parts[i + 1].strip()
            if not any(k.lower() == val.lower() for k in known_keys):
                out.append([match, val])
                i += 2
                continue
        i += 1
    return out


def extract_section(page: str, label: str) -> str:
    m = re.search(re.escape(label) + r'</h3>(.*?)(?=<h3|$)', page, re.S | re.I)
    return m.group(1) if m else ''


def parse(url: str) -> dict:
    page = fetch(url)
    params = parse_url_params(url)

    h1 = re.search(r'<h1[^>]*>\s*(MG\d+)\s*\((.+?)\)\s*</h1>', page)
    regno = h1.group(1) if h1 else ""
    surname = re.sub(r'\s+', ' ', h1.group(2)).strip() if h1 else ""

    photos = []
    gal = re.search(r'Photo gallery</h3>(.*?)<h3', page, re.S)
    if gal:
        for m in re.finditer(r'src=["\']([^"\']*girls/[^"\']+)["\']', gal.group(1)):
            u = m.group(1)
            if '/no_img' in u:
                continue
            if u.startswith('/'):
                u = 'https://www.anandmaratha.com' + u
            u = re.sub(r'\?v=\d+', '', u)
            if u not in photos:
                photos.append(u)

    try:
        match_pct = int(float(params.get('p', '') or '0'))
    except ValueError:
        match_pct = 0
    gun_raw = params.get('g', '') or ''
    if gun_raw:
        try:
            f = float(gun_raw)
            gun_str = str(int(f)) if f.is_integer() else str(f)
        except ValueError:
            gun_str = ""
    else:
        gun_str = ""
    gun = f"{gun_str}/36" if gun_str else ""

    # Try to find the gun breakdown text. Pattern from emails:
    #   "Varna 1/1, Vashya 1/2, Nakshtra ..., Nadi 8/8"
    gun_break = ""
    gb = re.search(r'Varna\s*\d[^<\n]*?Nadi\s*\d/\d', page)
    if gb:
        gun_break = re.sub(r'\s+', ' ', gb.group(0)).strip()

    return {
        "regno": regno,
        "surname": surname,
        "mgid": params.get("mgid", ""),
        "source": "Anand Maratha",
        "link": url,
        "match": match_pct,
        "gun": gun,
        "gunBreak": gun_break,
        "photos": photos,
        "details": section_kv(extract_section(page, "PROFILE DETAILS"), DETAILS_KEYS),
        "family":  section_kv(extract_section(page, "FAMILY BACKGROUND"), FAMILY_KEYS),
        "expectation": section_kv(extract_section(page, "EXPECTATION"), EXPECT_KEYS),
        "contact": None,
    }


def merge_into_db(profile: dict, db_path: Path) -> str:
    """Patch one profile into data/profiles.json. Preserves firstSeen, contact, and any
    pre-existing fields the scraper didn't fill. Returns a short status string."""
    db = json.loads(db_path.read_text(encoding="utf-8"))
    by_regno = {p["regno"]: p for p in db.get("profiles", [])}
    existing = by_regno.get(profile["regno"])
    if existing:
        # preserve fields the scrape can't get
        profile["firstSeen"] = existing.get("firstSeen", profile.get("firstSeen", ""))
        if existing.get("contact"):
            profile["contact"] = existing["contact"]
        # gunBreak lives in emails, not the profile page — keep existing if scrape was blank
        if not profile.get("gunBreak") and existing.get("gunBreak"):
            profile["gunBreak"] = existing["gunBreak"]
        # only overwrite a section if scrape returned non-empty
        for k in ("details", "family", "expectation"):
            if not profile[k] and existing.get(k):
                profile[k] = existing[k]
        if not profile["photos"] and existing.get("photos"):
            profile["photos"] = existing["photos"]
        # replace in place
        for i, p in enumerate(db["profiles"]):
            if p["regno"] == profile["regno"]:
                db["profiles"][i] = profile
                break
        status = f"updated {profile['regno']}"
    else:
        import datetime
        profile["firstSeen"] = datetime.date.today().isoformat()
        db.setdefault("profiles", []).append(profile)
        status = f"added {profile['regno']}"
    # keep sources catalog in sync
    sources = set(db.get("sources", []))
    if profile.get("source"):
        sources.add(profile["source"])
    db["sources"] = sorted(sources)
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--merge", action="store_true",
                    help="Merge into data/profiles.json instead of printing JSON")
    args = ap.parse_args()
    prof = parse(args.url)
    if args.merge:
        repo = Path(__file__).resolve().parent.parent
        print(merge_into_db(prof, repo / "data" / "profiles.json"))
    else:
        print(json.dumps(prof, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
