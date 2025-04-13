# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring
# pylint: disable=invalid-name,too-few-public-methods,protected-access
import os
import tempfile
from unittest.mock import patch

from secblk.tables import TableSpec
from secblk.funds import Fund
from secblk.subs import process_funds
from .test_tables import file_path_in_testdir


@patch("secblk.queries.Query.lookup")
def test_process_funds(mock_lookup):
    # Mock Query.lookup so that it returns a basic Fund object
    def Query_lookup(isin, _year):
        if isinstance(isin, str):
            return Fund(isin=isin)
        if isinstance(isin, Fund):
            return Fund(isin=isin.isin) + isin
        return None
    mock_lookup.side_effect = Query_lookup
    pdf_path = file_path_in_testdir("tables.pdf")
    spec = TableSpec(
        columns={"isin": "Name", "quantity": "Numeric Id"},
        drop=["Amount"]
    )
    # pylint: disable=consider-using-with  # Managing the file based on test outcome
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx",
                                            dir=file_path_in_testdir("."))
    file_ok = False
    try:
        process_funds(pdf_path, spec,
                      thousand_separator="", decimal_separator=",",
                      force=False, docling=False, year=None, name_width=40,
                      xlsx_path=temp_file.name,
                      no_lookup=False)
        assert os.path.exists(temp_file.name)
        assert (os.path.getsize(temp_file.name)
                == os.path.getsize(file_path_in_testdir("test_process_funds_expect.xlsx")))
        file_ok = True
    finally:
        if os.path.exists(temp_file.name) and file_ok:
            os.remove(temp_file.name)
        else:
            print(f"Temporary file of failed test not deleted: {temp_file.name}")
    assert file_ok
