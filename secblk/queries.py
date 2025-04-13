"""
This module defines static classes for querying funds data from web API.
Currently, it only includes a class for querying the Swiss ICTax API.
"""
from datetime import datetime
import logging
import time
from typing import Optional, Union

import requests

from .funds import Fund


class Query:
    """A static class for querying funds from a web API."""

    @classmethod
    def default_year(cls) -> int:
        """Returns the default year for querying funds, which is the latest completed year."""
        current_year = datetime.now().year
        return current_year - 1

    @classmethod
    def year(cls, year: Optional[int]) -> int:
        """Returns the year for querying funds. If year is None, use default_year()."""
        if year is None:
            return cls.default_year()
        return year

    @classmethod
    def lookup_all(cls, *args: Union[str, Fund], year: Optional[int]=None) -> list[Fund]:
        """Query a web API to get information about funds.
        
        Args:
            *args: The ISIN or Fund objects to query.
            year: The year for which to query the funds. If None (the
                  default), use default_year() to get the latest completed year.

        Returns:
            A list with Fund objects:
            - For each element of *args that is a valid ISIN, a Fund
              object for that fund that contains the queried data.
            - For each element of *args that is a Fund, a new Fund object
              that merges the input data with the queried data.
        """
        funds = []
        for fund_or_isin in args:
            time.sleep(1.0)
            fund = cls.lookup(fund_or_isin, year)
            if fund is not None:
                funds.append(fund)
        return funds

    @classmethod
    def lookup(cls, fund_or_isin: Union[str, Fund], year: Optional[int]=None) -> Optional[Fund]: # pylint: disable=unused-argument
        """Query a web API to get information about a single fund.
        
        Args:
            fund: The ISIN or Fund object to query.
            year: The year for which to query the fund. If None (the
                  default), use default_year() to get the latest completed year.

        Returns:
            A Fund object with the queried data, or None if the fund is not found.
        """
        return None


class ICTaxQuery(Query):
    """A class for querying the Swiss ICTax API."""

    _HEADERS = {'Content-Type': 'application/json'}
    _URL = "https://www.ictax.admin.ch/lsi/api/security"

    @classmethod
    def _payload(cls, isin: str, year: int) -> dict:
        """Returns the payload for the ICTax API request."""
        return {
            "max": 5,
            "fetch": 5,
            "offset": 0,
            "isin": isin,
            "year": str(year),
            "lang": "it"
        }

    @classmethod
    def lookup(cls, fund_or_isin: Union[str, Fund], year: Optional[int]=None) -> Optional[Fund]:
        if isinstance(fund_or_isin, Fund):
            base_fund = fund_or_isin
        elif isinstance(fund_or_isin, str):
            base_fund = Fund(isin=fund_or_isin)
        else:
            logging.error("Cannot query %s: not a Fund or ISIN", fund_or_isin)
            return None
        isin = base_fund.isin
        logging.info("Querying fund with ISIN: %s", isin)
        year = cls.year(year)
        payload = cls._payload(isin, year)
        headers = cls._HEADERS
        url = cls._URL
        logging.debug("Querying ICTax API for %s", payload)
        # Query the ICTax API for the fund data
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        # Check if the response is valid
        if resp.status_code != 200:
            logging.error("Error querying ICTax API for %s: response %d", isin, resp.status_code)
            return None
        # Parse the response as JSON
        resp_dict = resp.json()
        try:
            if len(resp_dict["security"]) > 1:
                logging.warning("Multiple entries for %s: using the first one", isin)
            fund_dict = resp_dict["security"][0]
            if fund_dict["isin"] != isin:
                logging.error("ISIN mismatch: %s != %s", isin, fund_dict["isin"])
                return None
            value_number = fund_dict["vn"]
            name = fund_dict["institution"]
            country = fund_dict["countryName"] if "countryName" in fund_dict else None
            currency = fund_dict["currencyName"] if "currencyName" in fund_dict else None
        except KeyError:
            logging.error("Error parsing response for %s: %s", isin, resp_dict)
            return None
        fund = Fund(
            isin=isin,
            value_number=value_number,
            name=name,
            country=country,
            currency=currency
        )
        try:
            fund = base_fund + fund
        except ValueError:
            logging.error("Cannot merge %s with %s. Returning only queried data.", base_fund, fund)
        return fund
