"""
Audit config.ts HEX_LAYER_REGISTRY expected columns against actual parquet
schemas on R2. Reports missing (in config but not in parquet) and extra
(in parquet but not in config) columns per analysis.

Usage: python pipeline/audit_parquet_schemas.py
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

import duckdb

R2_BASE = "https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev"
CONFIG_PATH = "src/lib/config.ts"


@dataclass
class Layer:
    analysis_id: str
    parquet_name: str
    cache_bust: str
    expected_vars: list[str]

    def province_url(self) -> str:
        return f"{R2_BASE}/data/{self.parquet_name}.parquet{self.cache_bust}"


def parse_cache_busts(ts_source: str) -> dict[str, str]:
    busts: dict[str, str] = {}
    match = re.search(r"const busts: Record<string, string> = \{([^}]+)\};", ts_source, re.S)
    if not match:
        return busts
    body = match.group(1)
    for name, bust in re.findall(r"(\w+)\s*:\s*'([^']+)'", body):
        busts[name] = bust
    return busts


def parse_hex_layer_registry(ts_source: str) -> list[Layer]:
    """Very small TS object parser for HEX_LAYER_REGISTRY entries."""
    busts = parse_cache_busts(ts_source)

    # Find HEX_LAYER_REGISTRY block
    reg_match = re.search(
        r"export const HEX_LAYER_REGISTRY[^=]*=\s*\{(.*?)\n\};",
        ts_source,
        re.S,
    )
    if not reg_match:
        raise RuntimeError("HEX_LAYER_REGISTRY not found")
    body = reg_match.group(1)

    layers: list[Layer] = []
    # Match each analysis entry: <id>: { ... variables: [...], parquet: '...', ... }
    # Use a greedy but bounded approach: find each top-level object
    depth = 0
    entries: list[tuple[str, str]] = []
    current_key: str | None = None
    start = 0
    i = 0
    while i < len(body):
        c = body[i]
        if depth == 0 and c not in "{, \t\n":
            key_match = re.match(r"(\w+)\s*:\s*\{", body[i:])
            if key_match:
                current_key = key_match.group(1)
                start = i + key_match.end() - 1
                i = start
                depth = 1
                i += 1
                continue
        if depth > 0:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0 and current_key:
                    entries.append((current_key, body[start : i + 1]))
                    current_key = None
        i += 1

    for analysis_id, obj_src in entries:
        parquet_match = re.search(r"parquet:\s*'([^']+)'", obj_src)
        if not parquet_match:
            continue
        parquet_name = parquet_match.group(1)
        if not parquet_name.startswith("sat_") and parquet_name not in {"overture_scores"}:
            continue
        # Skip overture_scores — not a sat analysis
        if parquet_name == "overture_scores":
            continue
        vars_block = re.search(r"variables:\s*\[(.*?)\]", obj_src, re.S)
        if not vars_block:
            continue
        var_cols = re.findall(r"col:\s*'([^']+)'", vars_block.group(1))
        layers.append(
            Layer(
                analysis_id=analysis_id,
                parquet_name=parquet_name,
                cache_bust=busts.get(parquet_name, ""),
                expected_vars=var_cols,
            )
        )
    return layers


def get_schema(con: duckdb.DuckDBPyConnection, url: str) -> list[str] | None:
    try:
        rows = con.execute(
            f"SELECT column_name FROM (DESCRIBE SELECT * FROM '{url}')"
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return None


def main() -> int:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        ts_source = f.read()
    layers = parse_hex_layer_registry(ts_source)
    print(f"Parsed {len(layers)} sat layers from config.ts\n")

    con = duckdb.connect(":memory:")
    con.execute("INSTALL httpfs; LOAD httpfs;")

    report = []
    missing_total = 0

    for layer in layers:
        url = layer.province_url()
        sys.stdout.write(f"  {layer.analysis_id:<26} ")
        sys.stdout.flush()

        actual = get_schema(con, url)
        if actual is None:
            print("UNREACHABLE")
            report.append({
                "analysis": layer.analysis_id,
                "parquet": url,
                "status": "unreachable",
            })
            continue

        actual_set = set(actual)
        expected_set = set(layer.expected_vars)
        missing = sorted(expected_set - actual_set)
        extra = sorted(actual_set - expected_set - {"h3index", "score"})

        status = "ok" if not missing else "mismatch"
        print(f"{status:<10} missing={len(missing):2d} extra={len(extra):2d}")

        if missing:
            missing_total += len(missing)
            print(f"     missing: {missing}")

        report.append({
            "analysis": layer.analysis_id,
            "parquet": url,
            "status": status,
            "missing": missing,
            "extra": extra,
            "actual_columns": actual,
        })

    out_path = "pipeline/output/schema_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print()
    print(f"Report: {out_path}")
    print(f"Total missing columns across all layers: {missing_total}")
    return 0 if missing_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
