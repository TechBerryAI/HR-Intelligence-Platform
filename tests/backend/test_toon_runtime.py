"""TOON round-trip, tabular encoding, and back-compatibility with stored docs.

The encoder writes object arrays as a tabular block (columns declared once).
Documents written before that change carry no banner and use dotted paths; they
are still in the database, so the reader has to handle both and the two must
agree on every legacy document.
"""
from __future__ import annotations

import pytest

from app.ai.toon.runtime import FORMAT_BANNER, toon_dumps, toon_loads, toon_loads_flex

RESUME = {
    'type': 'resume',
    'person': {
        'name': 'Abrar Kumbharlikar',
        'email': 'abrar@example.com',
        'phone': '+919619463501',
        'location': 'Mumbai',
    },
    'summary': 'Business development specialist.',
    'skills': ['Python', 'SQL', 'Negotiation'],
    'experience': [
        {'title': 'Analyst', 'company': 'Acme, Inc.', 'from': '2018-09', 'to': 'Present'},
        {'title': 'Associate', 'company': 'Globex', 'from': '2015-07', 'to': '2018-08'},
    ],
    'education': [
        {'degree': 'B.Sc. IT', 'institution': 'SM Shetty College, Mumbai', 'to': '2014'},
    ],
}


def test_object_arrays_use_a_tabular_block():
    out = toon_dumps(RESUME)
    assert 'experience[2]{title,company,from,to}:' in out
    # The dotted form is what the table replaces.
    assert 'experience.0.title' not in out
    assert out.startswith(FORMAT_BANNER)


def test_round_trip_is_exact():
    assert toon_loads(toon_dumps(RESUME)) == RESUME


def test_tabular_is_smaller_than_json():
    import json

    assert len(toon_dumps(RESUME)) < len(json.dumps(RESUME, ensure_ascii=False))


@pytest.mark.parametrize(
    'value',
    [
        '+919619463501',  # would decay to int 919619463501, losing the '+'
        '2014',           # a year is a string in the contract, not an int
        '8.5',            # a GPA, likewise
        'true',
        'null',
        '',
    ],
)
def test_numeric_and_keyword_strings_survive_as_strings(value):
    assert toon_loads(toon_dumps({'v': value}))['v'] == value


def test_numeric_strings_survive_inside_a_table():
    doc = {'rows': [{'phone': '+919619463501', 'year': '2014'}]}
    assert toon_loads(toon_dumps(doc)) == doc


def test_single_element_scalar_list_stays_a_list():
    doc = {'skills': ['Soft']}
    assert toon_loads(toon_dumps(doc)) == doc


def test_empty_list_stays_an_empty_list():
    assert toon_loads(toon_dumps({'skills': []})) == {'skills': []}


def test_real_numbers_stay_numbers():
    doc = {'score': 87, 'ratio': 0.5, 'ok': True, 'nope': False}
    assert toon_loads(toon_dumps(doc)) == doc


def test_cells_containing_commas_and_quotes_survive():
    doc = {'rows': [{'a': 'Shetty College, Mumbai', 'b': 'said "hi"', 'c': 'x|y'}]}
    assert toon_loads(toon_dumps(doc)) == doc


def test_multiline_cell_survives():
    doc = {'rows': [{'desc': 'line one\nline two', 'n': 'x'}]}
    assert toon_loads(toon_dumps(doc)) == doc


def test_uneven_arrays_fall_back_to_dotted_paths():
    """A key missing from one row must not be invented as an empty string."""
    doc = {'rows': [{'a': '1', 'b': '2'}, {'a': '3'}]}
    out = toon_dumps(doc)
    assert '{' not in out.split('\n', 1)[1]  # no table header
    assert toon_loads(out) == doc


def test_nested_values_in_array_items_fall_back_to_dotted_paths():
    doc = {'rows': [{'a': 'x', 'sub': {'k': 'v'}}]}
    assert toon_loads(toon_dumps(doc)) == doc


