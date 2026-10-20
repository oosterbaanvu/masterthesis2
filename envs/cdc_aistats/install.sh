#!/usr/bin/env bash
# Reproducible install of the isolated original-CDC environment (Python 3.9).
set -euo pipefail
cd "$(dirname "$0")"
uv venv --python 3.9 .venv -q --allow-existing
VIRTUAL_ENV=.venv uv pip install -r requirements.txt
# conformal-inference and conformal-data-cleaning at the pinned commits, without their
# autogluon[all] dependency (which would pull torch/fastai/spaCy).
VIRTUAL_ENV=.venv uv pip install --no-deps \
  "conformal-inference @ git+https://github.com/se-jaeger/conformal-inference@e25cb5938808360033201afc2ae567e5de3ad6c0"
VIRTUAL_ENV=.venv uv pip install --no-deps \
  "conformal-data-cleaning @ git+https://github.com/se-jaeger/conformal-data-cleaning@fd8a2126c9626099f3d45511fd05d30af8de6b64"
