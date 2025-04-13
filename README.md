# Security Blanket

This program extracts table information from PDFs and converts them to
Excel. In particular, it is geared towards extracting information
about funds and other securities from a PDF. It can also lookup onlin
additional information about the instruments, based on their [ISIN
number](https://en.wikipedia.org/wiki/International_Securities_Identification_Number).


## Quick start

```sh
# Install
python -m pip install git+https://github.com/bugcounting/secblk
# Extract security information with default options
secblk extract funds securities.pdf
# If extraction fails, try again with Docling
python -m pip install git+https://github.com/bugcounting/secblk[docling]
secblk extract --docling funds securities.pdf
```


## Installation

You will need `python3.10`, `pip`, and `venv` installed.

1. Create a virtual environment to install `secblk` and activate it:

```sh
python -m venv venv
source venv/bin/activate
```

2. Install `secblk` directly from GitHub:

```sh
python -m pip install git+https://github.com/bugcounting/secblk
```

3. If you want to use
   [`docling`](https://github.com/docling-project/docling) to parse
   tables in PDFs, install the `docling` target:
   
```sh
python -m pip install git+https://github.com/bugcounting/secblk[docling]
```

4. Of course, you can also install from a local clone of the
   repository:

```sh
git clone https://github.com/bugcounting/secblk
python -m pip install "secblk/"  # possibly with [docling] target
```


## Detailed usage

First of all, you'll need a table specification file that indicates
which tables to select, and how to parse their columns.

### Available specs

Perhaps there's already a table specification file that suits your
needs packaged with the project. 

- Print a numbered list of all available specification
  files:
  
```sh
secblk specs
```

- To select any of them, pass the option `--spec N` to `secblk
  extract`, where `N` is the number of the spec that you want to
  use. If you don't pass option `--spec` to `secblk extract`, the
  first available specification will be used.

### Table specs

If you want to create your own table specification file, you can of
course modify any of the available ones (which are available under
`lib/python3.X/site-packages/secblk/data/` in the virtual
environment's folder). More generally, a table specification is a
[YAML](https://en.wikipedia.org/wiki/YAML) file with the following
general structure:

```yaml
key_1:
  col_1: Header of 1st column
  col_3: Header of 3rd column

key_2:
  col_2: Header of 2nd column
  col_4:

key_3:
  - Foo
  - Bar

key_4:
  - Baz
```

At the top level, the spec file is a mapping, whose keys (`key_1`,
`key_2`, `key_3`, `key_4` in the example above) are simply used to
partition the specification in sections.

Within each section, there can be a nested mapping (such as under
`key_1` and `key_2`) or a list (such as under `key_3` and `key_4`).

- A *mapping* within a section is interpreted as follows: each `key,
  value` pair &mdash; such that `value` is not empty &mdash; means
  that only tables with a column labeled `value` will be extracted. In
  the exported Excel file, that column will be renamed to `key`. If
  `value` is empty, the pair is ignored.
  
- A *list* within a section is intepreted as follows: only tables with
  columns labeled as the list elements will be extracted; however, the
  columns themselves will be ignored and will not be exported to the
  Excel file.
  
- The order of columns in the PDF tables does not have to match the
  order in the specification.
  
In the example above, the specification determines that only tables
with columns labeled `Header of 1st column`, `Header of 3rd column`,
`Header of 2nd column`, `Foo`, `Bar`, and `Baz` will be processed. In
other words, a table may have additional columns beyond these, but it
must have at least these six columns in any order. Then, only the
first three columns will actually be exported, and they will be
renamed to `col_1`, `col_3`, and `col_2` and rearranged in this order.

### Extract tables

Now that you have selected a specification `$SPEC` &mdash; which can
be a number among those listed by `secblk specs` or a path to a
`.yaml` spec file with the format described above, extract the tables
in a PDF file `$PDF`.

```sh
secblk extract --spec "$SPEC" tables "$PDF"
```

This will extract all tables in `$PDF` that conform to `$SPEC` as a
single sheet in file `"${PDF%.pdf}.xlsx"`.

Other options to `extract` (try also `secblk extract -h`):

- `--docling`: by default, `secblk` uses
  [`tabula-py`](https://tabula-py.readthedocs.io/en/latest/) to
  extract tables from the PDF file. This is pretty good and fast, but
  may fail if PDF tables are not properly encoded. With option
  `--docling`, `secblk` uses the much more powerful
  [`docling`](https://github.com/docling-project/docling), which uses
  state-of-the-art machine learning models to reliable extract PDF
  tables. Using `docling` is not the default because `docling` is a
  big library, and takes time. Thus the recommendation is to first try
  without `docling`; if it fails to properly extract the tables you
  are interested in, install the project with the `[docling]` target
  and then try again with option `--docling`:
  
```sh
# Install project including `docling` dependency
python -m pip install "$SECBLK"[docling]
```

- `--out_path`: path to the Excel file that will be generated. By
  default it is the input PDF's basename, with extension `.xlsx`, in
  the directory where `secblk` is called.
  
- `--force`: since `docling` extraction can take time, once it
  completes `secblk` serializes the structured document produced by
  `docling`, so that future runs of the script will not have to
  re-parse the PDF with `docling`. Option `--force` ignores any
  serialized document, and calls `docling` anew.

### Lookup funds

Command `extract funds` takes the same arguments as `extract tables`,
but requires a table specification with at least a column that is
renamed to `isin`. It will interpret this column as ISIN numbers of
securities, and will lookup additional information about the
securities (*Value number*, *Name*, *Value*, *Country*, and
*Currency*) and combine them with existing information in the PDF tables.

```sh
secblk extract --spec "$SPEC" funds "$PDF"
```

Other options to subcommand `funds` (try also `secblk extract funds
-h`):

-  `--thousand-separator`: the character used to separate thousands in
   numbers in the table.
   
- `--decimal-separator`: the character used to separate the decimal
  digits in numbers in the table.

- `--no-lookup`: do not lookup fund information online, but still
  process the table content as security data.
  
- `--year`: by default, `secblk` looks up the information about funds
  at the end of the previous year. This option overrides the default.
  
- `--name-width`: width, in characters, of column *Name* in the
  generated Excel file.


## Development

Install the `[dev]` target in editable mode to be able to also run the
test suite:

```sh
git clone https://github.com/bugcounting/secblk
cd secblk
python -m pip install .[dev]
pytest test/
```

Some tests may occasionally be flaky: they create a temporary `.xlsx`
file and compare it for size with the expected ones; occasionally, the
temporary file has an off-by-one difference in size, which might be
due to some race conditions. Usually, the problem goes away if you
just rerun the tests.
