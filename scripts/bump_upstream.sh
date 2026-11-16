#!/usr/bin/env bash
# Bump the pinned upstream version: UPSTREAM + config.ini + control in lockstep.
# Usage: ./scripts/bump_upstream.sh 0.10.1
# After bumping, fill the new asset SHA256s into UPSTREAM, then run ./build.sh
set -euo pipefail

NEW_VERSION="${1:?usage: bump_upstream.sh <version>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

BASE="${NEW_VERSION/v/}"

# UPSTREAM
sed -i "s/^UPSTREAM_TAG=.*/UPSTREAM_TAG=v${BASE}/" UPSTREAM
sed -i "s/^UPSTREAM_VERSION=.*/UPSTREAM_VERSION=${BASE}/" UPSTREAM
sed -i "s/-v[0-9.]*\$/-v${BASE}/" UPSTREAM || true
for k in WEB_x86_64 WEB_aarch64 COLLECTOR_x86_64 COLLECTOR_aarch64; do
    sed -i "s/^SHA256_${k}=.*/SHA256_${k}=REPLACE_WITH_UPSTREAM_SHA256/" UPSTREAM
done

# config.ini
python3 - "$BASE" <<'PYEOF'
import json, sys
cfg = json.load(open("config.ini", encoding="utf-8"))
cfg["version"] = sys.argv[1]
with open("config.ini", "w", encoding="utf-8", newline="\n") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
PYEOF

# DEBIAN/control version
sed -i "s/^Version:.*/Version: ${BASE}/" DEBIAN/control

echo "bumped to ${BASE}"
echo "NEXT STEPS:"
echo "  1. pin the new release binary SHA256s in UPSTREAM (SHA256_WEB_*/SHA256_COLLECTOR_*)"
echo "  2. review upstream release notes for breaking changes (config schema)"
echo "  3. run ./build.sh && ./scripts/validate.py"
echo "  4. commit, tag v${BASE} and push to trigger CI"
