#!/bin/bash
# =============================================================================
# demo-record-session.sh — Record Demo Session with asciinema (P-4)
#
# Records the complete demo execution for async sharing with customers
# who couldn't attend the live session.
#
# Output: .cast file playable via asciinema player or embeddable in HTML
#
# Prerequisites:
#   - asciinema installed (brew install asciinema)
#   - run-demo.sh configured and tested
#
# Usage:
#   ./demo-record-session.sh --ap-alias <alias>
#   ./demo-record-session.sh --ap-alias <alias> --output my-demo.cast
#   ./demo-record-session.sh --upload  # Upload to asciinema.org after recording
#
# Duration: ~15-20 minutes (matches live demo)
# =============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

log() { echo -e "${GREEN}[REC]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# =============================================================================
# Parse arguments
# =============================================================================
AP_ALIAS=""
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
OUTPUT_FILE=""
UPLOAD=false
TITLE="FSx for ONTAP Iceberg Metadata Catalog — Customer Demo"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
  case $1 in
    --ap-alias) AP_ALIAS="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --output) OUTPUT_FILE="$2"; shift 2 ;;
    --upload) UPLOAD=true; shift ;;
    --title) TITLE="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 --ap-alias <FSx-S3-AP-alias> [options]"
      echo ""
      echo "Options:"
      echo "  --ap-alias <alias>   FSx S3 Access Point alias (required)"
      echo "  --region <region>    AWS region (default: ap-northeast-1)"
      echo "  --output <file>      Output .cast file path"
      echo "  --upload             Upload to asciinema.org after recording"
      echo "  --title <title>      Recording title"
      echo "  -h, --help           Show this help"
      echo ""
      echo "Sharing options after recording:"
      echo "  1. asciinema.org:  asciinema upload <file>.cast"
      echo "  2. HTML embed:     Use asciinema-player.js (see instructions below)"
      echo "  3. GIF export:     agg <file>.cast <file>.gif"
      exit 0
      ;;
    *) error "Unknown option: $1" ;;
  esac
done

# =============================================================================
# Validate prerequisites
# =============================================================================
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  Demo Recording Setup (asciinema)                           ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check asciinema
if ! command -v asciinema &> /dev/null; then
  warn "asciinema is not installed."
  echo ""
  echo "  Install options:"
  echo "    macOS:   brew install asciinema"
  echo "    Ubuntu:  sudo apt install asciinema"
  echo "    pip:     pip install asciinema"
  echo "    conda:   conda install -c conda-forge asciinema"
  echo ""
  echo "  After install, run this script again."
  exit 1
fi

log "✅ asciinema found: $(asciinema --version 2>/dev/null || echo 'installed')"

# Check run-demo.sh exists
if [[ ! -f "${SCRIPT_DIR}/run-demo.sh" ]]; then
  error "run-demo.sh not found in ${SCRIPT_DIR}"
fi

# Validate AP alias
if [[ -z "$AP_ALIAS" ]]; then
  error "Usage: $0 --ap-alias <FSx-S3-AP-alias-ext-s3alias>"
fi

# Set output filename
if [[ -z "$OUTPUT_FILE" ]]; then
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  OUTPUT_FILE="${SCRIPT_DIR}/../recordings/demo-${TIMESTAMP}.cast"
fi

# Create recordings directory
mkdir -p "$(dirname "$OUTPUT_FILE")"

log "Recording configuration:"
echo "  Title:    ${TITLE}"
echo "  Output:   ${OUTPUT_FILE}"
echo "  AP Alias: ${AP_ALIAS}"
echo "  Region:   ${REGION}"
echo ""

# =============================================================================
# Pre-recording checks
# =============================================================================
log "Pre-recording checks..."

# Verify AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
  error "AWS credentials not configured. Run 'aws configure' or set environment variables."
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
log "  AWS Account: ${ACCOUNT_ID}"
log "  Region: ${REGION}"

# Check terminal size (recommend 120x35 for good recording)
COLS=$(tput cols 2>/dev/null || echo 80)
ROWS=$(tput lines 2>/dev/null || echo 24)

if [[ $COLS -lt 100 ]]; then
  warn "Terminal width is ${COLS} columns. Recommend >= 120 for best recording."
  echo "  Resize your terminal or run: printf '\\e[8;35;120t'"
fi

log "  Terminal: ${COLS}x${ROWS}"
echo ""

# =============================================================================
# Start recording
# =============================================================================
log "Starting recording in 3 seconds..."
echo "  Press Ctrl+D or type 'exit' to stop recording."
echo ""
sleep 3

asciinema rec \
  --title "${TITLE}" \
  --idle-time-limit 5 \
  --command "${SCRIPT_DIR}/run-demo.sh --ap-alias ${AP_ALIAS} --region ${REGION} --skip-deploy" \
  "${OUTPUT_FILE}"

# =============================================================================
# Post-recording
# =============================================================================
echo ""
log "✅ Recording saved: ${OUTPUT_FILE}"
echo ""

# File info
if [[ -f "$OUTPUT_FILE" ]]; then
  FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
  log "  File size: ${FILE_SIZE}"
  log "  Playback:  asciinema play ${OUTPUT_FILE}"
fi

# Upload if requested
if [[ "$UPLOAD" == "true" ]]; then
  echo ""
  log "Uploading to asciinema.org..."
  asciinema upload "${OUTPUT_FILE}"
fi

# =============================================================================
# Sharing instructions
# =============================================================================
echo ""
echo -e "${BOLD}┌──────────────────────────────────────────────────────────────┐${NC}"
echo -e "${BOLD}│  Sharing Options                                             │${NC}"
echo -e "${BOLD}├──────────────────────────────────────────────────────────────┤${NC}"
echo "│                                                              │"
echo "│  1. asciinema.org (public/unlisted link):                    │"
echo "│     asciinema upload ${OUTPUT_FILE}                          │"
echo "│                                                              │"
echo "│  2. Self-hosted HTML embed:                                  │"
echo "│     <div id=\"demo\"></div>                                    │"
echo "│     <script src=\"asciinema-player.min.js\"></script>          │"
echo "│     <link rel=\"stylesheet\" href=\"asciinema-player.css\"/>     │"
echo "│     <script>                                                 │"
echo "│       AsciinemaPlayer.create('demo.cast',                    │"
echo "│         document.getElementById('demo'),                     │"
echo "│         {cols: 120, rows: 35, theme: 'monokai'});            │"
echo "│     </script>                                                │"
echo "│                                                              │"
echo "│  3. Convert to GIF (for slides/email):                       │"
echo "│     # Install: cargo install agg                             │"
echo "│     agg ${OUTPUT_FILE} demo.gif                              │"
echo "│                                                              │"
echo "│  4. Convert to SVG animation:                                │"
echo "│     # Install: pip install svg-term                          │"
echo "│     svg-term --in ${OUTPUT_FILE} --out demo.svg              │"
echo "│                                                              │"
echo -e "${BOLD}└──────────────────────────────────────────────────────────────┘${NC}"
echo ""
echo "  Recommended for customer sharing:"
echo "    • Live demo follow-up → asciinema.org unlisted link"
echo "    • Email attachment    → GIF (agg conversion)"
echo "    • Internal wiki       → HTML embed with asciinema-player"
echo "    • Presentation slides → GIF or SVG"
echo ""
