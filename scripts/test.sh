#!/usr/bin/env bash
set -e

echo "=== Python tests ==="
pytest -q

echo
echo "=== Electron tests ==="
npm --prefix electron test

echo
echo "ALL TESTS PASSED"