def test_reader_still_parses_legacy_dotted_documents():
    """Exactly the bytes the previous encoder produced, banner absent."""
    legacy = (
        'type: resume\n'
        'person.name: Abrar Kumbharlikar\n'
        'person.email: abrar@example.com\n'
        'skills: Python|SQL|Negotiation\n'
        'experience.0.title: Analyst\n'
        'experience.0.company: Acme\n'
        'experience.1.title: Associate\n'
        'experience.1.company: Globex\n'
        'certifications[0]:\n'
    )
    assert toon_loads(legacy) == {
        'type': 'resume',
        'person': {'name': 'Abrar Kumbharlikar', 'email': 'abrar@example.com'},
        'skills': ['Python', 'SQL', 'Negotiation'],
        'experience': [
            {'title': 'Analyst', 'company': 'Acme'},
            {'title': 'Associate', 'company': 'Globex'},
        ],
        'certifications': [],
    }


def test_tables_and_dotted_paths_can_share_a_document():
    doc = (
        f'{FORMAT_BANNER}\n'
        'type: resume\n'
        'education[1]{degree,to}:\n'
        '  B.Sc. IT,"2014"\n'
        'person.name: Abrar\n'
        'experience.0.title: Analyst\n'
    )
    assert toon_loads(doc) == {
        'type': 'resume',
        'education': [{'degree': 'B.Sc. IT', 'to': '2014'}],
        'person': {'name': 'Abrar'},
        'experience': [{'title': 'Analyst'}],
    }


def test_flex_still_reads_historical_json():
    import json

    assert toon_loads_flex(json.dumps(RESUME)) == RESUME


def test_fenced_output_is_tolerated():
    assert toon_loads('```toon\na: 1\n```') == {'a': 1}


def test_empty_input():
    assert toon_loads('') == {}
    assert toon_loads_flex('') == {}


def test_dumps_rejects_non_dict():
    with pytest.raises(TypeError):
        toon_dumps(['not', 'a', 'dict'])


def test_list_mixing_a_dict_and_a_scalar_round_trips():
    """A list that isn't uniformly dicts must not be stringified via repr()."""
    doc = {'items': [{'a': 1}, 'x']}
    out = toon_dumps(doc)
    assert "{'a': 1}" not in out  # would indicate the old str()-fallback bug
    assert toon_loads(out) == doc


def test_list_containing_a_nested_list_round_trips():
    doc = {'items': [[1, 2], 'x', {'a': 1}]}
    out = toon_dumps(doc)
    assert '[1, 2]' not in out  # would indicate the old str()-fallback bug
    assert toon_loads(out) == doc


def test_list_of_lists_round_trips():
    doc = {'matrix': [[1, 2], [3, 4]]}
    assert toon_loads(toon_dumps(doc)) == doc


def test_three_level_nested_list_round_trips():
    """A list of lists of lists must not collapse an inner list into a dict."""
    doc = {'a': [[[1, 2]]]}
    assert toon_loads(toon_dumps(doc)) == doc


def test_mixed_list_alongside_dict_list_round_trips():
    doc = {'items': [{'a': 1}, 'x'], 'rows': [{'a': '1', 'b': '2'}, {'a': '3'}]}
    assert toon_loads(toon_dumps(doc)) == doc


def test_top_level_numeric_string_key_does_not_crash():
    """A field literally named e.g. "2020" must not be mistaken for a list index."""
    assert toon_loads('2020: x') == {'2020': 'x'}


def test_stray_dotted_sibling_after_a_table_does_not_crash():
    """A hallucinated extra line reusing a table's key with a non-numeric next
    segment (e.g. `experience.notes:` after an `experience[N]{...}:` table)
    must degrade gracefully rather than raise, since the whole document would
    otherwise fail to parse over one malformed line."""
    doc = (
        'experience[1]{title,company}:\n'
        '  Analyst,Acme\n'
        'experience.notes: some stray extra line\n'
    )
    assert toon_loads(doc) == {'experience': [{'title': 'Analyst', 'company': 'Acme'}]}
