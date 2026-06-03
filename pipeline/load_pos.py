"""
Load POS transactions CSV into the Store Intelligence API.

Supports the Purplle POS CSV format with columns:
    order_id, order_date, order_time, store_id, product_id, brand_name, total_amount

Usage:
    python -m pipeline.load_pos \
        --csv pos_transactions.csv \
        --api-url http://localhost:8000

    # Override store_id if CSV uses a legacy POS ID (e.g. ST1008 → STORE_BLR_002):
    python -m pipeline.load_pos \
        --csv pos_transactions.csv \
        --api-url http://localhost:8000 \
        --store-id-map ST1008:STORE_BLR_002
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys

import requests

logger = logging.getLogger(__name__)

# Default POS store ID → internal store ID mapping.
# Covers the known mismatch: POS CSV uses "ST1008", API uses "STORE_BLR_002".
DEFAULT_STORE_ID_MAP: dict[str, str] = {
    "ST1008": "STORE_BLR_002",
}


def _parse_store_id_map(raw: list[str]) -> dict[str, str]:
    """Parse ['ST1008:STORE_BLR_002', ...] into a dict."""
    result = {}
    for entry in raw:
        parts = entry.split(":", 1)
        if len(parts) != 2:
            logger.warning("Ignoring invalid --store-id-map entry: %s (expected KEY:VALUE)", entry)
            continue
        result[parts[0].strip()] = parts[1].strip()
    return result


def load_csv(csv_path: str, api_url: str, store_id_map: dict[str, str]) -> None:
    transactions = []
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate columns exist
        expected = {"order_id", "order_date", "order_time", "store_id", "total_amount"}
        actual = set(reader.fieldnames or [])
        missing = expected - actual
        if missing:
            logger.error(
                "CSV is missing required columns: %s — found: %s",
                sorted(missing), sorted(actual)
            )
            sys.exit(1)

        for row in reader:
            raw_store_id = row["store_id"].strip()
            # Remap POS store ID → internal store ID
            mapped_store_id = store_id_map.get(raw_store_id, raw_store_id)

            # Combine order_date + order_time into ISO timestamp
            # Input format: "10-04-2026" + "12:15:05" → "2026-04-10T12:15:05"
            try:
                date_parts = row["order_date"].strip().split("-")  # DD-MM-YYYY
                iso_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
                timestamp = f"{iso_date}T{row['order_time'].strip()}+05:30"
            except (IndexError, KeyError):
                logger.warning("Skipping row %s — cannot parse date/time", row.get("order_id"))
                skipped += 1
                continue

            try:
                basket_value = float(row["total_amount"].strip())
                if basket_value <= 0:
                    logger.warning("Skipping row %s — zero or negative total_amount", row.get("order_id"))
                    skipped += 1
                    continue
            except ValueError:
                logger.warning("Skipping row %s — invalid total_amount", row.get("order_id"))
                skipped += 1
                continue

            transactions.append({
                "transaction_id": f"POS-{row['order_id'].strip()}",
                "store_id": mapped_store_id,
                "timestamp": timestamp,
                "basket_value_inr": basket_value,
            })

    if skipped:
        logger.warning("Skipped %d malformed rows", skipped)

    if not transactions:
        logger.error("No valid transactions found in %s", csv_path)
        sys.exit(1)

    logger.info(
        "Loaded %d transactions from CSV. Store ID map: %s",
        len(transactions), store_id_map or "none"
    )

    # Send in batches of 500
    batch_size = 500
    total_loaded = 0
    for i in range(0, len(transactions), batch_size):
        batch = transactions[i : i + batch_size]
        try:
            resp = requests.post(
                f"{api_url}/pos/ingest",
                json={"transactions": batch},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            total_loaded += result.get("loaded", 0)
            logger.info(
                "Batch %d: loaded=%d duplicates=%d",
                i // batch_size + 1,
                result.get("loaded", 0),
                result.get("duplicates", 0),
            )
        except Exception as exc:
            logger.error("Failed to load batch %d: %s", i // batch_size + 1, exc)
            sys.exit(1)

    print(f"Done. Total transactions loaded: {total_loaded} / {len(transactions)}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Load POS transactions CSV into the API")
    parser.add_argument("--csv", required=True, help="Path to POS transactions CSV")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument(
        "--store-id-map",
        nargs="*",
        default=[],
        metavar="POS_ID:STORE_ID",
        help="Remap POS store IDs to internal store IDs. E.g. ST1008:STORE_BLR_002",
    )
    args = parser.parse_args()

    # Merge CLI overrides on top of defaults
    store_id_map = {**DEFAULT_STORE_ID_MAP, **_parse_store_id_map(args.store_id_map)}

    load_csv(args.csv, args.api_url, store_id_map)


if __name__ == "__main__":
    main()

