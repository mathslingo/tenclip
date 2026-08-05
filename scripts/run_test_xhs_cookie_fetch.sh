#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
export PATH="${HOME}/miniconda3/envs/tenclip/bin:${HOME}/anaconda3/envs/tenclip/bin:${PATH}"
unset TENCLIP_XHS_NO_COOKIE
echo "python: $(command -v python3)"
python3 scripts/test_xhs_cookie_fetch.py 2>&1 | tee data/xhs_cookie_fetch_test.txt
echo "--- xhs_crab (curl + cookie) ---"
python3 xhs_crab.py 2>&1 | tee -a data/xhs_cookie_fetch_test.txt
