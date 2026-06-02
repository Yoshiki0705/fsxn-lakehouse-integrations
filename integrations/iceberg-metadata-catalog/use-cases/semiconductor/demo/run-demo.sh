#!/bin/bash
# Industry Demo Wrapper — delegates to shared demo-runner.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDUSTRY="$(basename "$(dirname "$SCRIPT_DIR")")"
exec "$(dirname "$SCRIPT_DIR")/../../_shared/demo-runner.sh" --industry "$INDUSTRY" "$@"
