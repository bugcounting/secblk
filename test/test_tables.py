# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring
# pylint: disable=invalid-name,too-few-public-methods,protected-access
import os
import tempfile

import pandas as pd
import pytest

from secblk.tables import (
    TableSpec, Parser, IntParser, FloatParser, Table,
    read_pdf, find_tables, table_specification, tables_to_xlsx
)


this_dir = os.path.abspath(os.path.dirname(__file__))

def file_path_in_testdir(file_name: str) -> str:
    """Return the full path to a file in the test directory."""
    return os.path.join(this_dir, file_name)


class TestParser:
    def test_parser_value(self):
        parser = Parser()
        assert parser.value("test") == "test"

    def test_intparser_value_valid(self):
        parser = IntParser(thousand_separator=",")
        assert parser.value("1,000") == 1000
        assert parser.value("123456") == 123456

    def test_intparser_value_invalid(self):
        parser = IntParser(thousand_separator=",")
        # Invalid integer format
        with pytest.raises(ValueError):
            parser.value("1,000.5")
        # Non-numeric string
        with pytest.raises(ValueError):
            parser.value("abc")

    def test_floatparser_value_valid(self):
        parser = FloatParser(thousand_separator=",", decimal_separator=".")
        assert parser.value("1,000.50") == 1000.50
        assert parser.value("123456.78") == 123456.78
        assert parser.value("123,456") == 123456.00

    def test_floatparser_value_invalid(self):
        parser = FloatParser(thousand_separator=",", decimal_separator=".")
        # Invalid decimal format
        with pytest.raises(ValueError):
            parser.value("1,000,50")
        # Non-numeric string
        with pytest.raises(ValueError):
            parser.value("abc")

    def test_floatparser_no_separators(self):
        parser = FloatParser(thousand_separator=None, decimal_separator=None)
        assert parser.value("1000") == 1000.0
        assert parser.value("1234.56") == 1234.56
        with pytest.raises(ValueError):
            parser.value("1,000.12")

    def test_intparser_no_separators(self):
        parser = IntParser(thousand_separator=None)
        assert parser.value("1000") == 1000
        assert parser.value("123456") == 123456
        with pytest.raises(ValueError):
            parser.value("1,000")


def test_read_pdf():
    pdf_file = file_path_in_testdir("tables.pdf")
    document = read_pdf(pdf_file, force=False, docling=True)
    assert document
    assert len(document.tables) == 3
    document2 = read_pdf(pdf_file, force=True, docling=False)
    assert document2
    assert len(document2) == 3

def parsed_pdf(docling: bool):
    pdf_file = file_path_in_testdir("tables.pdf")
    document = read_pdf(pdf_file, force=False, docling=docling)
    return document

def test_find_tables_default_parsers():
    for docling in [True, False]:
        document = parsed_pdf(docling=docling)
        tables1 = find_tables(document,
                              TableSpec({"id": "Numeric Id", "A": "Amount"}))
        assert len(tables1) == 3
        tables2 = find_tables(document,
                              TableSpec({"name": "Full Name", "id": "Numeric Id", "A": "Amount"}))
        assert len(tables2) == 2
        tables3 = find_tables(document,
                              TableSpec({"name": "Name", "id": "Numeric Id", "A": "Amount"}))
        assert len(tables3) == 1

def test_find_tables_numeric_parsers():
    for docling in [True, False]:
        document = parsed_pdf(docling=docling)
        # This thousand separator is used in the last table only
        int_parser = IntParser(thousand_separator="'")
        fp_parser = FloatParser(thousand_separator="'", decimal_separator=".")
        tables = find_tables(document,
                             TableSpec({"name": "Full Name", "id": "Numeric Id", "A": "Amount"}),
                             parsers={"id": int_parser, "A": fp_parser})
        assert len(tables) == 2
        table2 = tables[0]
        for row in table2:
            # The first row will be skipped because it fails parsing
            assert len(row) == 3
            assert row["name"] == "Bar"
            assert row["id"] == 2
            assert row["A"] == 21000.0
            break
        table3 = tables[1]
        for row in table3:
            # The first row will be skipped because it fails parsing
            assert len(row) == 3
            assert row["name"] == "Bar"
            assert row["id"] == 1100
            assert row["A"] == 123.0

def test_table_specification():
    yaml_file = file_path_in_testdir("funds.yaml")
    expected_drop = ["Column 1", "Column X"]
    result = table_specification(yaml_file)
    assert isinstance(result, TableSpec)
    assert len(result.columns) == 5
    assert all(key == value for key, value in result.columns.items())
    assert result.drop == expected_drop

def test_table_specification_flat():
    yaml_file = file_path_in_testdir("flat.yaml")
    expected_columns = {"x": "X", "y": "Y"}
    expected_drop = []
    result = table_specification(yaml_file)
    assert isinstance(result, TableSpec)
    assert len(result.columns) == 2
    assert result.columns == expected_columns
    assert result.drop == expected_drop

def test_tables_to_xlsx():
    # Read both sheets from Excel file into a dataframe
    xls_path = file_path_in_testdir("test_tables_to_xlsx.xlsx")
    sheets = pd.read_excel(xls_path, sheet_name=None)
    spec = TableSpec(
        columns={"name": "Name", "number": "Number"},
        drop=["Color"]
    )
    tables = []
    for _sheet, df in sheets.items():
        table = Table(df)
        assert table.select(spec)
        table.parse_with({"number": IntParser(thousand_separator="")})
        tables.append(table)
    assert len(tables) == 2
    # pylint: disable=consider-using-with  # Managing the file based on test outcome
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx",
                                            dir=file_path_in_testdir("."))
    file_ok = False
    try:
        tables_to_xlsx(tables, temp_file.name,
                       sheet_name="Sheet12",
                       widths={"name": 100})
        assert os.path.exists(temp_file.name)
        assert (os.path.getsize(temp_file.name)
                == os.path.getsize(file_path_in_testdir("test_tables_to_xlsx_expect.xlsx")))
        file_ok = True
    finally:
        if os.path.exists(temp_file.name) and file_ok:
            os.remove(temp_file.name)
        else:
            print(f"Temporary file of failed test not deleted: {temp_file.name}")
    assert file_ok
