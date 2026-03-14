from modules.adapter.table_rescue_onward_tables_v1.main import (
    _normalize_rescue_html,
    _page_rescue_quality,
    _should_apply_normalized_existing,
    _should_accept_rescue,
)


HEADER = (
    "<tr>"
    "<th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th>"
    "<th>BOY</th><th>GIRL</th><th>DIED</th>"
    "</tr>"
)


ARTHUR_HEADING_ONLY = f"""
<table>
  {HEADER}
  <tr><td>Linda</td><td>Dec. 21, 1947</td><td>Oct. 22, 1966</td><td>Eric Breidford</td><td>3</td><td>0</td><td></td></tr>
  <tr><td>Richard</td><td>Sept. 23, 1949</td><td>May 19, 1973</td><td>Patricia Vercuellen</td><td>2</td><td>0</td><td></td></tr>
  <tr><td>Paul</td><td>July 7, 1951</td><td>June 10, 1977</td><td>Fern Holmgren</td><td>3</td><td>0</td><td></td></tr>
</table>
<p>RICHARD'S FAMILY</p>
<p>PAUL'S FAMILY</p>
<p>VIVIAN'S FAMILY</p>
<table>
  <tr><td>TOTAL DESCENDANTS</td><td>54</td></tr>
  <tr><td>LIVING</td><td>49</td></tr>
  <tr><td>DECEASED</td><td>5</td></tr>
</table>
"""


ARTHUR_WITH_CHILD_ROWS = f"""
<table>
  {HEADER}
  <tr><td>Linda</td><td>Dec. 21, 1947</td><td>Oct. 22, 1966</td><td>Eric Breidford</td><td>3</td><td>0</td><td></td></tr>
  <tr><td>Richard</td><td>Sept. 23, 1949</td><td>May 19, 1973</td><td>Patricia Vercuellen</td><td>2</td><td>0</td><td></td></tr>
  <tr><td>Paul</td><td>July 7, 1951</td><td>June 10, 1977</td><td>Fern Holmgren</td><td>3</td><td>0</td><td></td></tr>
</table>
<h2>RICHARD'S FAMILY</h2>
<table>
  {HEADER}
  <tr><td>Brent</td><td>Feb. 9, 1975</td><td></td><td></td><td></td><td></td><td></td></tr>
  <tr><td>Jeffery</td><td>Feb. 20, 1977</td><td></td><td></td><td></td><td></td><td></td></tr>
</table>
<h2>PAUL'S FAMILY</h2>
<table>
  {HEADER}
  <tr><td>Steven (adpt)</td><td>Sept. 1, 1969</td><td></td><td></td><td></td><td></td><td></td></tr>
  <tr><td>Richard (adpt)</td><td>Sept. 10, 1973</td><td></td><td></td><td></td><td></td><td></td></tr>
  <tr><td>Shane (adpt)</td><td>July 17, 1978</td><td></td><td></td><td></td><td></td><td></td></tr>
</table>
<h2>VIVIAN'S FAMILY</h2>
<table>
  {HEADER}
  <tr><td>Ralph</td><td>July 7, 1973</td><td></td><td></td><td></td><td></td><td></td></tr>
  <tr><td>Lisa</td><td>Nov. 6, 1975</td><td></td><td></td><td></td><td></td><td></td></tr>
  <tr><td>Tanya</td><td>Dec. 13, 1976</td><td></td><td></td><td></td><td></td><td></td></tr>
</table>
<table>
  <tr><td>TOTAL DESCENDANTS</td><td>54</td></tr>
  <tr><td>LIVING</td><td>49</td></tr>
  <tr><td>DECEASED</td><td>5</td></tr>
</table>
"""


ROSEANNA_PARAGRAPH_TAIL = """
<p>NAME BORN</p>
<p>Carrie Lynn Feb. 22, 1972</p>
<p>Lisa Marie Mar. 28, 1974</p>
<p>Aaron Judy Mar. 21, 1979</p>
<p>PATRICIA'S FAMILY</p>
<p>ELAINE'S FAMILY</p>
<p>IRENE'S FAMILY</p>
<p>TOTAL DESCENDANTS 56</p>
<p>LIVING 44</p>
<p>DECEASED 8</p>
"""


ROSEANNA_MIXED_TABLE = f"""
<table>
  {HEADER}
  <tr><td>Rose</td><td>Nov. 3, 1894</td><td>July 6, 1915</td><td>Roch Landreville</td><td>2</td><td>4</td><td>Mar. 11, 1972</td></tr>
</table>
<h2>PATRICIA'S FAMILY</h2>
<table>
  {HEADER}
  <tr><td>Carrie Lynn</td><td>Feb. 22, 1972</td><td></td><td></td><td></td><td></td><td></td></tr>
  <tr><td>Lisa Marie</td><td>Mar. 28, 1974</td><td></td><td></td><td></td><td></td><td></td></tr>
</table>
<table>
  <tr><td>TOTAL DESCENDANTS</td><td>56</td></tr>
  <tr><td>LIVING</td><td>44</td></tr>
  <tr><td>DECEASED</td><td>8</td></tr>
</table>
"""


