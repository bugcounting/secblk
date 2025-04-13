"""
A module for parsing tables from PDF documents using docling.

Functions:
    read_pdf: Read a PDF file and parse it into a DoclingDocument.
    find_tables: Find tables in a parsed document with specified columns and parsers.
"""
from dataclasses import dataclass
import logging
import os
import pickle
import re
import sys
from typing import Optional, Union

import yaml
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from pandas import DataFrame
from tabula import read_pdf as tabula_read     # pip install tabula-py


@dataclass
class TableSpec:
    """
    A class for specifying table columns.

    Attributes:
        columns: a dict mapping new labels to existing column names
        drop: a list of column names that must exist in the table but will be dropped
              during iteration
    """
    columns: dict[str, str]
    drop: Optional[list[str]] = None


def table_specification(yaml_file: str) -> TableSpec:
    """
    Read a table format specification from a YAML file and return it as a dictionary.

    All keys in the YAML file are expected to be dictionaries, whose entries are
    used to partition the column specification in groups. Each value can then be
    either a dictionary (for column specifications) or a list (for columns to drop).
    
    Args:
        yaml_file: Path to the YAML file containing a table format specification.
    
    Returns:
        A dictionary with the table format specification read from the YAML file.
    """
    with open(yaml_file, "r", encoding="utf-8") as file:
        raw_data = yaml.safe_load(file)
    dict_specs = [value for value in raw_data.values() if isinstance(value, dict)]
    list_specs = [value for value in raw_data.values() if isinstance(value, list)]
    columns = {key: value for spec in dict_specs for key, value in spec.items()
               if value is not None}
    drop = [value for spec in list_specs for value in spec]
    logging.debug("Table specification read.")
    logging.debug("Specification map: %s", columns)
    logging.debug("Specification drop: %s", drop)
    return TableSpec(columns=columns, drop=drop)


class Parser:               # pylint: disable=too-few-public-methods # It's just a function object
    """A class for parsing text into strings."""

    def value(self, text: str):
        """Parse a value from a string."""
        return text


class IntParser(Parser):     # pylint: disable=too-few-public-methods # It's just a function object
    """A class for parsing text into integer numbers."""

    thousand_sep: Optional[str] = None

    def __init__(self, thousand_separator: Optional[str] = None):
        self.thousand_sep = thousand_separator

    def value(self, text: str) -> int:
        """Parse an integer string with the configured separator."""
        if self.thousand_sep:
            text = re.sub(fr"(?<=\d)[{self.thousand_sep}](?=\d{{3}})", "", text)
        return int(text)


class FloatParser(IntParser): # pylint: disable=too-few-public-methods # It's just a function object
    """A class for parsing text into float numbers."""

    decimal_sep: Optional[str] = None

    def __init__(self, thousand_separator: Optional[str] = None,
                 decimal_separator: Optional[str] = None):
        super().__init__(thousand_separator)
        self.decimal_sep = decimal_separator

    def value(self, text: str) -> float:
        """Parse a float number string with the configured separators."""
        if self.thousand_sep:
            text = re.sub(fr"(?<=\d)[{self.thousand_sep}](?=\d{{3}})", "", text)
        if self.decimal_sep:
            text = re.sub(fr"[{self.decimal_sep}](?=\d*$)", ".", text)
        return float(text)


class AbstractTable:
    """
    Interface for iterating over a table made of rows and a header.
    """

    @property
    def header(self) -> list[str]:
        """Return the table header."""
        return []

    def __iter__(self):
        return self

    def __next__(self) -> dict[str, str]:
        raise StopIteration


