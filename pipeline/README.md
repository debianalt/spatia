# Flood Risk Pipeline

Automated pipeline: Sentinel-1 SAR → GEE export → GCS → H3 zonal stats → R2.

## Quick Start

```bash
# Dry run (show steps without executing)
python pipeline/run_flood_update.py --dry-run

# Full run (current extent only, ~20min)
python pipeline/run_flood_update.py --current

# Full run with historical recurrence (~4h)
python pipeline/run_flood_update.py --historical

# Reprocess local GeoTIFFs (skip GEE/GCS)
python pipeline/run_flood_update.py --skip-gee
```

## Pipeline Steps

| Step | Script | Description |
|------|--------|-------------|
| 1 | `gee_flood_detection.py` | Authenticate to GEE |
| 2 | `gee_flood_detection.py` | Launch S1 flood export to GCS |
| 3 | `gee_flood_detection.py` | Poll GEE tasks (60s interval, 4h timeout) |
| 4 | `download_gcs.py` | Download GeoTIFFs from `gs://spatia-satellite/flood/` |
| 5 | `process_to_h3.py` | H3 zonal stats → `hex_flood_risk.parquet` |
| 6 | `upload_to_r2.py` | Upload parquet to R2 (`neahub-public`) |

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEE_SERVICE_ACCOUNT_KEY` | GEE service account JSON key (path or string) | For GEE steps |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token with R2 write access | For R2 upload |

## GitHub Actions

Workflow: `.github/workflows/flood-update.yml`

- **Schedule**: 1st of each month, 06:00 UTC
- **Manual trigger**: Actions tab → "Update Flood Risk Layer" → Run workflow
- **Secrets needed**: `GEE_SERVICE_ACCOUNT_KEY`, `CLOUDFLARE_API_TOKEN`

### Pushing the workflow file

GitHub requires the `workflow` OAuth scope to push workflow files:

```bash
gh auth refresh -s workflow
git push origin master:main
```

## Troubleshooting

- **GEE timeout**: Increase `--days` to get more S1 images, or check [GEE task monitor](https://code.earthengine.google.com/tasks)
- **No GeoTIFFs in GCS**: Verify the service account has `storage.objects.list` on `spatia-satellite`
- **R2 upload fails**: Check `CLOUDFLARE_API_TOKEN` has R2 write permissions; ensure wrangler is installed
- **No hexagon grid**: Run `python pipeline/generate_h3_grid.py` first

## Individual Scripts

Each script can also run standalone:

```bash
# GEE export only
python pipeline/gee_flood_detection.py --current --wait

# Download from GCS only
python pipeline/download_gcs.py

# H3 processing only
python pipeline/process_to_h3.py --recurrence output/recurrence.tif --current output/current.tif --grid output/hexagons.geojson

# R2 upload only
python pipeline/upload_to_r2.py --file pipeline/output/hex_flood_risk.parquet --dest data/hex_flood_risk.parquet
```
