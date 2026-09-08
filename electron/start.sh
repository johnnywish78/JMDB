#!/bin/bash
cd "$(dirname "$0")"
exec ./node_modules/electron/dist/electron . --no-sandbox "$@"
