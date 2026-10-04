#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${OUT_DIR:-paper_results}"

python adjudicate_and_plot.py \
  --scores combined_detailed_scores.csv \
  --reviews manual_review_decisions.csv \
  --mapping manual_review_mapping.csv \
  --out-dir "$OUT_DIR"

echo
echo "Cleaned metrics:"
echo "  $OUT_DIR/cleaned_condition_metrics.csv"
echo
echo "Paper figures:"
echo "  $OUT_DIR/*.pdf"
echo "  $OUT_DIR/*.png"
echo
echo "Unresolved review rows:"
python - "$OUT_DIR/unresolved_reviews.csv" <<'PY'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open(newline="", encoding="utf-8-sig") as f:
    count = sum(1 for _ in csv.DictReader(f))
print(count)
PY
