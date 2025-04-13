"""
This module defines a Fund class representing a financial fund
with attributes such as ISIN, value number, quantity, name(s), and
value. It includes methods for creating Fund instances from a table,
merging Fund instances, exporting Fund data to an XLSX file, and
generating a header for the Fund attributes.
"""
from __future__ import annotations
from dataclasses import dataclass, field as init_field, fields as enumerate_fields
import logging
import math
import re
import sys
from typing import Optional

from .tables import Parser, IntParser, FloatParser, AbstractTable, Table, tables_to_xlsx


@dataclass(init=False)
class Fund(AbstractTable):
    """A fund with ISIN number, value number, quantity, name(s), and value."""

    isin: str
    value_number: Optional[int] = None
    quantity: int = 0
    _name: list[str] = init_field(default_factory=list)
    value: Optional[float] = None
    country: Optional[str] = None
    currency: Optional[str] = None

    @classmethod
    def default_parsers(cls, thousand_separator: str, decimal_separator: str) -> dict[str, Parser]:
        """
        Return a dictionary with default parsers for the attributes of the Fund class.
        
        Args:
            thousand_separator: The character used as the thousand separator.
            decimal_separator: The character used as the decimal separator.
        
        Returns:
            A dictionary mapping attribute names to their respective parsers.
        """
        return {
            "isin": Parser(),
            "value_number": IntParser(thousand_separator=thousand_separator),
            "quantity": IntParser(thousand_separator=thousand_separator),
            "name": Parser(),
            "value": FloatParser(thousand_separator=thousand_separator,
                                 decimal_separator=decimal_separator),
            "country": Parser(),
            "currency": Parser()
        }

    def __init__(self,
                 isin: str,
                 value_number: Optional[int] = None,
                 quantity: int = 0,
                 name: Optional[str] = None,
                 value: Optional[float] = None,
                 country: Optional[str] = None,
                 currency: Optional[str] = None,
                 check_isin: bool = True) -> None:
        self.isin = isin
        if check_isin:
            isin_ok = re.match(
                r"^(?P<pre>.*)(?P<isin>[A-Z]{2}[A-Z0-9]{10})(?P<post>.*)$",
                isin
                )
            if isin_ok is None:
                raise TypeError(f"Invalid ISIN: {isin}")
            self.isin = isin_ok.group("isin")
            if isin_ok.group("pre") or isin_ok.group("post"):
                logging.warning(
                    "ISIN %s contains extra characters before or after the ISIN number %s",
                    isin, self.isin
                )
        self.value_number = value_number
        self.quantity = quantity
        self.value = value
        self.country = country
        self.currency = currency
        self._name = name
        self._iterated = False
        if self._name is None:
            self._name = []
        elif isinstance(self._name, str):
            self._name = [self._name]
        if not isinstance(self._name, list):
            raise TypeError("Name must be a string or a list of strings")

    @property
    def name(self) -> str:
        """Return the name of the fund as a string."""
        return " | ".join(self._name)

    def __eq__(self, other) -> bool:
        """Compare two Fund objects by their ISIN."""
        if not isinstance(other, Fund):
            return False
        return self.isin == other.isin

    def __hash__(self) -> int:
        """Hash the Fund object by its ISIN."""
        return hash(self.isin)

    def __add__(self, other: "Fund") -> "Fund":
        """
        Merge two Fund objects if they are compatible.
        
        Two funds are compatible if they have the same ISIN number,
        and the same value number and value, or if either of their 
        value number or value is None.
        
        The merge of two compatible funds is a Fund object with the same ISIN,
        value number, and value, the sum of their quantities, and the concatenation
        of the names.
        """
        if not isinstance(other, Fund):
            raise TypeError("Can only add Fund objects")
        if self != other:
            raise ValueError("Cannot add funds with different ISINs")
        if (self.value_number is not None
            and other.value_number is not None
            and self.value_number != other.value_number):
            raise ValueError("Cannot add funds with different value numbers")
        if (self.value is not None
            and other.value is not None
            and not math.isclose(self.value, other.quantity)):
            raise ValueError("Cannot add funds with different quantities")
        if (self.country is not None
            and other.country is not None
            and self.country != other.country):
            raise ValueError("Cannot add funds with different countries")
        if (self.currency is not None
            and other.currency is not None
            and self.currency != other.currency):
            raise ValueError("Cannot add funds with different currencies")
        isin = self.isin
        value_number = self.value_number or other.value_number
        quantity = self.quantity + other.quantity
        name = self._name + other._name
        value = self.value or other.value
        country=self.country or other.country
        currency=self.currency or other.currency
        return Fund(
            isin=isin,
            value_number=value_number,
            quantity=quantity,
            name=name,
            value=value,
            country=country,
            currency=currency
        )

    @classmethod
    def from_table(cls, table: Table) -> list[Fund]:
        """Create a list of Fund objects from a table."""
        funds = []
        for row in table:
            try:
                fund = cls(**row)
            except (TypeError, ValueError):
                print(f"Skipping invalid fund data: {row}", file=sys.stderr)
                continue
            funds.append(fund)
        return funds

    @property
    def header(self) -> list[str]:
        """Return a header with a fund's attribute names."""
        headers = ["ISIN", "Value Number", "Quantity", "Name", "Value", "Country", "Currency"]
        return headers

    def __iter__(self):
        self._iterated = False
        return self

    def __next__(self) -> dict[str, str]:
        """
        Return a dictionary of the fund's attribute -> value mapping (without type conversions).
        """
        if self._iterated:
            raise StopIteration
        self._iterated = True
        headers = self.header
        values = self.as_list()
        assert len(headers) == len(values)
        return dict(zip(headers, values))

    def as_list(self) -> list:
        """Return a list with the fund's attribute values (without type conversions)."""
        values = [getattr(self, field.name) if field.name != "_name" else self.name
                  for field in enumerate_fields(self)]
        return values


def funds_to_xlsx(funds: list[Fund], file_path: str, name_width: int) -> None:
    """
    Export a list of Fund instances to an XLSX file.

    Args:
        funds: List of Fund instances to export.
        file_path: Path to the output XLSX file.
        name_width: Width of the "Name" column in the XLSX file.
    """
    tables_to_xlsx(tables=funds, file_path=file_path,
                   sheet_name="Funds", widths={"Name": name_width})
