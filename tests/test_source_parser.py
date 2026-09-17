import pytest

from scripts.extract import parse_csv


def test_parser_fails_closed_when_boe_columns_drift() -> None:
    with pytest.raises(ValueError, match="columns drifted"):
        parse_csv(b"DATE,WRONG\n", "snapshot", "https://bankofengland.co.uk")