class Table(AbstractTable):
    """
    Iterate over a table with selected columns and parsers.
    
    Arguments:
        table: a TableItem object from a DoclingDocument, or a Pandas DataFrame
        
    Attributes:
        header: a list of column names
        content: a list of rows with column values
        selected: a dict mapping new column names to their column indexes
        parsers: a dict mapping column indexes to parser classes
        
    Example:
        # initialize the table from a TableItem/DataFrame object
        table = Table(table_item)
        # after initialization, all columns are selected with their original names
        # select only columns "Family Name" and "NumID",
        # which will be labeled "name" and "identifier"
        table.select({"name": "Family Name", "identifier": "NumID"})
        # column labeled "name" will be parsed with the Parser class,
        # column labeled "identifier" with the IntParser class
        table.parse_with({"name": Parser(), "identifier": IntParser()})
        # The iteration will skip rows with values that fail parsing
        for row_dict in table:
            row = [f"{label}: {value}" for label, value in row_dict.items()]
            print(", ".join(row))
    """

    _header: list[str]
    _content: list[list[str]]
    selected: dict[str, int]
    parsers: dict[int, Parser]

    _table_data: Union["TableItem", DataFrame]  # type: ignore # Docling is imported conditionally
    _n_row: int = 0
    _is_dockling: bool
                                                               # Docling is imported conditionally
    def __init__(self, table: Union["TableItem", DataFrame]):  # type: ignore
        if isinstance(table, DataFrame):
            self._is_dockling = False
            self._table_data = table
            self._header = self._table_data.columns.tolist()
            content = []
            for _, row in self._table_data.iterrows():
                content.append([str(cell) for cell in row])
        else:
            self._is_dockling = True
            self._table_data = table.data
            self._header = [cell.text for cell in self._table_data.grid[0]]
            content = []
            for row in self._table_data.grid[1:]:
                content.append([cell.text for cell in row])
        self._content = content
        self.selected = dict(enumerate(self._header))
        self.parsers = {k: Parser() for k, _ in enumerate(self._header)}

    @property
    def header(self) -> list[str]:
        """Return the table header after selection and parsing."""
        return list(self.selected)

    def has_column(self, column_name: str) -> bool:
        """Does the table have a column with the given name?"""
        return column_name in self._header

    def select(self, spec: TableSpec) -> bool:
        """
        Select columns from the table for iteration. Calling this method resets
        the parsers to the default Parser class.
        
        Arguments:
            spec: a TableSpec object with columns and drop attributes
        
        Returns:
            True if all columns are found in the table, False otherwise.
        """
        try:
            self.selected = {label: self._header.index(column)
                             for label, column in spec.columns.items()}
            self.parsers = {column: Parser() for column in self.selected.values()}
        except ValueError:
            return False
        return spec.drop is None or all(column in self._header for column in spec.drop)

    def parse_with(self, parsers: dict[str, Parser], strict: bool=True) -> bool:
        """
        Set parsers for columns in the table. The keys are the new
        labels (same as in `select`), the values are the parser
        classes.

        If `strict` is True, any labels not in the table will raise a ValueError.
        
        Any label in the table and not in `parsers` will keep its current parser.
        
        Since `select` resets the parser, call this method after `select`.

        Returns:
            If `strict` is True, returns True iff all columns are found in the table.
            If `strict` is False, returns True iff all columns also in `parsers` 
            are found in the table.
        """
        if not strict:
            parsers = {label: parser for label, parser in parsers.items()
                       if label in self.selected}
        if strict and any(label not in self.selected for label in parsers):
            return False
        for label, parser in parsers.items():
            self.parsers[self.selected[label]] = parser
        return True

    def __iter__(self):
        self._n_row = 0
        return self

    def __next__(self) -> dict[str, str]:
        if self._n_row >= len(self._content):
            raise StopIteration
        row = self._content[self._n_row]
        self._n_row += 1
        try:
            row_dict = {label: self.parsers[index].value(row[index])
                        for label, index in self.selected.items()}
        except ValueError:
            print(f"Skipping row {row}", file=sys.stderr)
            return self.__next__()
        return row_dict


