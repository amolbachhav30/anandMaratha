# Anand Maratha — Interested Profiles Dashboard

Static dashboard that displays profiles from anandmaratha.com who have expressed
interest in **AMOL BACHHAV (MB112528)**. Hosted on GitHub Pages.

## Live site

`https://amolbachhav30.github.io/anandMaratha/`

The page is gated with passcode **`134393`** (kept in session storage once entered).
Data is base64-wrapped inside `index.html` to avoid casual indexing — this is a UX
gate, not strong protection. The repo is public, so anyone who downloads
`index.html` can decode the data offline.

## Files

| Path | Purpose |
| --- | --- |
| `data/profiles.json` | Source of truth — profile list. |
| `build.py` | Renders `data/profiles.json` → `index.html` with passcode gate. |
| `index.html` | Built dashboard. Committed so GitHub Pages can serve it. |
| `scripts/scrape.py` | **Scaffold** for scraping interested profiles. Not yet finished. |
| `.github/workflows/refresh.yml` | Scheduled daily refresh job. **Disabled** until scraper is finished. |
| `Secret.rtf` | Local-only credentials file. Gitignored. |

## Build locally

```bash
python3 build.py            # rewrites index.html
open index.html             # test the passcode gate
```

## Daily refresh — current state

The dashboard is updated by re-running `python3 build.py` after `data/profiles.json`
changes. The hard part is getting fresh JSON.

**Today:** Refresh happens manually via a Claude Desktop session that logs into
anandmaratha.com (Google OAuth) and pulls the interested-profiles list.

**Plan to automate:** the GitHub Actions workflow at `.github/workflows/refresh.yml`
is in place but **disabled**. Two blockers:

1. **`scripts/scrape.py` is a scaffold.** The login form selectors, the URL of
   the "interested profiles" listing page, and the per-profile detail parser
   are all marked `FIXME`. Filling them in requires inspecting a logged-in
   session.
2. **anandmaratha.com login is via Google OAuth.** Storing a Google password
   in GitHub secrets is not safe and Google blocks headless OAuth anyway.
   Realistic options:
   - **Local launchd cron** on the Mac, reusing the existing Chrome profile
     (no credentials in cloud). Only runs while the Mac is awake.
   - **Saved session cookies** uploaded as a secret, refreshed manually every
     few weeks when they expire. Brittle but cloud-runnable.

Pick one before re-enabling the schedule.

## Passcode

Hard-coded in `build.py` (`PASSWORD = "134393"`). To change it, edit that
constant and re-run `python3 build.py`. The hash is baked into `index.html`;
the plaintext is never shipped.
