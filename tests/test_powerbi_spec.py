"""Static checks on the Power BI design files.

These tests do not run DAX or Power Query M (no engine is available here). They catch the mistakes a text
check can catch: unbalanced brackets, a function name that is not on the list that was verified against the
documentation, a measure without a documentation header, and documents that have drifted from the files
they describe.
"""

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"

# Every DAX function used in measures.dax. Each was checked against its Microsoft Learn reference page.
ALLOWED_FUNCTIONS = {
    "DIVIDE", "CALCULATE", "COUNTROWS", "SUM", "COUNT", "MAX", "MIN", "EOMONTH", "REMOVEFILTERS",
    "USERELATIONSHIP", "FILTER", "ISBLANK", "IF", "BLANK", "SWITCH", "TRUE", "SELECTEDVALUE",
}

DEFINITION = re.compile(r"^([^\s/].*?) =( |$)")


def read_measures():
    """Return a list of dicts: name, header (comment lines above), body (code lines, comments removed)."""
    lines = (PBI / "measures.dax").read_text(encoding="utf-8").split("\n")
    measures = []
    header = []
    current = None
    for line in lines:
        stripped = line.strip()
        if current is None and stripped.startswith("//"):
            header.append(stripped[2:].strip())
            continue
        if stripped == "":
            if current is not None:
                measures.append(current)
                current = None
            header = []
            continue
        if current is None:
            match = DEFINITION.match(line)
            assert match, f"unexpected line outside a measure: {line!r}"
            current = {"name": match.group(1), "header": header, "body": [line[len(match.group(1)) + 2:]]}
            header = []
        else:
            current["body"].append(line.split("//")[0])
    if current is not None:
        measures.append(current)
    return measures


@pytest.fixture(scope="module")
def measures():
    return read_measures()


def strip_text(code):
    """Remove string literals, column references and measure references so only code remains."""
    code = re.sub(r'"[^"]*"', '""', code)
    code = re.sub(r"\[[^\]]*\]", "[]", code)
    code = re.sub(r"'[^']*'", "''", code)
    return code


def test_there_are_measures(measures):
    assert len(measures) == 46


def test_measure_names_are_unique(measures):
    names = [m["name"] for m in measures]
    assert len(names) == len(set(names))


def test_every_measure_has_name_answers_and_format_in_its_header(measures):
    for m in measures:
        header = m["header"]
        assert header, m["name"]
        assert header[0] == m["name"], f"header title does not match definition for {m['name']}"
        assert any(h.startswith("Answers:") for h in header), f"{m['name']} has no Answers line"
        assert header[-1].startswith("Format:"), f"{m['name']} has no Format line last"


def test_brackets_and_parentheses_balance_in_every_measure(measures):
    for m in measures:
        code = strip_text("\n".join(m["body"]))
        assert code.count("(") == code.count(")"), f"parentheses in {m['name']}"
        assert code.count("[") == code.count("]"), f"square brackets in {m['name']}"
        depth = 0
        for char in code:
            depth += char == "("
            depth -= char == ")"
            assert depth >= 0, f"closing before opening in {m['name']}"


def test_only_verified_functions_are_used(measures):
    for m in measures:
        code = strip_text("\n".join(m["body"]))
        for name in re.findall(r"\b([A-Z][A-Z0-9_.]*)\s*\(", code):
            assert name in ALLOWED_FUNCTIONS, f"{m['name']} uses {name}, which is not on the verified list"


def test_every_var_has_a_return(measures):
    for m in measures:
        code = strip_text("\n".join(m["body"]))
        if re.search(r"\bVAR\b", code):
            assert re.search(r"\bRETURN\b", code), f"{m['name']} declares VAR without RETURN"


def test_ratios_use_divide_not_the_division_operator(measures):
    # A bare "/" by an expression fails on a zero denominator. DIVIDE handles it. Dividing by a literal
    # (for example minutes to hours) is safe.
    for m in measures:
        code = strip_text("\n".join(m["body"]))
        assert not re.search(r"/(?!\s*\d)", code), f"{m['name']} uses / instead of DIVIDE"


def test_no_averages_of_percentages(measures):
    for m in measures:
        code = strip_text("\n".join(m["body"]))
        assert "AVERAGE" not in code, m["name"]


def test_every_measure_is_in_the_reference_table(measures):
    reference = (PBI / "measures.md").read_text(encoding="utf-8")
    for m in measures:
        assert f"| `{m['name']}` |" in reference, f"{m['name']} missing from measures.md"


def test_reference_table_lists_no_measure_that_is_not_in_the_file(measures):
    reference = (PBI / "measures.md").read_text(encoding="utf-8")
    names = {m["name"] for m in measures}
    listed = re.findall(r"^\| `([^`]+)` \|", reference, flags=re.M)
    assert len(listed) == len(names)
    assert set(listed) == names


