"""
Process funds from a PDF file, lookup values online, and export to XLSX.
"""
import argparse
from enum import Enum
import logging
import os
import sys
from typing import Optional, Union

from .funds import Fund, funds_to_xlsx
from .queries import ICTaxQuery
from .tables import read_pdf, find_tables, Table, TableSpec, table_specification, tables_to_xlsx


class Command(Enum):
    """Available commands."""
    EXTRACT = "extract"
    SPECS = "specs"

class Extract(Enum):
    """Available subcommands."""
    TABLES = "tables"
    FUNDS = "funds"


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))


def setup_log(debug: bool=False, log_file=None, level:int=logging.INFO) -> None:
    """
    Setup logging to a file or to terminal.

    Args:
        debug: If True, print debugging information with the log messages.
        log_file: Path to the log file. If None, log to terminal.
        level: Logging level. Default is INFO.
    """
    if debug:
        log_format = "%(filename)s %(funcName)s() %(lineno)d : %(message)s"
    else:
        log_format = "%(message)s"
    if log_file:
        # Log to a file
        logging.basicConfig(
            filename=log_file,
            filemode="a",
            level=level,
            format=log_format,
        )
    else:
        # Log to terminal
        logging.basicConfig(
            stream=sys.stdout,
            level=level,
            format=log_format,
        )
    # Disable all third-party logging below ERROR
    for logger_name in logging.root.manager.loggerDict.keys():  # pylint: disable=no-member # Spurious warning
        if not logger_name.startswith("secblk"):
            logging.getLogger(logger_name).setLevel(logging.ERROR)

def available_specs() -> dict[str, str]:
    """
    Available table specification YAML files.
    
    Returns:
        A dictionary whose keys are the names of the available table specification
        YAML files, and the values are the contents of the files.
    """
    yaml_files = sorted([
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".yaml") and os.path.isfile(os.path.join(DATA_DIR, f))
    ])
    logging.info("There are %d available table specification files in %s",
                 len(yaml_files), DATA_DIR)
    result = {}
    for yaml_file in yaml_files:
        path = os.path.join(DATA_DIR, yaml_file)
        with open(path, "r", encoding="utf-8") as file:
            yaml_content = file.read()
        result[yaml_file] = yaml_content
    return result


# pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals, inconsistent-return-statements
def process_tables(pdf_path: str,
                   spec: TableSpec,
                   force: bool,
                   docling: bool,
                   xlsx_path: str) -> Union[None, list[Table]]:
    """
    Process tables from a PDF file and export to XLSX.
    
    Args:
        pdf_path: Path to the input PDF file with tables of funds.
        spec: Table specification for parsing the PDF.
        force: Force reparsing of the PDF file, even if a serialized document is available.
        docling: Use docling for PDF parsing (default: use tabula-py).
        xlsx_path: Path to the output XLSX file that is created.
    """
    document = read_pdf(pdf_path, force=force, docling=docling)
    tables = find_tables(document, spec=spec)
    logging.info("Found %d tables in the PDF file", len(tables))
    tables_to_xlsx(tables=tables, file_path=xlsx_path, sheet_name="Tables")


def process_funds(pdf_path: str,
                  spec: TableSpec,
                  thousand_separator: str,
                  decimal_separator: str,
                  force: bool,
                  docling: bool,
                  year: Optional[int],
                  name_width: Optional[int],
                  xlsx_path: str,
                  no_lookup: bool) -> None:
    """
    Process funds from a PDF file, lookup values online, and export to XLSX.
    
    Args:
        pdf_path: Path to the input PDF file with tables of funds.
        spec: Table specification for parsing the PDF.
        thousand_separator: Thousand separator used to parse numbers.
        decimal_separator: Decimal separator used to parse numbers.
        force: Force reparsing of the PDF file, even if a serialized document is available.
        docling: Use docling for PDF parsing (default: use tabula-py).
        year: Year for fund lookup (default: use the latest completed year).
        name_width: Width of the name column in the XLSX file.
        xlsx_path: Path to the output XLSX file that is created.
        no_lookup: If True, do not lookup the funds online, just extract the tables
          from the PDF file.
    """
    document = read_pdf(pdf_path, force=force, docling=docling)
    parsers = Fund.default_parsers(thousand_separator=thousand_separator,
                                   decimal_separator=decimal_separator)
    tables = find_tables(document, spec=spec, parsers=parsers)
    logging.info("Found %d tables in the PDF file", len(tables))
    funds_from_table = []
    for table in tables:
        fund_list = Fund.from_table(table)
        funds_from_table += fund_list
    logging.info("Converted %d rows into funds", len(funds_from_table))
    funds = funds_from_table
    if not no_lookup:
        logging.info("Looking up %d funds online", len(funds))
        funds = ICTaxQuery.lookup_all(*funds_from_table, year=year)
    logging.info("Queried %d funds", len(funds))
    funds_to_xlsx(funds, file_path=xlsx_path, name_width=name_width)


