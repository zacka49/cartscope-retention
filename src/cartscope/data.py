from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
}


def load_transactions(path: Path) -> pd.DataFrame:
    """Load the UCI workbook, CSV, or Parquet using stable identifier types."""
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": str})
    elif suffix == ".csv":
        frame = pd.read_csv(path, dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": str})
    elif suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported input format: {suffix}")
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    return frame


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def demo_transactions() -> pd.DataFrame:
    """Small deterministic dataset containing purchases, credits, and anonymous rows."""
    rows: list[dict[str, object]] = []
    customers = ["10001", "10002", "10003", "10004", "10005", "10006"]
    starts = pd.to_datetime(["2011-01-05", "2011-01-18", "2011-02-02", "2011-03-10", "2011-07-01", "2011-09-12"])
    gaps = [[0, 25, 80, 175], [0, 44, 120], [0, 15, 61, 130], [0, 72, 145], [0, 20, 55], [0, 30]]
    for customer, start, offsets in zip(customers, starts, gaps, strict=True):
        for order_number, offset in enumerate(offsets, start=1):
            invoice = f"{customer[-2:]}{order_number:04d}"
            order_date = start + pd.Timedelta(days=offset)
            for line_number in range(2):
                rows.append(
                    {
                        "InvoiceNo": invoice,
                        "StockCode": f"SKU{line_number + 1:03d}",
                        "Description": ["Notebook set", "Desk organiser"][line_number],
                        "Quantity": line_number + 1,
                        "InvoiceDate": order_date + pd.Timedelta(minutes=line_number),
                        "UnitPrice": [8.5, 12.0][line_number],
                        "CustomerID": customer,
                        "Country": "United Kingdom",
                    }
                )
    rows.extend(
        [
            {
                "InvoiceNo": "C010001",
                "StockCode": "SKU001",
                "Description": "Notebook set",
                "Quantity": -1,
                "InvoiceDate": pd.Timestamp("2011-04-03"),
                "UnitPrice": 8.5,
                "CustomerID": "10001",
                "Country": "United Kingdom",
            },
            {
                "InvoiceNo": "900001",
                "StockCode": "SKU003",
                "Description": "Gift wrap",
                "Quantity": 1,
                "InvoiceDate": pd.Timestamp("2011-05-01"),
                "UnitPrice": 2.0,
                "CustomerID": pd.NA,
                "Country": "United Kingdom",
            },
        ]
    )
    return pd.DataFrame(rows)

