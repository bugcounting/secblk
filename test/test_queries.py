# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring
# pylint: disable=invalid-name,too-few-public-methods,protected-access
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from secblk.queries import Query, ICTaxQuery
from secblk.funds import Fund


class TestQuery:

    def test_default_year(self):
        """Test that default_year returns the previous year."""
        current_year = datetime.now().year
        assert Query.default_year() == current_year - 1

    @pytest.mark.parametrize("input_year, expected_year", [
        (None, datetime.now().year - 1),  # Default year
        (2018, 2018),                     # Specific year
    ])
    def test_year(self, input_year, expected_year):
        assert Query.year(input_year) == expected_year

    @patch("secblk.queries.Query.lookup")
    def test_lookup_all(self, mock_lookup):
        # Mock Query.lookup so that it returns a basic Fund object
        def Query_lookup(isin, _year):
            if isinstance(isin, str):
                return Fund(isin=isin)
            elif isinstance(isin, Fund):
                return isin
            return None
        mock_lookup.side_effect = Query_lookup
        # Test with ISIN strings
        funds = Query.lookup_all("ISIN1", "ISIN2", year=2023)
        assert len(funds) == 2
        assert funds[0].isin == "ISIN1"
        assert funds[1].isin == "ISIN2"
        # Test with a mix of ISIN strings and Fund objects
        fund_obj = Fund(isin="ISIN3")
        funds = Query.lookup_all("ISIN1", fund_obj, year=2023)
        assert len(funds) == 2
        assert funds[0].isin == "ISIN1"
        assert funds[1].isin == "ISIN3"
        # Test with invalid input
        funds = Query.lookup_all(True, year=2023)
        assert len(funds) == 0


class TestICTaxQuery:
    @patch("requests.post")
    def test_lookup_success(self, mock_post):
        """Test successful lookup with valid response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 1,
            "count": 1,
            "security": [
                {
                    "isin": "ISIN123",
                    "vn": "12345",
                    "institution": "Test Institution",
                    "countryName": "CH",
                    "currencyName": "CHF"
                }
            ]
        }
        mock_post.return_value = mock_response
        fund = ICTaxQuery.lookup("ISIN123", year=2016)
        assert fund is not None
        assert fund.isin == "ISIN123"
        assert fund.value_number == "12345"
        assert fund.name == "Test Institution"
        assert fund.country == "CH"
        assert fund.currency == "CHF"

    @patch("requests.post")
    def test_lookup_isin_mismatch(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "count": 1,
            "security": [
                {
                    "isin": "ISIN999",  # Different returned by query
                    "vn": "12345",
                    "institution": "Test Institution",
                    "countryName": "Switzerland",
                    "currencyName": "CHF"
                }
            ]
        }
        mock_post.return_value = mock_response
        fund = ICTaxQuery.lookup("ISIN123", year=2023)
        assert fund is None

    @patch("requests.post")
    def test_lookup_request_failure(self, mock_post):
        mock_response = MagicMock()
        # Simulate a request failure
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        fund = ICTaxQuery.lookup("ISIN123", year=2023)
        assert fund is None
