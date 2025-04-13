# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring
# pylint: disable=invalid-name,too-few-public-methods,protected-access
import os
import tempfile

import pytest

from secblk.funds import Fund, funds_to_xlsx
from .test_tables import file_path_in_testdir

class TestFund:

    def test_fund_initialization(self):
        fund = Fund(isin="IT1234567890", value_number=100,
                    quantity=10, name="Test Fund", value=1000.0)
        assert fund.isin == "IT1234567890"
        assert fund.value_number == 100
        assert fund.quantity == 10
        assert fund.name == "Test Fund"
        assert fund.value == 1000.0

    def test_fund_equality(self):
        fund1 = Fund(isin="IT1234567890", value_number=100,
                     quantity=10, name="Test Fund", value=1000.0)
        fund2 = Fund(isin="IT1234567890", value_number=200,
                     quantity=10, name="Test Fund", value=1000.0)
        fund3 = Fund(isin="CH0987654321", value_number=200,
                     quantity=20, name="Another Fund", value=2000.0)
        assert fund1 == fund2
        assert fund1 != fund3
        assert fund2 != fund3

    def test_fund_add(self):
        fund1 = Fund(isin="IT1234567890", value_number=100,
                     quantity=10, name="Test Fund")
        fund2 = Fund(isin="IT1234567890", quantity = 1, name="Test Fund 2")
        fund_12 = fund1 + fund2
        assert fund_12.isin == "IT1234567890"
        assert fund_12.value_number == 100
        assert fund_12.quantity == 11
        assert fund_12.name == "Test Fund | Test Fund 2"
        assert fund_12.value is None

    def test_fund_add_different_isin(self):
        fund1 = Fund(isin="IT1234567890", value_number=100,
                     quantity=10, name="Test Fund")
        fund2 = Fund(isin="CH0987654321", quantity = 1, name="Test Fund 2")
        with pytest.raises(ValueError):
            _result = fund1 + fund2

    def test_fund_add_different_currency(self):
        fund1 = Fund(isin="CH1234567890", currency="CHF")
        fund2 = Fund(isin="CH0987654321", currency="EUR")
        with pytest.raises(ValueError):
            _result = fund1 + fund2

    def test_fund_as_list(self):
        fund = Fund(isin="IT1234567890", value_number=100,
                    quantity=10, name=["Test Fund", "a.k.a. TF"],
                    value=1000.0)
        assert fund.as_list() == [
            "IT1234567890", 100, 10, "Test Fund | a.k.a. TF", 1000.0, None, None
        ]

    def test_fund_as_abstracttable(self):
        fund = Fund(isin="IT1234567890", value_number=100,
                    quantity=10, name=["Test Fund"],
                    value=1000.0, country="IT", currency="EUR")
        header = fund.header
        for f in fund:
            table = f
            break
        assert list(table) == header
        assert list(table.values()) == [
            "IT1234567890",
            100,
            10,
            "Test Fund",
            1000.0,
            "IT",
            "EUR"
        ]


def test_funds_to_xlsx():
    fund1 = Fund(isin="IT1234567890", value_number=100,
                 quantity=10, name="Test Fund", value=1000.0)
    fund2 = Fund(isin="IT1234567890", value_number=200,
                 quantity=20, name=["Test Fund 2", "a.k.a. TF2"],
                 value=2000.0)
    fund3 = Fund(isin="CH0987654321", value_number=300,
                 quantity=30, name="Another Fund", value=3000.0)
    # pylint: disable=consider-using-with  # Managing the file based on test outcome
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx",
                                            dir=file_path_in_testdir("."))
    file_ok = False
    try:
        funds_to_xlsx([fund1, fund2, fund3], temp_file.name, name_width=40)
        assert os.path.exists(temp_file.name)
        assert (os.path.getsize(temp_file.name)
                == os.path.getsize(file_path_in_testdir("test_funds_to_xlsx_expect.xlsx")))
        file_ok = True
    finally:
        if os.path.exists(temp_file.name) and file_ok:
            os.remove(temp_file.name)
        else:
            print(f"Temporary file of failed test not deleted: {temp_file.name}")
    assert file_ok
