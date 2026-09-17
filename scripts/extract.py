"""Daily sterling exchange rates from the Bank of England IADB CSV endpoint."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from urllib.parse import urlencode

import httpx

from scripts.config import MAX_DOWNLOAD_BYTES, REQUEST_TIMEOUT, USER_AGENT
from scripts.snapshots import Snapshot, build_snapshot
from scripts.time_series import Observation

SERIES = {
    "XUDLBK67": ("BOE_FX_STERLING_ERI", "Sterling effective exchange rate index", "index"),
    "XUDLUSS": ("BOE_FX_GBP_USD", "US dollars per pound sterling", "ratio"),
    "XUDLERD": ("BOE_FX_GBP_EUR", "Euros per pound sterling", "ratio"),
}
ENDPOINT = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"


@dataclass(frozen=True)
class ExtractedData:
    observations: list[Observation]
    snapshots: list[Snapshot]
    catalog: dict[str, dict[str, Any]]
    releases: list[datetime]
    availability_by_key: dict[tuple[str, date], tuple[datetime, str, date | None]]
    min_lag_days: int = 0
    max_lag_days: int = 0
    inferred_lag_days: int | None = None


def parse_csv(
    body: bytes, snapshot_id: str, source_url: str
) -> tuple[
    list[Observation],
    dict[str, dict[str, Any]],
    dict[tuple[str, date], tuple[datetime, str, date | None]],
]:
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    if set(reader.fieldnames or ()) != {"DATE", *SERIES}:
        raise ValueError(f"BoE FX columns drifted: {reader.fieldnames}")
    observations: list[Observation] = []
    availability: dict[tuple[str, date], tuple[datetime, str, date | None]] = {}
    keys: set[tuple[str, date]] = set()
    for row in reader:
        reference = datetime.strptime(row["DATE"], "%d %b %Y").replace(tzinfo=UTC).date()
        for code, (series_id, _name, _unit) in SERIES.items():
            raw = row[code].strip()
            if not raw:
                continue
            key = (series_id, reference)
            if key in keys:
                raise ValueError(f"Duplicate BoE FX key {key}")
            keys.add(key)
            observations.append(Observation(series_id, reference, float(raw), snapshot_id))
            availability[key] = (
                datetime.combine(reference, time(23, 59), tzinfo=UTC),
                "official_date",
                reference,
            )
    if len(observations) < 1000:
        raise ValueError("BoE FX history unexpectedly short")
    latest = max(o.reference_date for o in observations)
    if (datetime.now(UTC).date() - latest).days > 10:
        raise ValueError(f"BoE FX latest date regressed to {latest}")
    catalog = {
        series_id: {
            "source_id": "boe_fx_daily",
            "name": name,
            "description": f"Raw daily {name.lower()} published in the Bank of England database; GBP is the base currency for bilateral rates.",
            "frequency": "daily",
            "unit": unit,
            "eco_group": "exchange_rates",
            "source_url": source_url,
            "last_publish_date": latest,
        }
        for _code, (series_id, name, unit) in SERIES.items()
    }
    return observations, catalog, availability


def collect() -> ExtractedData:
    fetched = datetime.now(UTC)
    params = {
        "csv.x": "yes",
        "Datefrom": "01/Jan/1990",
        "Dateto": fetched.strftime("%d/%b/%Y"),
        "SeriesCodes": ",".join(SERIES),
        "CSVF": "TN",
        "UsingCodes": "Y",
        "VPD": "Y",
        "VFD": "N",
    }
    url = f"{ENDPOINT}?{urlencode(params)}"
    with httpx.Client(
        timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        response = client.get(url)
        response.raise_for_status()
    body = response.content
    if not body or len(body) > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"Invalid BoE FX response size {len(body)}")
    digest = hashlib.sha256(body).hexdigest()
    observations, catalog, availability = parse_csv(body, digest, url)
    latest = max(o.reference_date for o in observations)
    snapshot = build_snapshot(
        "boe_fx_daily",
        url,
        "boe_fx_daily.csv",
        body,
        digest,
        response.headers.get("etag"),
        response.headers.get("last-modified"),
        fetched,
        latest,
    )
    return ExtractedData(observations, [snapshot], catalog, [], availability)