EMILIE_BETTER_EXISTING = f"""
<h1>Emilie L'Heureux Nolin</h1>
<table>
  {HEADER}
  <tr><td>Emilie</td><td>June 8, 1898</td><td>Sept. 22, 1922</td><td>Patrick Nolin</td><td>1</td><td>1</td><td>June 23, 1947</td></tr>
  <tr><td></td><td></td><td></td><td>Patrick</td><td></td><td></td><td>Jan. 2, 1923</td></tr>
  <tr><td></td><td></td><td>Remarried</td><td>Isidore Nolin</td><td>3</td><td></td><td>Deceased</td></tr>
  <tr><td>Herve P.</td><td>July 12, 1923</td><td>Jan. 22, 1946</td><td>Delores Lessard</td><td>0</td><td>3</td><td></td></tr>
  <tr><td></td><td></td><td></td><td>Delores</td><td></td><td></td><td>Mar. 13, 1986</td></tr>
</table>
<h2>EMILIE'S FIRST FAMILY</h2>
<table>
  {HEADER}
  <tr><td>Reine</td><td>July 15, 1926</td><td>Oct. 25, 1943</td><td>Paul Bru</td><td>3</td><td>5</td><td></td></tr>
  <tr><td>Emilienne</td><td>Feb. 18, 1930</td><td>, 1950</td><td>Claude Cadrian</td><td>2</td><td>3</td><td></td></tr>
</table>
<table>
  <tr><td>TOTAL DESCENDANTS</td><td>83</td></tr>
  <tr><td>LIVING</td><td>78</td></tr>
  <tr><td>DECEASED</td><td>5</td></tr>
</table>
"""


EMILIE_WORSE_CANDIDATE = """
<h1>Emilie L'Heureux Nolin</h1>
<table>
  <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
  <tr><td>Emilie</td><td>June 8, 1898</td><td>Sept. 22, 1922</td><td>Patrick Nolin</td><td>1 / 1</td><td>June 23, 1947</td></tr>
  <tr><td>Herve P.</td><td>July 12, 1923</td><td>Jan. 22, 1946</td><td>Delores Lessard</td><td>0 / 3</td><td>Mar. 13, 1986</td></tr>
</table>
<p>EMILIE'S FIRST FAMILY</p>
<p>Reine July 15, 1926 Oct. 25, 1943 Paul Bru 3 / 5</p>
<p>Emilienne Feb. 18, 1930 , 1950 Claude Cadrian 2 / 3</p>
<p>TOTAL DESCENDANTS 83</p>
<p>LIVING 78</p>
<p>DECEASED 5</p>
"""


EMILIE_SPLIT_CONTINUATION = """
<h3>PAULETTE'S FAMILY</h3>
<table>
  <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
  <tr><td>Tammy Lynn</td><td>Apr. 1, 1972</td><td></td><td></td><td></td><td></td></tr>
</table>
<h3>Emilie's Grandchildren<br>EMILIENNE'S FAMILY</h3>
<table>
  <tr><td>Gilles</td><td>Mar. 17, 1952</td><td>Mar. 6, 1982</td><td>Eleonore Thieson</td><td>0</td><td></td></tr>
</table>
<h3>Emilie's Great Grandchildren<br>Emilienne's Grandchildren<br>CORINE'S FAMILY</h3>
<table>
  <tr><td>Trina</td></tr>
</table>
"""


EMILIE_MERGED_CONTINUATION = """
<table>
  <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY</th><th>GIRL</th><th>DIED</th></tr>
  <tr class="genealogy-subgroup-heading"><th colspan="7">PAULETTE'S FAMILY</th></tr>
  <tr><td>Tammy Lynn</td><td>Apr. 1, 1972</td><td></td><td></td><td></td><td></td><td></td></tr>
  <tr class="genealogy-subgroup-heading"><th colspan="7">Emilie's Grandchildren</th></tr>
  <tr class="genealogy-subgroup-heading"><th colspan="7">EMILIENNE'S FAMILY</th></tr>
  <tr><td>Gilles</td><td>Mar. 17, 1952</td><td>Mar. 6, 1982</td><td>Eleonore Thieson</td><td>0</td><td></td><td></td></tr>
  <tr class="genealogy-subgroup-heading"><th colspan="7">Emilie's Great Grandchildren</th></tr>
  <tr class="genealogy-subgroup-heading"><th colspan="7">Emilienne's Grandchildren</th></tr>
  <tr class="genealogy-subgroup-heading"><th colspan="7">CORINE'S FAMILY</th></tr>
  <tr><td>Trina</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</table>
"""


