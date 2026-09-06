#!/usr/bin/env bash
# ==============================================================================
# Dr. Paper: Scheduled Weekly Ingestion Script
# Can be run via crontab or executed directly.
# ==============================================================================

set -euo pipefail

# Resolve script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Ensure logs directory exists
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ingest_$(date +'%Y%m%d').log"

echo "======================================================================" | tee -a "$LOG_FILE"
echo "🔬 [Dr. Paper] Starting Scheduled Ingestion: $(date -u '+%Y-%m-%d %H:%M:%S UTC')" | tee -a "$LOG_FILE"
echo "📂 Project root: $PROJECT_ROOT" | tee -a "$LOG_FILE"
echo "======================================================================" | tee -a "$LOG_FILE"

# Detect Python virtualenv
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "[ERROR] Python interpreter not found." | tee -a "$LOG_FILE"
    exit 1
fi

# Run ingestion pipeline (limit 10 candidates by default)
LIMIT="${1:-10}"
echo "[*] Executing: $PYTHON_BIN src/pipeline.py --ingest --limit $LIMIT" | tee -a "$LOG_FILE"

if "$PYTHON_BIN" src/pipeline.py --ingest --limit "$LIMIT" 2>&1 | tee -a "$LOG_FILE"; then
    echo "✅ [Dr. Paper] Ingestion completed successfully at $(date -u '+%Y-%m-%d %H:%M:%S UTC')" | tee -a "$LOG_FILE"
    exit 0
else
    EXIT_CODE=$?
    echo "❌ [Dr. Paper] Ingestion failed with exit code $EXIT_CODE at $(date -u '+%Y-%m-%d %H:%M:%S UTC')" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