def main():
    """Main function to parse command line arguments and process funds."""
    parser = argparse.ArgumentParser(
        description="Process tables from PDF files, lookup securities data online, and export to XLSX."
        )
    parser.add_argument("--debug", default=False, action="store_true",
                        help="print debugging information about what is being done")
    subparsers = parser.add_subparsers(dest="command", required=True,
                                       help="command to execute")
    cmd_parsers = {
        Command.EXTRACT:
        subparsers.add_parser(
            "extract",
            help="extract tables from a PDF file and save them as an Excel file"
        ),
        Command.SPECS:
        subparsers.add_parser(
            "specs",
            help="list the available table specification YAML files"
        ),
    }

    def str_or_int(value: str) -> Union[str, int]:
        """Return `value` parsed as an `int` if possible, otherwise return `value`."""
        try:
            return int(value)
        except ValueError:
            return str(value)

    cmd_parsers[Command.EXTRACT].add_argument(
        "--spec", type=str_or_int, default=1,
        help=("Either a number, indicating one of the available specification files,"
              " or a path to a table column specification YAML file "
              "(default: %(default)sst available table specification file).")
        )
    cmd_parsers[Command.EXTRACT].add_argument(
        "--docling", action="store_true",
        help="Use docling for PDF parsing (default: use tabula-py)."
        )
    cmd_parsers[Command.EXTRACT].add_argument(
        "--out_path", type=str, default=None,
        help="Path to the output XLSX file (default: <pdf_path>.xlsx)."
        )
    cmd_parsers[Command.EXTRACT].add_argument(
        "--force", action="store_true",
        help="Force reparsing of the PDF file, even if a serialized document is available."
        )

    extract_subparsers = cmd_parsers[Command.EXTRACT].add_subparsers(
        dest="subcommand", required=True,
        help="what kind of extraction to execute"
        )

    cmd_parsers[Command.EXTRACT].add_argument(
        "pdf_path", type=str,
        help="Path to the input PDF file with tables to extract."
        )

    extract_parsers = {
        Extract.TABLES:
        extract_subparsers.add_parser(
            "tables",
            help="just extract tables from a PDF file"
        ),
        Extract.FUNDS:
        extract_subparsers.add_parser(
            "funds",
            help="extract funds information from a PDF file's table"
        )
    }

    extract_parsers[Extract.FUNDS].add_argument(
        "--thousand-separator", type=str, default="'",
        help="Thousand separator used in the numbers (default: %(default)s)."
        )
    extract_parsers[Extract.FUNDS].add_argument(
        "--decimal-separator", type=str, default=".",
        help="Decimal separator used in the numbers (default: %(default)s)."
        )
    extract_parsers[Extract.FUNDS].add_argument(
        "--no-lookup", action="store_true",
        help="Do not lookup the funds online, just extract the funds data from the PDF file."
        )
    extract_parsers[Extract.FUNDS].add_argument(
        "--year", type=int, default=None,
        help="Year for fund lookup (default: use the latest completed year)."
        )
    extract_parsers[Extract.FUNDS].add_argument(
        "--name-width", type=int, default=40,
        help="Width of the name column in the XLSX file (default: %(default) characters)."
        )
    args = parser.parse_args()
    setup_log(debug=args.debug, log_file=None)
    if args.command == Command.SPECS.value:
        specs = available_specs()
        for index, (name, content) in enumerate(specs.items(), start=1):
            print(f"=== SPEC #{index}: {name} ===")
            print(content)
            print()
        return
    assert args.command == Command.EXTRACT.value
    pdf_path = args.pdf_path
    out_path = args.out_path if args.out_path else os.path.splitext(pdf_path)[0] + ".xlsx"
    if isinstance(args.spec, int):
        specs = available_specs()
        try:
            spec_fname = os.path.join(DATA_DIR, list(specs)[args.spec - 1])
        except IndexError:
            parser.error(f"Invalid specification number: {args.spec}.")
            sys.exit(1)
    else:
        spec_fname = args.spec
    if not os.path.isfile(spec_fname):
        parser.error(f"Specification file not found: {spec_fname}.")
        sys.exit(1)
    spec = table_specification(spec_fname)
    if args.subcommand == Extract.TABLES.value:
        process_tables(
            pdf_path=pdf_path,
            spec=spec,
            force=args.force,
            docling=args.docling,
            xlsx_path=out_path
        )
        return
    assert args.subcommand == Extract.FUNDS.value
    process_funds(
        pdf_path=pdf_path,
        spec=spec,
        thousand_separator=args.thousand_separator,
        decimal_separator=args.decimal_separator,
        force=args.force,
        docling=args.docling,
        year=args.year,
        name_width=args.name_width,
        xlsx_path=out_path,
        no_lookup=args.no_lookup
    )


if __name__ == "__main__":
    main()
