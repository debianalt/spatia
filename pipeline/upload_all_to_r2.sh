#!/bin/bash
# Upload all parquets + PMTiles to R2
# Run when network is stable: bash pipeline/upload_all_to_r2.sh

echo "=== Main parquets ==="
for f in pipeline/output/sat_*.parquet; do
  name=$(basename "$f")
  [[ "$name" == *dpto* || "$name" == *metadata* ]] && continue
  echo -n "$name: "
  npx wrangler r2 object put "neahub/data/$name" --file "$f" --remote 2>&1 | grep -q "Creating object" && echo "OK" || echo "FAIL"
done

echo ""
echo "=== Dept splits ==="
for f in pipeline/output/sat_dpto/sat_*.parquet; do
  name=$(basename "$f")
  echo -n "$name: "
  npx wrangler r2 object put "neahub/data/sat_dpto/$name" --file "$f" --remote 2>&1 | grep -q "Creating object" && echo "OK" || echo "FAIL"
done

echo ""
echo "=== Catastro PMTiles ==="
npx wrangler r2 object put neahub/tiles/catastro.pmtiles --file pipeline/output/catastro.pmtiles --remote 2>&1 | grep -q "Creating object" && echo "OK" || echo "FAIL"

echo ""
echo "Done."
