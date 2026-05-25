# Anand Maratha — Interested Profiles Dashboard

Static dashboard that displays profiles from anandmaratha.com who have expressed
interest in **AMOL BACHHAV (MB112528)**. Hosted on GitHub Pages.

## Live site

https://amolbachhav30.github.io/anandMaratha/

Passcode: **`134393`**.

Profile data inside `index.html` is **AES-256-GCM encrypted** with the passcode
(PBKDF2-HMAC-SHA256, 250k iterations). Without the passcode the JSON is
unreadable even if someone downloads the file. Once unlocked, the decrypted
JSON is cached in the browser's `sessionStorage` so reloads don't re-prompt
within the same tab.

## Files

| Path | Purpose |
| --- | --- |
| `data/profiles.json` | Source of truth — profile list. Tag each entry with `source: "Anand Maratha"`. |
| `build.py` | Encrypts the JSON and renders `index.html`. |
| `index.html` | Built dashboard (committed so GitHub Pages can serve it). |
| `scripts/scrape_profile.py` | Scrapes a single anandmaratha.com profile URL → JSON. No login required (URL is self-authenticated). |
| `publish.sh` | One-shot: rebuild + commit + push. Run after manual JSON edits. |
| `.github/workflows/refresh.yml` | Old GitHub Actions scaffold — superseded by the cloud routine below. Disabled. |
| `requirements.txt` | Python deps for `build.py` (just `cryptography`). |
| `Secret.rtf` | Local-only credentials file. Gitignored. |

## Daily auto-refresh

Runs as a Claude Code remote routine: `https://claude.ai/code/routines/trig_01NaDxQ5HUrMaqzeVkAMvzs7`

- **Schedule:** `30 3 * * *` UTC = **9:00 AM IST daily**
- **What it does:** reads Gmail (via MCP) for new emails from anandmaratha.com,
  scrapes new profile URLs via `scripts/scrape_profile.py`, merges contact
  details from "Contact Details" emails, commits + pushes if anything changed.
- **No login or credential storage** — anandmaratha.com profile URLs carry the
  user's `rid` as an embedded auth token; they work via plain HTTP.

## Adding new data pipelines

`data/profiles.json` has a top-level `sources` array and a per-profile `source`
field. To add Hemant Pagar, Wedlock, or Anuroop pipelines later:

1. Build a similar scraper script under `scripts/`
2. Tag each entry it produces with `"source": "<pipeline name>"`
3. Add the pipeline name to the top-level `sources` array
4. The dashboard's source filter dropdown will populate automatically

## Pulling more Anand Maratha emails from other inboxes

The cloud routine only reads `amolbachhav@gmail.com` (the Gmail MCP is
authorized for one account). To fold in anandmaratha emails sent to other
addresses (e.g., `p.bachhav14@gmail.com`, `jv.patil29@gmail.com`), set up
auto-forwarding **once per source account**:

### One-time setup on each source Gmail (e.g., p.bachhav14@gmail.com)

1. Sign into the source Gmail in a browser.
2. **Settings → See all settings → Forwarding and POP/IMAP**.
3. Click *Add a forwarding address*. Enter `amolbachhav@gmail.com`. Click Next.
4. Gmail sends a verification email to `amolbachhav@gmail.com` with a code.
   Open that inbox, click the verify link.
5. Back in the source account, refresh **Forwarding and POP/IMAP**. The
   address is now eligible.
6. Go to **Filters and Blocked Addresses → Create a new filter**:
   - **From:** `*@anandmaratha.com`
   - Click *Create filter*
   - Tick: **Forward it to:** `amolbachhav@gmail.com`
   - Tick: **Also apply filter to matching conversations.** *(This forwards
     all existing anandmaratha emails — historical backfill happens immediately.)*
   - Click *Create filter*.

After step 6 the cloud routine starts seeing those forwarded emails on its
next 9 AM IST run. (Forwarded `from:` is still `*@anandmaratha.com`, so the
existing search filters keep working.)

### If you cannot access the other account

For accounts owned by family (e.g., `jv.patil29@gmail.com`), ask the owner to
follow steps 1–6 above. Or have them simply forward the relevant emails
manually — the routine matches on subject, not sender.

## Build locally

```bash
pip install -r requirements.txt
python3 build.py
open index.html
```

## Manual publish (e.g., after editing data/profiles.json by hand)

```bash
./publish.sh
```

Rebuilds, commits with today's date, pushes. Pages updates in ~30 seconds.

## Passcode

Hard-coded in `build.py` as `PASSWORD = "134393"`. To change it, edit that
constant and re-run `python3 build.py`. The passcode itself is never written
to disk in the repo — only the encrypted ciphertext + a random salt + IV
appear in `index.html`.
