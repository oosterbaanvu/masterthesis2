#!/usr/bin/env bash
# Fetch the original dBoost (GPL-3.0) at a pinned commit into envs/dboost/src (git-ignored).
# dBoost is pure Python 3 (standard library only for the gaussian/histogram models), so it runs with
# the system/main interpreter in a separate process; it is never imported by the framework.
set -euo pipefail
cd "$(dirname "$0")"
COMMIT=a47cb564e900c3e5220413f810e810b00046d561
if [ ! -d src/.git ]; then git clone -q https://github.com/cpitclaudel/dBoost.git src; fi
git -C src fetch -q origin "$COMMIT" 2>/dev/null || true
git -C src checkout -q "$COMMIT"
echo "dBoost at $(git -C src rev-parse HEAD)"
