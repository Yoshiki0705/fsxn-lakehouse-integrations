#!/usr/bin/env bash
# =============================================================================
# upload-media-samples.sh - Upload unstructured sample data to FSxN
#
# Generates and uploads sample media files for Snowflake Directory Table and
# Snowpark UDF verification:
#   - Images: JPEG, PNG (small generated test images)
#   - Documents: PDF, DOCX (minimal valid files)
#   - Video: MP4 (minimal valid placeholder)
#
# Usage:
#   ./upload-media-samples.sh --access-point-alias <alias>
#   ./upload-media-samples.sh --nfs-mount /mnt/fsxn/vol1
#   ./upload-media-samples.sh --output-dir ./local-output
#
# Requirements: REQ-6 (Unstructured Data), REQ-7 (Snowpark UDF)
# =============================================================================

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMP_DIR="${SCRIPT_DIR}/../../.tmp/media-samples"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"

# Media paths on FSxN
MEDIA_PREFIX="media"
IMAGES_PATH="${MEDIA_PREFIX}/images"
DOCUMENTS_PATH="${MEDIA_PREFIX}/documents"
VIDEOS_PATH="${MEDIA_PREFIX}/videos"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Functions ---
log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Upload sample unstructured media files to FSxN for Snowflake verification.

Options:
  --access-point-alias ALIAS   S3 Access Point alias for upload
  --nfs-mount PATH             NFS mount path (e.g., /mnt/fsxn/vol1)
  --output-dir DIR             Local output directory (for testing)
  --region REGION              AWS region (default: ap-northeast-1)
  --force                      Overwrite existing files
  --help                       Show this help message

Examples:
  $(basename "$0") --access-point-alias fsxn-snowflake-ap-abc123-s3alias
  $(basename "$0") --nfs-mount /mnt/fsxn/vol1
  $(basename "$0") --output-dir ./sample-output
EOF
    exit 0
}

# --- Parse Arguments ---
ACCESS_POINT_ALIAS=""
NFS_MOUNT=""
OUTPUT_DIR=""
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --access-point-alias) ACCESS_POINT_ALIAS="$2"; shift 2 ;;
        --nfs-mount)          NFS_MOUNT="$2"; shift 2 ;;
        --output-dir)         OUTPUT_DIR="$2"; shift 2 ;;
        --region)             REGION="$2"; shift 2 ;;
        --force)              FORCE=true; shift ;;
        --help)               usage ;;
        *) log_error "Unknown option: $1"; usage ;;
    esac
done

# Validate: at least one destination must be specified
if [[ -z "$ACCESS_POINT_ALIAS" && -z "$NFS_MOUNT" && -z "$OUTPUT_DIR" ]]; then
    log_error "Must specify one of: --access-point-alias, --nfs-mount, or --output-dir"
    usage
fi

