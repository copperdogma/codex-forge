from types import SimpleNamespace

from bs4 import BeautifulSoup

from modules.adapter.table_rescue_onward_tables_v1.main import (
    _build_user_text,
    _call_ocr,
    _normalize_rescue_html,
    _strip_page_markers,
)


class _DummyResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="<p>ok</p>", usage=None, id="resp_test")


class _DummyOpenAI:
    responses_instance = None

    def __init__(self, timeout=None):
        self.timeout = timeout
        self.responses = _DummyResponses()
        _DummyOpenAI.responses_instance = self.responses


def test_call_ocr_omits_temperature_for_gpt5_models(monkeypatch):
    monkeypatch.setattr(
        "modules.adapter.table_rescue_onward_tables_v1.main.OpenAI",
        _DummyOpenAI,
    )

    _call_ocr(
        "gpt-5",
        "system prompt",
        "data:image/jpeg;base64,abc",
        0.0,
        512,
        30.0,
    )

    call = _DummyOpenAI.responses_instance.calls[0]
    assert call["model"] == "gpt-5"
    assert "temperature" not in call
    assert call["max_output_tokens"] == 512


def test_call_ocr_keeps_temperature_for_non_gpt5_models(monkeypatch):
    monkeypatch.setattr(
        "modules.adapter.table_rescue_onward_tables_v1.main.OpenAI",
        _DummyOpenAI,
    )

    _call_ocr(
        "gpt-4.1",
        "system prompt",
        "data:image/jpeg;base64,abc",
        0.0,
        512,
        30.0,
    )

    call = _DummyOpenAI.responses_instance.calls[0]
    assert call["model"] == "gpt-4.1"
    assert call["temperature"] == 0.0
    assert call["max_output_tokens"] == 512


def test_call_ocr_includes_custom_user_text(monkeypatch):
    monkeypatch.setattr(
        "modules.adapter.table_rescue_onward_tables_v1.main.OpenAI",
        _DummyOpenAI,
    )

    _call_ocr(
        "gpt-4.1",
        "system prompt",
        "data:image/jpeg;base64,abc",
        0.0,
        512,
        30.0,
        user_text="Return only HTML.\n<current-html><p>broken</p></current-html>",
    )

    call = _DummyOpenAI.responses_instance.calls[0]
    assert "current-html" in call["input"][1]["content"][0]["text"]


def test_build_user_text_truncates_context():
    text = _build_user_text("<p>" + ("x" * 50) + "</p>", 20)

    assert "current-html" in text
    assert "truncated" in text


