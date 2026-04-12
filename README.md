# Spatia — Territorial Intelligence Platform

Spatia is a zero-cost, reproducible platform for subnational territorial analysis. It combines satellite imagery, census data, and open geospatial datasets into composite indicators on a hexagonal grid (H3 resolution 9), validated through PCA diagnostics following OECD/UNDP methodology.

**Live instance**: [spatia.ar](https://www.spatia.ar) (Misiones province, Argentina — 320,000 hexagons, 27 analyses)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19543818.svg)](https://doi.org/10.5281/zenodo.19543818)

## Architecture

```
Google Earth Engine ──► GeoTIFF rasters ──► H3 zonal stats ──► PCA scoring ──► Parquet
                                                                                  │
                                              Browser (DuckDB-WASM) ◄── Cloudflare R2
                                                        │
                                              SvelteKit + MapLibre GL
```

The entire stack runs on free or near-free tiers: GEE (research), Cloudflare Pages/R2/D1, and GitHub Actions for CI/CD.

## Project Structure

```
pipeline/           Python scripts for GEE exports, raster processing,
                    H3 aggregation, PCA-validated scoring, and R2 uploads
  scoring.py        Shared scoring module (KMO, Bartlett, PCA, geometric mean)
  config.py         Global configuration (bbox, H3 resolution, thresholds)
  gee_*.py          Google Earth Engine export scripts
  process_*.py      Raster-to-H3 zonal statistics
  compute_*.py      Composite score computation
  model_*.py        Spatial regression models (PM2.5, deforestation)
  run_*.py          Pipeline orchestrators

src/                SvelteKit 5 frontend application
  lib/config.ts     Analysis registry and layer configuration
  lib/stores/       Reactive state (Svelte 5 runes)
  lib/components/   Map, analysis views, comparison charts
  routes/           Page routes (territorial map, EUDR compliance)

functions/api/      Cloudflare Pages Functions (EUDR check, terrain proxy)
db/                 D1 schema definitions
.github/workflows/  Automated pipeline updates (flood, deforestation, etc.)
```

## Data Sources

| Source | Coverage | License |
|--------|----------|---------|
| Google Earth Engine (Sentinel-1, Sentinel-2, MODIS, Landsat) | Global | [GEE Terms](https://earthengine.google.com/terms/) |
| JRC Global Surface Water v1.4 | Global, 1984-2021 | CC BY 4.0 |
| Hansen Global Forest Change v1.12 | Global, 2000-2023 | CC BY 4.0 |
| SoilGrids v2.0 (ISRIC) | Global | CC BY 4.0 |
| CHIRPS v2.0 | 50S-50N, 1981-present | Public domain |
| ERA5-Land (ECMWF/Copernicus) | Global | Copernicus License |
| VIIRS Nighttime Lights | Global | Public domain |
| Overture Maps Foundation | Global | ODbL |
| INDEC Census 2022 | Argentina | Public |
| MapBiomas | South America | CC BY 4.0 |

## Scoring Methodology

All composite scores follow the same validated pipeline:

1. **Percentile rank** each indicator (0-100)
2. **Correlation diagnostics** — flag pairs with |r| > 0.70
3. **KMO/Bartlett tests** — verify sampling adequacy (KMO > 0.50)
4. **PCA** (varimax rotation) — confirm dimensionality
5. **Variable selection** — drop redundant indicators
6. **Geometric mean** (floor = 1.0) — OECD Handbook / UNDP HDI style

The `--diagnostics` flag on `compute_satellite_scores.py` outputs full PCA results as JSON for each analysis.

## Quick Start

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for a step-by-step guide with example data instructions.

## Setup

### Pipeline (Python)

```bash
pip install -r pipeline/requirements.txt

# Authenticate to Google Earth Engine
earthengine authenticate

# Run a pipeline (example: flood risk)
python pipeline/run_flood_update.py --skip-gee  # with local rasters
python pipeline/run_flood_update.py --current    # full run with GEE
```

### Frontend (Node.js)

```bash
npm install
npm run dev       # local development at localhost:5173
npm run build     # static build
```

### Environment Variables

See [.env.example](.env.example) for a full template.

| Variable | Purpose |
|----------|---------|
| `GEE_SERVICE_ACCOUNT_KEY` | GEE service account JSON (for CI) |
| `CLOUDFLARE_API_TOKEN` | R2/D1 access (for deployment) |
| `EE_CLIENT_ID` | Earth Engine OAuth client ID (for Drive downloads) |
| `EE_CLIENT_SECRET` | Earth Engine OAuth client secret (for Drive downloads) |

## Citation

If you use Spatia in your research, please cite:

```bibtex
@software{gomez2026nealab,
  title={nealab: A Zero-Cost Platform for Subnational Territorial Intelligence},
  author={Gomez, R.E.},
  year={2026},
  doi={10.5281/zenodo.19543818},
  url={https://github.com/debianalt/nealab},
  license={AGPL-3.0}
}
```

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** — see [LICENSE](LICENSE). The AGPL additionally requires that any modified version made available over a network must also be released in source form, ensuring that Spatia remains a commons even when offered as a web service.
