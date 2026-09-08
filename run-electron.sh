#!/bin/bash
export LD_LIBRARY_PATH="$HOME/.local/bin:$LD_LIBRARY_PATH"
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/electron"
exec "$HOME/.local/bin/electron" . --no-sandbox "$@"