def test_strip_page_markers_splits_inline_family_tables():
    html = """
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Linda</td><td>Dec. 21, 1947</td><td>Oct. 22, 1966</td><td>Eric Breidford</td><td>3</td><td>0</td><td></td></tr>
        <tr><th>RICHARD'S FAMILY</th></tr>
        <tr><td>Brent</td><td>Feb. 9, 1975</td><td></td><td></td><td></td><td></td><td></td></tr>
        <tr><td>Jeffery</td><td>Feb. 20, 1977</td><td></td><td></td><td></td><td></td><td></td></tr>
        <tr><th>PAUL'S FAMILY</th></tr>
        <tr><td>Steven (adpt)</td><td>Sept. 1, 1969</td><td></td><td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table>
    """

    cleaned = _strip_page_markers(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    headings = [tag.get_text(" ", strip=True) for tag in soup.find_all("h2")]
    assert headings == ["RICHARD'S FAMILY", "PAUL'S FAMILY"]
    assert len(soup.find_all("table")) == 3
    assert not any(
        th.get_text(" ", strip=True) in {"RICHARD'S FAMILY", "PAUL'S FAMILY"}
        for th in soup.find_all("th")
    )


def test_strip_page_markers_pads_genealogy_tables_to_expected_columns():
    html = """
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Brent</td><td>Feb. 9, 1975</td></tr>
      </tbody>
    </table>
    """

    cleaned = _strip_page_markers(html)
    soup = BeautifulSoup(cleaned, "html.parser")
    table = soup.find("table")
    assert table is not None

    header_cells = table.find("thead").find_all("th")
    assert [cell.get_text(" ", strip=True) for cell in header_cells] == [
        "NAME",
        "BORN",
        "MARRIED",
        "SPOUSE",
        "BOY",
        "GIRL",
        "DIED",
    ]

    row_cells = table.find("tbody").find("tr").find_all("td", recursive=False)
    assert len(row_cells) == 7
    assert row_cells[0].get_text(" ", strip=True) == "Brent"
    assert row_cells[1].get_text(" ", strip=True) == "Feb. 9, 1975"
    assert all(cell.get_text(" ", strip=True) == "" for cell in row_cells[2:])


def test_strip_page_markers_moves_trailing_generation_context_into_merged_table():
    html = """
    <h2>HERVE'S FAMILY</h2>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Annette</td><td>Nov. 4, 1946</td><td>July 12, 1969</td><td>Robert Hyde</td><td>1</td><td>1</td><td></td></tr>
        <tr><td><strong>Emilie's Great Grandchildren</strong></td></tr>
        <tr><td><strong>Herve's Grandchildren</strong></td></tr>
      </tbody>
    </table>
    <h2>ANNETTE'S FAMILY</h2>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>David</td><td>Oct. 7, 1973</td><td></td><td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table>
    """

    cleaned = _strip_page_markers(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    headings = [heading.get_text("\n", strip=True) for heading in soup.find_all("h2")]
    assert headings == ["HERVE'S FAMILY"]

    tables = soup.find_all("table")
    assert len(tables) == 1
    merged_rows = tables[0].find("tbody").find_all("tr", recursive=False)
    heading_rows = [
        row.get_text("\n", strip=True)
        for row in merged_rows
        if "genealogy-subgroup-heading" in (row.get("class") or [])
    ]
    assert heading_rows == [
        "Emilie's Great Grandchildren",
        "Herve's Grandchildren",
        "ANNETTE'S FAMILY",
    ]
    assert "David" in tables[0].get_text(" ", strip=True)


def test_strip_page_markers_does_not_merge_plain_contextual_headings_without_moved_context():
    html = """
    <h2>DANIEL'S FAMILY</h2>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Tyrell</td><td>Oct. 9, 1981</td><td></td><td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table>
    <h2>Arthur's Grandchildren<br/>DORA'S FAMILY</h2>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Linda</td><td>Dec. 21, 1947</td><td>Oct. 22, 1966</td><td>Eric Breidford</td><td>3</td><td>0</td><td></td></tr>
      </tbody>
    </table>
    """

    cleaned = _strip_page_markers(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    assert len(soup.find_all("table")) == 2
    assert [heading.get_text("\n", strip=True) for heading in soup.find_all("h2")] == [
        "DANIEL'S FAMILY",
        "Arthur's Grandchildren\nDORA'S FAMILY",
    ]
    assert not soup.find_all("tr", class_="genealogy-subgroup-heading")


def test_strip_page_markers_merges_same_schema_run_once_later_table_has_subgroups():
    html = """
    <h1>Emilie L'Heureux Nolin</h1>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Emilie</td><td>June 8, 1898</td><td>Sept. 22, 1922</td><td>Patrick Nolin</td><td>1</td><td>0</td><td>June 23, 1947</td></tr>
      </tbody>
    </table>
    <h2>EMILIE'S FIRST FAMILY</h2>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Herve P.</td><td>July 12, 1923</td><td>Jan. 22, 1946</td><td>Delores Lessard</td><td>0</td><td>3</td><td></td></tr>
      </tbody>
    </table>
    <h2>EMILIE'S SECOND FAMILY</h2>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Reine</td><td>July 15, 1926</td><td>Oct. 25, 1943</td><td>Paul Bru</td><td>3</td><td>5</td><td></td></tr>
        <tr class="genealogy-subgroup-heading"><th colspan="7">Emilie's Grandchildren</th></tr>
        <tr class="genealogy-subgroup-heading"><th colspan="7">HERVE'S FAMILY</th></tr>
        <tr><td>Annette</td><td>Nov. 4, 1946</td><td>July 12, 1969</td><td>Robert Hyde</td><td>1</td><td>1</td><td></td></tr>
      </tbody>
    </table>
    <h2>CAROLE'S FAMILY</h2>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Stephan</td><td>July 7, 1978</td><td></td><td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table>
    """

    cleaned = _strip_page_markers(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    assert len(soup.find_all("table")) == 1
    assert [heading.get_text(" ", strip=True) for heading in soup.find_all("h2")] == []
    heading_rows = [
        row.get_text("\n", strip=True)
        for row in soup.find_all("tr", class_="genealogy-subgroup-heading")
    ]
    assert heading_rows[:4] == [
        "EMILIE'S FIRST FAMILY",
        "EMILIE'S SECOND FAMILY",
        "Emilie's Grandchildren",
        "HERVE'S FAMILY",
    ]
    assert "CAROLE'S FAMILY" in heading_rows
    assert "Stephan" in soup.get_text(" ", strip=True)


def test_strip_page_markers_merges_headerless_contextual_continuation_run():
    html = """
    <h3>PAULETTE'S FAMILY</h3>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Tammy Lynn</td><td>Apr. 1, 1972</td><td></td><td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table>
    <h3>Emilie's Grandchildren<br/>EMILIENNE'S FAMILY</h3>
    <table>
      <tbody>
        <tr><td>Gilles</td><td>Mar. 17, 1952</td><td>Mar. 6, 1982</td><td>Eleonore Thieson</td><td>0</td><td></td></tr>
      </tbody>
    </table>
    <h3>Emilie's Great Grandchildren<br/>Emilienne's Grandchildren<br/>CORINE'S FAMILY</h3>
    <table>
      <tbody>
        <tr><td>Trina</td></tr>
      </tbody>
    </table>
    <h3>MADELAINE'S FAMILY</h3>
    <table>
      <tbody>
        <tr><td>Charity</td></tr>
      </tbody>
    </table>
    """

    cleaned = _strip_page_markers(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    assert len(soup.find_all("table")) == 1
    assert [heading.get_text(" ", strip=True) for heading in soup.find_all("h3")] == []
    heading_rows = [
        row.get_text("\n", strip=True)
        for row in soup.find_all("tr", class_="genealogy-subgroup-heading")
    ]
    assert heading_rows[:4] == [
        "PAULETTE'S FAMILY",
        "Emilie's Grandchildren",
        "EMILIENNE'S FAMILY",
        "Emilie's Great Grandchildren",
    ]
    assert "Trina" in soup.get_text(" ", strip=True)
    assert "Charity" in soup.get_text(" ", strip=True)
    merged_rows = soup.find("table").find("tbody").find_all("tr", recursive=False)
    assert max(len(row.find_all(["td", "th"], recursive=False)) for row in merged_rows) == 7


def test_normalize_rescue_html_merges_split_genealogy_run_into_single_table():
    html = """
    <h3>PAULETTE'S FAMILY</h3>
    <table>
      <thead>
        <tr>
          <th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th colspan="2">BOY/GIRL</th><th>DIED</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>Tammy Lynn</td><td>Apr. 1, 1972</td><td></td><td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table>
    <h3>Emilie's Grandchildren<br/>EMILIENNE'S FAMILY</h3>
    <table>
      <tbody>
        <tr><td>Gilles</td><td>Mar. 17, 1952</td><td>Mar. 6, 1982</td><td>Eleonore Thieson</td><td>0</td><td></td></tr>
      </tbody>
    </table>
    <h3>Emilie's Great Grandchildren<br/>Emilienne's Grandchildren<br/>CORINE'S FAMILY</h3>
    <table>
      <tbody>
        <tr><td>Trina</td></tr>
      </tbody>
    </table>
    """

    cleaned = _normalize_rescue_html(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    assert len(soup.find_all("table")) == 1
    assert [heading.get_text(" ", strip=True) for heading in soup.find_all("h3")] == []
    heading_rows = [
        row.get_text("\n", strip=True)
        for row in soup.find_all("tr", class_="genealogy-subgroup-heading")
    ]
    assert heading_rows[:4] == [
        "PAULETTE'S FAMILY",
        "Emilie's Grandchildren",
        "EMILIENNE'S FAMILY",
        "Emilie's Great Grandchildren",
    ]
    merged_rows = soup.find("table").find("tbody").find_all("tr", recursive=False)
    assert max(len(row.find_all(["td", "th"], recursive=False)) for row in merged_rows) == 7


def test_normalize_rescue_html_promotes_contextual_thead_rows_before_splitting_tables():
    html = """
    <table>
      <thead>
        <tr><th>Alma's Great Grandchildren<br/>Rolland's Grandchildren<br/>SIMONE'S FAMILY</th></tr>
        <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
      </thead>
      <tbody>
        <tr><td>Jody</td><td>July 9, 1967</td><td></td><td></td><td></td><td></td></tr>
        <tr><td>Karlee</td><td>Oct. 21, 1975</td><td></td><td></td><td></td><td></td></tr>
        <tr><td><strong>Alma's Grandchildren<br/>MARY PAULE'S FAMILY</strong></td></tr>
        <tr><td>Ronald</td><td>Jan. 24, 1933</td><td>July 20, 1963</td><td>Jean Bailey</td><td>1 1</td><td></td></tr>
      </tbody>
    </table>
    """

    cleaned = _normalize_rescue_html(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    headings = [tag.get_text(" ", strip=True) for tag in soup.find_all(["p", "h2"])]
    assert headings[:5] == [
        "Alma's Great Grandchildren",
        "Rolland's Grandchildren",
        "SIMONE'S FAMILY",
        "Alma's Grandchildren",
        "MARY PAULE'S FAMILY",
    ]

    tables = soup.find_all("table")
    assert len(tables) == 2
    for table in tables:
        thead_rows = table.find("thead").find_all("tr", recursive=False)
        assert len(thead_rows) == 1
        assert "SIMONE'S FAMILY" not in thead_rows[0].get_text(" ", strip=True)
