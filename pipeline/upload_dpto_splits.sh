#!/bin/bash
# Upload dept splits with retry. Run WITHOUT VPN for best results.
# Usage: bash pipeline/upload_dpto_splits.sh

ok=0; fail=0; retry=0
for f in pipeline/output/sat_dpto/sat_*.parquet; do
  name=$(basename "$f")
  result=$(npx wrangler r2 object put "neahub/data/sat_dpto/$name" --file "$f" --remote 2>&1)
  if echo "$result" | grep -q "Upload complete"; then
    ok=$((ok+1))
  else
    # Retry once
    sleep 2
    result2=$(npx wrangler r2 object put "neahub/data/sat_dpto/$name" --file "$f" --remote 2>&1)
    if echo "$result2" | grep -q "Upload complete"; then
      ok=$((ok+1)); retry=$((retry+1))
    else
      fail=$((fail+1))
      echo "FAIL: $name"
    fi
  fi
  total=$((ok+fail))
  if [ $((total % 20)) -eq 0 ]; then echo "Progress: $total/238 ($ok OK, $fail FAIL, $retry retried)"; fi
done
echo "=== DONE: $ok OK, $fail FAIL, $retry retried ==="