# =============================================================================
# Generate sample media files using Python
# =============================================================================
generate_media_files() {
    log_info "Generating sample media files in ${TEMP_DIR}..."
    mkdir -p "${TEMP_DIR}/${IMAGES_PATH}"
    mkdir -p "${TEMP_DIR}/${DOCUMENTS_PATH}"
    mkdir -p "${TEMP_DIR}/${VIDEOS_PATH}"

    python3 - "${TEMP_DIR}" <<'PYTHON_SCRIPT'
import sys
import os
import struct
import zlib
from pathlib import Path

output_base = Path(sys.argv[1])
images_dir = output_base / "media" / "images"
documents_dir = output_base / "media" / "documents"
videos_dir = output_base / "media" / "videos"

# =========================================================================
# 1. Generate JPEG images (minimal valid JPEG files)
# =========================================================================
def create_minimal_jpeg(filepath, width=64, height=64, color=(255, 0, 0)):
    """Create a minimal valid JPEG file with solid color."""
    import struct

    # JPEG uses a complex format; create a minimal valid structure
    # SOI marker
    data = b'\xff\xd8'
    # APP0 (JFIF header)
    app0 = b'\xff\xe0'
    jfif = b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    app0_len = struct.pack('>H', len(jfif) + 2)
    data += app0 + app0_len + jfif

    # DQT (Quantization Table) - simplified
    dqt = b'\xff\xdb'
    qt_data = b'\x00' + bytes([8] * 64)  # Table 0, all values = 8
    dqt_len = struct.pack('>H', len(qt_data) + 2)
    data += dqt + dqt_len + qt_data

    # SOF0 (Start of Frame)
    sof = b'\xff\xc0'
    sof_data = struct.pack('>BHHB', 8, height, width, 3)  # 8-bit, YCbCr
    sof_data += b'\x01\x11\x00'  # Y: 1x1, table 0
    sof_data += b'\x02\x11\x00'  # Cb: 1x1, table 0
    sof_data += b'\x03\x11\x00'  # Cr: 1x1, table 0
    sof_len = struct.pack('>H', len(sof_data) + 2)
    data += sof + sof_len + sof_data

    # DHT (Huffman Table) - minimal DC table
    dht = b'\xff\xc4'
    # DC luminance table (simplified)
    ht_data = b'\x00'  # DC table 0
    ht_data += b'\x01' + b'\x00' * 15  # 1 code of length 1
    ht_data += b'\x00'  # Symbol
    dht_len = struct.pack('>H', len(ht_data) + 2)
    data += dht + dht_len + ht_data

    # SOS (Start of Scan)
    sos = b'\xff\xda'
    sos_data = struct.pack('>B', 3)  # 3 components
    sos_data += b'\x01\x00'  # Y: DC=0, AC=0
    sos_data += b'\x02\x00'  # Cb
    sos_data += b'\x03\x00'  # Cr
    sos_data += b'\x00\x3f\x00'  # Spectral selection
    sos_len = struct.pack('>H', len(sos_data) + 2)
    data += sos + sos_len + sos_data

    # Scan data (minimal) + EOI
    data += b'\x00' * 32 + b'\xff\xd9'

    with open(filepath, 'wb') as f:
        f.write(data)

print("  Generating JPEG images...")
jpeg_configs = [
    ("product_photo_001.jpg", 128, 128, (200, 50, 50)),
    ("product_photo_002.jpg", 256, 192, (50, 200, 50)),
    ("landscape_tokyo_001.jpg", 320, 240, (50, 50, 200)),
    ("warehouse_scan_001.jpg", 160, 120, (100, 100, 100)),
    ("document_scan_001.jpg", 200, 280, (240, 240, 240)),
]
for fname, w, h, color in jpeg_configs:
    create_minimal_jpeg(images_dir / fname, w, h, color)
    print(f"    Created: {fname} ({w}x{h})")

PYTHON_SCRIPT

    log_ok "JPEG images generated"
}

# =============================================================================
# Generate PNG images
# =============================================================================
generate_png_files() {
    python3 - "${TEMP_DIR}" <<'PYTHON_SCRIPT'
import sys
import struct
import zlib
from pathlib import Path

output_base = Path(sys.argv[1])
images_dir = output_base / "media" / "images"

def create_png(filepath, width=64, height=64, r=0, g=128, b=255):
    """Create a valid PNG file with solid color."""
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)
        return struct.pack('>I', len(data)) + chunk + crc

    # PNG signature
    png = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    png += make_chunk(b'IHDR', ihdr_data)

    # IDAT chunk (image data)
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # Filter: None
        for x in range(width):
            raw_data += bytes([r, g, b])

    compressed = zlib.compress(raw_data)
    png += make_chunk(b'IDAT', compressed)

    # IEND chunk
    png += make_chunk(b'IEND', b'')

    with open(filepath, 'wb') as f:
        f.write(png)

