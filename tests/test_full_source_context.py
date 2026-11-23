import pytest
from curiosity.storyboard import full_source_pack
from curiosity.evidence import catalog


def sources():
    return [{'url':'https://one.edu/x','text':''.join(f'Fictional item number {i} has an original observation under synthetic conditions. ' for i in range(75))},{'url':'https://two.edu/x','text':'Another synthetic original sentence explains a fictional condition, never a real-world fact.'}]


def test_full_body_retains_late_conditions_and_catalog_past_old_forty():
    original=sources();packed=full_source_pack(original)
    assert packed[0]['text']==original[0]['text']
    assert packed[0]['source_coverage']['semantic_window_selection'] is False
    entries=catalog(packed)
    assert any('number 74' in x['quote'] for x in entries.values())


def test_over_budget_full_body_fails_not_silently_truncates():
    with pytest.raises(ValueError,match='explicit context bound'):full_source_pack(sources(),max_source_characters=100)


def test_scope_context_never_splices_bibliography_into_evidence():
    original=sources();original[0]['text']+='\n== References ==\nUnrelated bibliography title.'
    packed=full_source_pack(original)
    assert 'bibliography title' not in packed[0]['text']
    assert packed[0]['source_coverage']['bibliography_excluded']
