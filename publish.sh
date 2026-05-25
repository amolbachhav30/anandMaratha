#!/usr/bin/env bash
# Rebuild index.html from data/profiles.json and push to GitHub.
# Run this after Claude Desktop updates data/profiles.json.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f data/profiles.json ]; then
  echo "data/profiles.json missing — nothing to publish." >&2
  exit 1
fi

python3 build.py

if [ -z "$(git status --porcelain data/profiles.json index.html)" ]; then
  echo "No changes in data/profiles.json or index.html — nothing to push."
  exit 0
fi

git add data/profiles.json index.html
git commit -m "Refresh $(date '+%Y-%m-%d %H:%M %Z')"
git push origin main

echo
echo "Pushed. Pages will rebuild in ~30s:"
echo "  https://amolbachhav30.github.io/anandMaratha/"