print("  Generating PNG images...")
png_configs = [
    ("chart_revenue_2024.png", 200, 150, 30, 100, 200),
    ("diagram_architecture.png", 300, 200, 240, 240, 240),
    ("logo_company.png", 64, 64, 0, 120, 200),
    ("screenshot_dashboard.png", 320, 240, 50, 50, 80),
    ("icon_notification.png", 32, 32, 255, 165, 0),
]
for fname, w, h, r, g, b in png_configs:
    create_png(images_dir / fname, w, h, r, g, b)
    print(f"    Created: {fname} ({w}x{h})")

PYTHON_SCRIPT

    log_ok "PNG images generated"
}

# =============================================================================
# Generate PDF documents
# =============================================================================
generate_pdf_files() {
    python3 - "${TEMP_DIR}" <<'PYTHON_SCRIPT'
import sys
from pathlib import Path
from datetime import datetime

output_base = Path(sys.argv[1])
documents_dir = output_base / "media" / "documents"

def create_pdf(filepath, title, pages=3):
    """Create a minimal valid PDF file with text content."""
    # PDF structure: header, objects, xref, trailer
    objects = []

    # Object 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # Object 2: Pages
    page_refs = " ".join([f"{i+3} 0 R" for i in range(pages)])
    objects.append(
        f"2 0 obj\n<< /Type /Pages /Kids [{page_refs}] /Count {pages} >>\nendobj\n".encode()
    )

    # Object for font
    font_obj_num = 3 + pages * 2
    objects_to_add = []

    # Generate page objects and content streams
    for p in range(pages):
        page_num = p + 1
        page_obj_num = 3 + p
        content_obj_num = 3 + pages + p

        # Page object
        objects_to_add.append(
            f"{page_obj_num} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Contents {content_obj_num} 0 R "
            f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> >>\n"
            f"endobj\n"
        )

        # Content stream
        content = (
            f"BT /F1 16 Tf 72 720 Td ({title}) Tj ET\n"
            f"BT /F1 12 Tf 72 680 Td (Page {page_num} of {pages}) Tj ET\n"
            f"BT /F1 10 Tf 72 640 Td "
            f"(Generated for FSxN Lakehouse Integration Testing) Tj ET\n"
            f"BT /F1 10 Tf 72 600 Td "
            f"(Date: {datetime.now().strftime('%Y-%m-%d')}) Tj ET\n"
        )
        content_bytes = content.encode()
        objects_to_add.append(
            f"{content_obj_num} 0 obj\n"
            f"<< /Length {len(content_bytes)} >>\n"
            f"stream\n".encode() + content_bytes +
            f"\nendstream\nendobj\n".encode()
        )

    # Font object
    objects_to_add.append(
        f"{font_obj_num} 0 obj\n"
        f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        f"endobj\n"
    )

    # Build PDF
    pdf = b"%PDF-1.4\n"
    offsets = []

    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj if isinstance(obj, bytes) else obj.encode()

    for obj in objects_to_add:
        offsets.append(len(pdf))
        pdf += obj if isinstance(obj, bytes) else obj.encode()

    # Cross-reference table
    xref_offset = len(pdf)
    total_objects = len(offsets) + 1
    pdf += f"xref\n0 {total_objects}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()

    # Trailer
    pdf += f"trailer\n<< /Size {total_objects} /Root 1 0 R >>\n".encode()
    pdf += f"startxref\n{xref_offset}\n%%EOF\n".encode()

    with open(filepath, 'wb') as f:
        f.write(pdf)

print("  Generating PDF documents...")
pdf_configs = [
    ("quarterly_report_2024_Q1.pdf", "Quarterly Financial Report Q1 2024", 5),
    ("product_specification_v2.pdf", "Product Specification v2.0", 3),
    ("compliance_audit_2024.pdf", "Annual Compliance Audit 2024", 8),
    ("architecture_design.pdf", "System Architecture Design", 4),
    ("user_manual_v3.pdf", "User Manual Version 3.0", 6),
]
for fname, title, pages in pdf_configs:
    create_pdf(documents_dir / fname, title, pages)
    print(f"    Created: {fname} ({pages} pages)")

PYTHON_SCRIPT

    log_ok "PDF documents generated"
}