def test_measures_referenced_by_other_measures_exist(measures):
    names = {m["name"] for m in measures}
    columns = set()
    for path in (ROOT / "model").glob("fact_ticket.csv"):
        with open(path, newline="", encoding="utf-8") as h:
            columns |= set(next(csv.reader(h)))
    dax_only_columns = {"opened_date", "resolved_date"}
    for m in measures:
        code = re.sub(r'"[^"]*"', '""', "\n".join(m["body"]))
        # Table[column] references are written with a table name directly before the bracket.
        bare = re.sub(r"\b[A-Za-z]+\[[^\]]*\]", "", code)
        for ref in re.findall(r"\[([^\]]+)\]", bare):
            assert ref in names, f"{m['name']} refers to [{ref}] which is not a measure"
        for table, column in re.findall(r"\b(Fact[A-Za-z]*)\[([^\]]+)\]", code):
            assert column in columns | dax_only_columns, f"{m['name']} uses unknown column {column}"


def test_calendar_columns_used_in_dax_exist_in_dim_date(measures):
    with open(ROOT / "data" / "dim_date.csv", newline="", encoding="utf-8") as h:
        columns = set(next(csv.reader(h)))
    for m in measures:
        code = "\n".join(m["body"])
        for column in re.findall(r"\bDimDate\[([^\]]+)\]", code):
            assert column in columns, f"{m['name']} uses DimDate[{column}] which is not in dim_date.csv"


def test_file_states_that_it_was_not_run():
    for name in ("measures.dax", "load-csvs.pq"):
        head = (PBI / name).read_text(encoding="utf-8")[:600]
        assert "NOT RUN" in head, name


# ---- Power Query M ----------------------------------------------------------------------------------

M_QUERIES = [
    "fnLoadCsv", "fnParseUtc", "fnParseDate", "FactTicket", "DimDate", "DimSite", "DimTeam",
    "DimPriority", "DimTicketType", "SlaTarget", "PriorityMatrix",
]


def test_m_file_has_every_query_with_matching_end_markers():
    text = (PBI / "load-csvs.pq").read_text(encoding="utf-8")
    starts = re.findall(r"^// ===== Query: (\w+) =====$", text, flags=re.M)
    assert starts == M_QUERIES
    assert len(re.findall(r"^// ===== end =====$", text, flags=re.M)) == len(M_QUERIES)


def test_m_blocks_are_balanced():
    text = (PBI / "load-csvs.pq").read_text(encoding="utf-8")
    blocks = re.split(r"^// ===== Query: \w+ =====$", text, flags=re.M)[1:]
    for block in blocks:
        code = block.split("// ===== end =====")[0]
        code = "\n".join(line for line in code.split("\n") if not line.strip().startswith("//"))
        code = re.sub(r'"[^"]*"', '""', code)
        for open_, close in (("(", ")"), ("{", "}")):
            assert code.count(open_) == code.count(close), code[:80]
        if "let" in code.split():
            assert re.search(r"^\s*in\s*$", code, flags=re.M), code[:80]


def test_m_file_loads_every_csv_it_needs():
    text = (PBI / "load-csvs.pq").read_text(encoding="utf-8")
    for name in ("fact_ticket.csv", "dim_date.csv", "sites.csv", "companies.csv", "teams.csv",
                 "priority_matrix.csv", "sla_targets.csv"):
        assert name in text


def test_m_fact_types_cover_every_fact_column():
    text = (PBI / "load-csvs.pq").read_text(encoding="utf-8")
    block = text.split("// ===== Query: FactTicket =====")[1].split("// ===== end =====")[0]
    with open(ROOT / "model" / "fact_ticket.csv", newline="", encoding="utf-8") as h:
        columns = next(csv.reader(h))
    for column in columns:
        assert f'"{column}"' in block, f"column {column} is not typed in the FactTicket query"


# ---- Data dictionary and data model -----------------------------------------------------------------

def csv_columns():
    files = sorted((ROOT / "data").glob("*.csv")) + [ROOT / "model" / "fact_ticket.csv"]
    for path in files:
        with open(path, newline="", encoding="utf-8") as h:
            yield path.name, next(csv.reader(h))


def test_data_dictionary_lists_every_file_and_every_column():
    text = (PBI / "data-dictionary.md").read_text(encoding="utf-8")
    for filename, columns in csv_columns():
        assert filename in text, f"{filename} is not described"
        for column in columns:
            assert f"| `{column}` |" in text, f"{filename}: column {column} missing from the data dictionary"


def test_data_model_documents_the_relationships_the_dax_relies_on():
    text = (PBI / "data-model.md").read_text(encoding="utf-8")
    for needle in ("opened_date", "resolved_date", "USERELATIONSHIP", "DimSite", "DimTeam", "DimPriority",
                   "DimTicketType", "DimDate"):
        assert needle in text, needle
    mmd = (PBI / "data-model.mmd").read_text(encoding="utf-8")
    for table in ("FactTicket", "DimDate", "DimSite", "DimTeam", "DimPriority", "DimTicketType"):
        assert table in mmd, table


def test_rendered_diagram_is_committed_and_is_svg():
    svg = (PBI / "data-model.svg").read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg") or "<svg" in svg[:500]


def test_report_layout_only_uses_measures_that_exist(measures):
    names = {m["name"] for m in measures}
    text = (PBI / "report-layout.md").read_text(encoding="utf-8")
    for ref in re.findall(r"`([^`]+)`", text):
        if ref in names:
            continue
        # Anything else in backticks is a column, file or view; only measure-like names matter here.
        assert not re.search(r"(Met %|MoM|Rolling 3M|Backlog at|MTTR \()", ref), f"unknown measure {ref!r}"
