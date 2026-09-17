# collector_boe_fx_uk

Standalone collector for three official daily Bank of England IADB series: sterling effective exchange-rate index (`XUDLBK67`), US dollars per pound (`XUDLUSS`) and euros per pound (`XUDLERD`). It stores 27,831 raw observations from 1990-01-02 through 2026-09-16; it does not calculate monthly means or returns.

Market observations use `official_date` at the end of their stated reference date. Quote direction is retained in metadata and never inverted.

## Install and run (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
Copy-Item .env.example .env
pytest -q
python main.py
```

Set `COLLECTOR_DB_URL` and allow the Bank of England IADB endpoint. Databricks is optional via `.[databricks]`. Source smoke: `python -c "from scripts.extract import collect; x=collect(); print(len(x.catalog), len(x.observations))"`.

See [METHODOLOGY.md](METHODOLOGY.md) and [POINT_IN_TIME.md](POINT_IN_TIME.md).