# =============================================================================
# Generate DOCX documents (minimal valid Office Open XML)
# =============================================================================
generate_docx_files() {
    python3 - "${TEMP_DIR}" <<'PYTHON_SCRIPT'
import sys
import zipfile
from pathlib import Path
from datetime import datetime

output_base = Path(sys.argv[1])
documents_dir = output_base / "media" / "documents"

def create_docx(filepath, title, paragraphs=5):
    """Create a minimal valid DOCX file (Office Open XML format)."""
    # DOCX is a ZIP file with XML content
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    word_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>'''

    # Build document body
    body_paragraphs = f'''<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>
      <w:r><w:t>{title}</w:t></w:r></w:p>'''

    for i in range(paragraphs):
        body_paragraphs += f'''
    <w:p><w:r><w:t>Paragraph {i+1}: Sample content for FSxN Lakehouse Integration testing. '''
        body_paragraphs += f'''Generated on {datetime.now().strftime("%Y-%m-%d")}.</w:t></w:r></w:p>'''

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body_paragraphs}
  </w:body>
</w:document>'''

    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels)
        zf.writestr('word/_rels/document.xml.rels', word_rels)
        zf.writestr('word/document.xml', document_xml)

print("  Generating DOCX documents...")
docx_configs = [
    ("meeting_notes_2024.docx", "Meeting Notes - Q1 2024 Planning", 8),
    ("project_proposal.docx", "Project Proposal: Data Lake Migration", 6),
    ("technical_review.docx", "Technical Review: Storage Architecture", 10),
]
for fname, title, paras in docx_configs:
    create_docx(documents_dir / fname, title, paras)
    print(f"    Created: {fname} ({paras} paragraphs)")

PYTHON_SCRIPT

    log_ok "DOCX documents generated"
}

