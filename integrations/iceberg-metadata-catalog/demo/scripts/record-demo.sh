#!/bin/bash
# =============================================================================
# Record Demo with asciinema
# =============================================================================
# Creates a terminal recording of the full demo for blog embedding.
#
# Usage:
#   ./record-demo.sh
#
# Output:
#   ../docs/assets/demo-recording.cast (asciinema v2 format)
#
# After recording:
#   - Upload to asciinema.org: asciinema upload ../docs/assets/demo-recording.cast
#   - Or convert to GIF: agg ../docs/assets/demo-recording.cast demo.gif
#   - Or embed in blog: <script src="https://asciinema.org/a/XXXXX.js"></script>
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="${SCRIPT_DIR}/../docs/assets"
RECORDING="${ASSETS_DIR}/demo-recording.cast"

mkdir -p "${ASSETS_DIR}"

echo "═══════════════════════════════════════════════════"
echo " Recording demo to: ${RECORDING}"
echo " Press Ctrl+D or type 'exit' when done."
echo "═══════════════════════════════════════════════════"
echo ""
echo "Run this inside the recording:"
echo "  ./run-demo.sh --ap-alias <AP_ALIAS> --skip-deploy"
echo ""

asciinema rec \
  --title "Iceberg Metadata Catalog — Full Demo (42s)" \
  --cols 100 \
  --rows 35 \
  --idle-time-limit 3 \
  "${RECORDING}"

echo ""
echo "Recording saved: ${RECORDING}"
echo ""
echo "Next steps:"
echo "  1. Upload:  asciinema upload ${RECORDING}"
echo "  2. GIF:     agg ${RECORDING} ${ASSETS_DIR}/demo.gif --theme monokai"
echo "  3. SVG:     svg-term --in ${RECORDING} --out ${ASSETS_DIR}/demo.svg"