def read_pdf(pdf_path: str, force: bool,
             docling: bool) -> Union["DoclingDocument",  # pyright: ignore[reportUndefinedVariable]
                                     list[DataFrame]]:
    """
    Read a PDF file, convert it to a DoclingDocument or a list of DataFrames,
    serialize it to file, and return it.
    
    Arguments:
        pdf_path: path to the PDF file
        force: if True, force re-parsing and re-serialization of the document
        docling: if True, use `docling` to parse the PDF, otherwise use `tabula-py`.
                 If `docling` is False, the `force` argument is ignored.
    
    Returns:
        A DoclingDocument or a list of Pandas DataFrames with tables.
    """
    obj_path = pdf_path + ".obj"
    if docling and not force and os.path.exists(obj_path):
        with open(obj_path, "rb") as f:
            document = pickle.load(f)
        logging.info("Parsed PDF document from cache: %s", obj_path)
    else:
        if docling:
            from docling.document_converter import DocumentConverter # pylint: disable=import-outside-toplevel
            converter = DocumentConverter()
            result = converter.convert(pdf_path)
            logging.info("PDF document parsed with Docling")
            document = result.document
            logging.info("Caching parsed PDF document to %s", obj_path)
            with open(obj_path, "wb") as f:
                pickle.dump(document, f)
        else:
            document = tabula_read(pdf_path, multiple_tables=True, pages="all")
            logging.info("PDF document parsed with Tabula")
        print("Parsed PDF document", file=sys.stderr)
    return document

                                                   # Docling is imported conditionally
def find_tables(document: Union["DoclingDocument", # pyright: ignore[reportUndefinedVariable]
                                list[DataFrame]],
                spec: TableSpec, parsers: Optional[dict[str, Parser]]=None,
                strict: bool=False) -> list[Table]:
    """
    Find tables in a parsed PDF document that have the specified columns.
    
    Arguments:
        document: a parsed PDF document with tables
        spec: a TableSpec object with columns and drop attributes
        parsers: a dict mapping column names to parser classes. If None, use standard parsers.
        strict: if True, all columns must be found in the table, otherwise
                only the columns in `columns` are required.

    Returns:
        A list of Table objects with the specified columns.
    """
    result = []
    tables = document if isinstance(document, list) else document.tables
    for raw_table in tables:
        table = Table(raw_table)
        if table.select(spec):
            if parsers is not None:
                ok = table.parse_with(parsers, strict=strict)
                if not ok:
                    logging.warning("Table with header: %s failed parsing", table.header)
                    continue
            logging.warning("Table with header: %s parsed successfully", table.header)
            result.append(table)
    return result


def tables_to_xlsx(tables: list[AbstractTable], file_path: str,   # pylint: disable=too-many-locals  # Not sure it's worth refactoring
                   sheet_name: str, widths: dict[str, int]=None, summarize_work: bool=False) -> None:
    """
    Export a list of AbstractTable instances to an XLSX file. The tables must have the same
    columns, otherwise the export will fail.

    Args:
        tables: List of AbstractTable instances to export.
        file_path: Path to the output XLSX file.
        sheet_name: Name of the worksheet in the XLSX file.
        widths: A dictionary mapping column names to their widths. Any column not in
                this dictionary will be set to fit its content.
    """
    if not summarize_work:
        logging.info("Exporting %d tables to XLSX file", len(tables))
    # Create a new workbook and select the active worksheet
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    all_rows = 0
    if widths is None:
        widths = {}
    widths_idx = {}
    for num, table in enumerate(tables):
        if num == 0:
            # Write the header row
            headers = table.header
            widths_idx = {headers.index(name): width
                          for name, width in widths.items() if name in headers}
            sheet.append(headers)
            # Format the header row
            for cell in sheet[1]:
                cell.font = Font(bold=True, size=12)
                cell.alignment = Alignment(horizontal="center", vertical="center")
        if table.header != headers:
            raise ValueError("Tables have different headers")
        # Write the data rows
        n_row = 0
        for n_row, row_dict in enumerate(table, start=1):
            row = list(row_dict.values())
            all_rows += 1
            sheet.append(row)
        if not summarize_work:
            logging.info("Exported %d rows in table #%d", n_row, num + 1)
    logging.info("Exported %d rows in %d tables", all_rows, len(tables))
    # Adjust column widths
    for num, col in enumerate(sheet.columns):
        max_length = 0
        col_letter = col[0].column_letter
        if num in widths_idx:
            adjusted_width = widths_idx[num]
            for cell in col:
                cell.alignment = Alignment(wrap_text=True)
        else:
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = max_length + 2
        sheet.column_dimensions[col_letter].width = adjusted_width
    # Save the workbook to the specified file path
    workbook.save(file_path)
    logging.info("Written file: %s", file_path)