# =============================================================================
# Generate MP4 video (minimal valid ftyp + moov + mdat)
# =============================================================================
generate_video_files() {
    python3 - "${TEMP_DIR}" <<'PYTHON_SCRIPT'
import sys
import struct
from pathlib import Path

output_base = Path(sys.argv[1])
videos_dir = output_base / "media" / "videos"

def create_minimal_mp4(filepath, duration_s=5):
    """Create a minimal valid MP4 file (ISO Base Media File Format)."""
    # MP4 is composed of boxes (atoms): ftyp, moov, mdat

    def make_box(box_type, data):
        """Create an MP4 box with type and data."""
        size = 8 + len(data)
        return struct.pack('>I', size) + box_type + data

    def make_full_box(box_type, version, flags, data):
        """Create a full box with version and flags."""
        full_data = struct.pack('>B3s', version, flags.to_bytes(3, 'big')) + data
        return make_box(box_type, full_data)

    # ftyp box (file type)
    ftyp_data = b'isom'  # major brand
    ftyp_data += struct.pack('>I', 0x200)  # minor version
    ftyp_data += b'isomiso2mp41'  # compatible brands
    ftyp = make_box(b'ftyp', ftyp_data)

    # moov box (movie header) - minimal structure
    timescale = 1000
    duration = duration_s * timescale

    # mvhd (movie header)
    mvhd_data = struct.pack('>I', 0)  # creation time
    mvhd_data += struct.pack('>I', 0)  # modification time
    mvhd_data += struct.pack('>I', timescale)  # timescale
    mvhd_data += struct.pack('>I', duration)  # duration
    mvhd_data += struct.pack('>I', 0x00010000)  # rate (1.0)
    mvhd_data += struct.pack('>H', 0x0100)  # volume (1.0)
    mvhd_data += b'\x00' * 10  # reserved
    # Matrix (identity)
    mvhd_data += struct.pack('>9I',
        0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
    mvhd_data += b'\x00' * 24  # pre-defined
    mvhd_data += struct.pack('>I', 2)  # next track ID
    mvhd = make_full_box(b'mvhd', 0, 0, mvhd_data)

    # trak box (track) - minimal video track
    # tkhd (track header)
    tkhd_data = struct.pack('>I', 0)  # creation time
    tkhd_data += struct.pack('>I', 0)  # modification time
    tkhd_data += struct.pack('>I', 1)  # track ID
    tkhd_data += struct.pack('>I', 0)  # reserved
    tkhd_data += struct.pack('>I', duration)  # duration
    tkhd_data += b'\x00' * 8  # reserved
    tkhd_data += struct.pack('>H', 0)  # layer
    tkhd_data += struct.pack('>H', 0)  # alternate group
    tkhd_data += struct.pack('>H', 0)  # volume
    tkhd_data += b'\x00' * 2  # reserved
    # Matrix (identity)
    tkhd_data += struct.pack('>9I',
        0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
    tkhd_data += struct.pack('>I', 320 << 16)  # width (fixed point)
    tkhd_data += struct.pack('>I', 240 << 16)  # height (fixed point)
    tkhd = make_full_box(b'tkhd', 0, 3, tkhd_data)  # flags=3 (enabled+in_movie)

    trak = make_box(b'trak', tkhd)
    moov = make_box(b'moov', mvhd + trak)

    # mdat box (media data) - minimal placeholder
    mdat_data = b'\x00' * 256  # placeholder media data
    mdat = make_box(b'mdat', mdat_data)

    with open(filepath, 'wb') as f:
        f.write(ftyp + moov + mdat)

print("  Generating MP4 video files...")
mp4_configs = [
    ("warehouse_walkthrough.mp4", 30),
    ("product_demo_short.mp4", 15),
    ("training_clip_001.mp4", 60),
]
for fname, duration in mp4_configs:
    create_minimal_mp4(videos_dir / fname, duration)
    print(f"    Created: {fname} (duration: {duration}s)")

PYTHON_SCRIPT

    log_ok "MP4 video files generated"
}

# =============================================================================
# Upload functions
# =============================================================================
upload_via_s3ap() {
    local alias="$1"
    local source_dir="$2"

    log_info "Uploading to S3 Access Point: ${alias}"
    log_info "  Source: ${source_dir}/${MEDIA_PREFIX}/"
    log_info "  Destination: s3://${alias}/${MEDIA_PREFIX}/"

    # Check if files already exist (idempotent)
    if [[ "$FORCE" != "true" ]]; then
        local existing
        existing=$(aws s3 ls "s3://${alias}/${IMAGES_PATH}/" --region "${REGION}" 2>/dev/null | wc -l || echo "0")
        if [[ "$existing" -gt 0 ]]; then
            log_warn "Files already exist at s3://${alias}/${IMAGES_PATH}/ (${existing} files)"
            log_warn "Use --force to overwrite. Skipping upload."
            return 0
        fi
    fi

    # Upload images
    log_info "  Uploading images..."
    aws s3 sync "${source_dir}/${IMAGES_PATH}/" "s3://${alias}/${IMAGES_PATH}/" \
        --region "${REGION}" --no-progress
    log_ok "  Images uploaded"

    # Upload documents
    log_info "  Uploading documents..."
    aws s3 sync "${source_dir}/${DOCUMENTS_PATH}/" "s3://${alias}/${DOCUMENTS_PATH}/" \
        --region "${REGION}" --no-progress
    log_ok "  Documents uploaded"

    # Upload videos
    log_info "  Uploading videos..."
    aws s3 sync "${source_dir}/${VIDEOS_PATH}/" "s3://${alias}/${VIDEOS_PATH}/" \
        --region "${REGION}" --no-progress
    log_ok "  Videos uploaded"
}

upload_via_nfs() {
    local mount_path="$1"
    local source_dir="$2"

    log_info "Uploading to NFS mount: ${mount_path}"

    # Verify NFS mount is accessible
    if [[ ! -d "$mount_path" ]]; then
        log_error "NFS mount path does not exist: ${mount_path}"
        exit 1
    fi

    # Check if files already exist (idempotent)
    if [[ "$FORCE" != "true" ]]; then
        if [[ -d "${mount_path}/${IMAGES_PATH}" ]] && \
           [[ $(ls -A "${mount_path}/${IMAGES_PATH}" 2>/dev/null | wc -l) -gt 0 ]]; then
            log_warn "Files already exist at ${mount_path}/${IMAGES_PATH}/"
            log_warn "Use --force to overwrite. Skipping upload."
            return 0
        fi
    fi

    # Create directories
    mkdir -p "${mount_path}/${IMAGES_PATH}"
    mkdir -p "${mount_path}/${DOCUMENTS_PATH}"
    mkdir -p "${mount_path}/${VIDEOS_PATH}"

    # Copy files
    log_info "  Copying images..."
    cp -v "${source_dir}/${IMAGES_PATH}/"* "${mount_path}/${IMAGES_PATH}/" 2>/dev/null || true
    log_ok "  Images copied"

    log_info "  Copying documents..."
    cp -v "${source_dir}/${DOCUMENTS_PATH}/"* "${mount_path}/${DOCUMENTS_PATH}/" 2>/dev/null || true
    log_ok "  Documents copied"

    log_info "  Copying videos..."
    cp -v "${source_dir}/${VIDEOS_PATH}/"* "${mount_path}/${VIDEOS_PATH}/" 2>/dev/null || true
    log_ok "  Videos copied"
}

upload_to_local() {
    local dest_dir="$1"
    local source_dir="$2"

    log_info "Copying to local directory: ${dest_dir}"

    mkdir -p "${dest_dir}/${IMAGES_PATH}"
    mkdir -p "${dest_dir}/${DOCUMENTS_PATH}"
    mkdir -p "${dest_dir}/${VIDEOS_PATH}"

    cp -r "${source_dir}/${IMAGES_PATH}/"* "${dest_dir}/${IMAGES_PATH}/"
    cp -r "${source_dir}/${DOCUMENTS_PATH}/"* "${dest_dir}/${DOCUMENTS_PATH}/"
    cp -r "${source_dir}/${VIDEOS_PATH}/"* "${dest_dir}/${VIDEOS_PATH}/"

    log_ok "Files copied to ${dest_dir}"
}

# =============================================================================
# Verification functions
# =============================================================================
verify_s3ap_upload() {
    local alias="$1"

    log_info "Verifying upload to S3 Access Point..."
    echo ""
    echo "  === Images (${IMAGES_PATH}/) ==="
    aws s3 ls "s3://${alias}/${IMAGES_PATH}/" --region "${REGION}" 2>/dev/null || \
        log_warn "  Could not list images"
    echo ""
    echo "  === Documents (${DOCUMENTS_PATH}/) ==="
    aws s3 ls "s3://${alias}/${DOCUMENTS_PATH}/" --region "${REGION}" 2>/dev/null || \
        log_warn "  Could not list documents"
    echo ""
    echo "  === Videos (${VIDEOS_PATH}/) ==="
    aws s3 ls "s3://${alias}/${VIDEOS_PATH}/" --region "${REGION}" 2>/dev/null || \
        log_warn "  Could not list videos"
    echo ""
}

verify_nfs_upload() {
    local mount_path="$1"

    log_info "Verifying upload to NFS mount..."
    echo ""
    echo "  === Images (${mount_path}/${IMAGES_PATH}/) ==="
    ls -la "${mount_path}/${IMAGES_PATH}/" 2>/dev/null || \
        log_warn "  Could not list images"
    echo ""
    echo "  === Documents (${mount_path}/${DOCUMENTS_PATH}/) ==="
    ls -la "${mount_path}/${DOCUMENTS_PATH}/" 2>/dev/null || \
        log_warn "  Could not list documents"
    echo ""
    echo "  === Videos (${mount_path}/${VIDEOS_PATH}/) ==="
    ls -la "${mount_path}/${VIDEOS_PATH}/" 2>/dev/null || \
        log_warn "  Could not list videos"
    echo ""
}

verify_local_output() {
    local dest_dir="$1"

    log_info "Verifying local output..."
    echo ""
    echo "  === Images (${dest_dir}/${IMAGES_PATH}/) ==="
    ls -la "${dest_dir}/${IMAGES_PATH}/" 2>/dev/null || \
        log_warn "  Could not list images"
    echo ""
    echo "  === Documents (${dest_dir}/${DOCUMENTS_PATH}/) ==="
    ls -la "${dest_dir}/${DOCUMENTS_PATH}/" 2>/dev/null || \
        log_warn "  Could not list documents"
    echo ""
    echo "  === Videos (${dest_dir}/${VIDEOS_PATH}/) ==="
    ls -la "${dest_dir}/${VIDEOS_PATH}/" 2>/dev/null || \
        log_warn "  Could not list videos"
    echo ""
}

# =============================================================================
# Main execution
# =============================================================================
main() {
    echo "============================================================"
    echo " FSxN Lakehouse - Unstructured Media Sample Upload"
    echo "============================================================"
    echo ""
    echo "  Target paths:"
    echo "    Images:    ${IMAGES_PATH}/ (JPEG, PNG)"
    echo "    Documents: ${DOCUMENTS_PATH}/ (PDF, DOCX)"
    echo "    Videos:    ${VIDEOS_PATH}/ (MP4)"
    echo ""

    # Step 1: Generate sample media files
    log_info "Step 1/3: Generating sample media files..."
    mkdir -p "${TEMP_DIR}"
    generate_media_files
    generate_png_files
    generate_pdf_files
    generate_docx_files
    generate_video_files
    echo ""

    # Step 2: Upload to destination
    log_info "Step 2/3: Uploading files..."
    if [[ -n "$ACCESS_POINT_ALIAS" ]]; then
        upload_via_s3ap "$ACCESS_POINT_ALIAS" "$TEMP_DIR"
    fi
    if [[ -n "$NFS_MOUNT" ]]; then
        upload_via_nfs "$NFS_MOUNT" "$TEMP_DIR"
    fi
    if [[ -n "$OUTPUT_DIR" ]]; then
        upload_to_local "$OUTPUT_DIR" "$TEMP_DIR"
    fi
    echo ""

    # Step 3: Verify upload
    log_info "Step 3/3: Verifying upload..."
    if [[ -n "$ACCESS_POINT_ALIAS" ]]; then
        verify_s3ap_upload "$ACCESS_POINT_ALIAS"
    fi
    if [[ -n "$NFS_MOUNT" ]]; then
        verify_nfs_upload "$NFS_MOUNT"
    fi
    if [[ -n "$OUTPUT_DIR" ]]; then
        verify_local_output "$OUTPUT_DIR"
    fi

    # Summary
    echo "============================================================"
    log_ok "Unstructured media sample upload complete!"
    echo "============================================================"
    echo ""
    echo "  Files generated:"
    echo "    - 5 JPEG images (product photos, scans)"
    echo "    - 5 PNG images (charts, diagrams, icons)"
    echo "    - 5 PDF documents (reports, specs, manuals)"
    echo "    - 3 DOCX documents (notes, proposals, reviews)"
    echo "    - 3 MP4 videos (walkthroughs, demos, training)"
    echo ""
    echo "  Total: 21 media files"
    echo ""
    echo "  Next steps:"
    echo "    1. Create Snowflake Directory Table stage (DIRECTORY=TRUE)"
    echo "    2. Run ALTER STAGE REFRESH to index files"
    echo "    3. Query Directory Table for file metadata"
    echo "    4. Generate Pre-signed URLs for file access"
    echo "    5. Apply Snowpark UDFs for media processing"
    echo ""

    # Cleanup temp files
    if [[ -n "$ACCESS_POINT_ALIAS" || -n "$NFS_MOUNT" ]]; then
        log_info "Cleaning up temp directory: ${TEMP_DIR}"
        rm -rf "${TEMP_DIR}"
    fi
}

main "$@"