ALMA_INLINE_FAMILY_ROWS = """
<table>
  <thead>
    <tr><th>NAME</th><th>BORN</th><th>MARRIED</th><th>SPOUSE</th><th>BOY/GIRL</th><th>DIED</th></tr>
  </thead>
  <tbody>
    <tr><td>Robert</td><td>Sept. 30, 1958</td><td>Oct. 11, 1980</td><td>Caren Rathie</td><td>2</td><td></td></tr>
    <tr><th>MAXINE'S FAMILY</th></tr>
    <tr><td>Loren</td><td>July 28, 1962</td><td></td><td></td><td></td><td></td></tr>
    <tr><th>MARCELLA'S FAMILY</th></tr>
    <tr><td>Paul</td><td>July 30, 1974</td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>
"""


def test_accepts_candidate_when_family_child_rows_are_recovered():
    accepted, reason, existing_quality, candidate_quality = _should_accept_rescue(
        ARTHUR_HEADING_ONLY,
        ARTHUR_WITH_CHILD_ROWS,
        0.8,
        15,
    )

    assert accepted is True
    assert reason in {"candidate_score_improved", "candidate_recovered_header_table"}
    assert candidate_quality.row_count > existing_quality.row_count


def test_accepts_candidate_when_paragraph_tail_becomes_table():
    accepted, reason, existing_quality, candidate_quality = _should_accept_rescue(
        ROSEANNA_PARAGRAPH_TAIL,
        ROSEANNA_MIXED_TABLE,
        0.8,
        15,
    )

    assert accepted is True
    assert reason == "candidate_recovered_header_table"
    assert existing_quality.header_table_count == 0
    assert candidate_quality.header_table_count > 0


def test_rejects_candidate_that_drops_structure_and_merges_counts():
    accepted, reason, existing_quality, candidate_quality = _should_accept_rescue(
        EMILIE_BETTER_EXISTING,
        EMILIE_WORSE_CANDIDATE,
        0.8,
        15,
    )

    assert accepted is False
    assert reason in {"candidate_lost_header_table", "candidate_score_not_improved"}
    assert candidate_quality.score < existing_quality.score


def test_quality_penalizes_paragraph_data_and_slash_counts():
    paragraph_quality = _page_rescue_quality(ROSEANNA_PARAGRAPH_TAIL, 0.8)
    degraded_quality = _page_rescue_quality(EMILIE_WORSE_CANDIDATE, 0.8)

    assert paragraph_quality.outside_table_data_lines >= 3
    assert degraded_quality.combined_boy_girl_headers == 1
    assert degraded_quality.slash_count_cells >= 2


def test_accepts_candidate_when_split_continuation_becomes_single_subgroup_table():
    accepted, reason, existing_quality, candidate_quality = _should_accept_rescue(
        EMILIE_SPLIT_CONTINUATION,
        EMILIE_MERGED_CONTINUATION,
        0.8,
        15,
    )

    assert accepted is True
    assert reason == "candidate_score_improved"
    assert candidate_quality.table_count == 1
    assert candidate_quality.inline_family_heading_count == 0
    assert existing_quality.table_count > candidate_quality.table_count


def test_accepts_normalized_existing_when_it_repairs_split_continuation():
    normalized_existing = _normalize_rescue_html(EMILIE_SPLIT_CONTINUATION)

    accepted, reason, existing_quality, candidate_quality = _should_accept_rescue(
        EMILIE_SPLIT_CONTINUATION,
        normalized_existing,
        0.8,
        15,
    )

    assert accepted is True
    assert reason == "candidate_score_improved"
    assert candidate_quality.table_count == 1
    assert candidate_quality.inline_family_heading_count == 0
    assert existing_quality.table_count > candidate_quality.table_count


def test_only_applies_normalized_existing_when_it_collapses_to_single_table():
    normalized_existing = _normalize_rescue_html(EMILIE_SPLIT_CONTINUATION)
    existing_quality = _page_rescue_quality(EMILIE_SPLIT_CONTINUATION, 0.8)
    normalized_quality = _page_rescue_quality(normalized_existing, 0.8)

    assert _should_apply_normalized_existing(existing_quality, normalized_quality) is True

    arthur_normalized = _normalize_rescue_html(ARTHUR_WITH_CHILD_ROWS)
    arthur_existing_quality = _page_rescue_quality(ARTHUR_WITH_CHILD_ROWS, 0.8)
    arthur_normalized_quality = _page_rescue_quality(arthur_normalized, 0.8)

    assert _should_apply_normalized_existing(arthur_existing_quality, arthur_normalized_quality) is False


def test_applies_normalized_existing_when_it_splits_inline_family_rows_into_tables():
    normalized_existing = _normalize_rescue_html(ALMA_INLINE_FAMILY_ROWS)
    existing_quality = _page_rescue_quality(ALMA_INLINE_FAMILY_ROWS, 0.8)
    normalized_quality = _page_rescue_quality(normalized_existing, 0.8)

    assert normalized_quality.table_count > existing_quality.table_count
    assert normalized_quality.header_table_count > existing_quality.header_table_count
    assert normalized_quality.inline_family_heading_count == 0
    assert _should_apply_normalized_existing(existing_quality, normalized_quality) is True
