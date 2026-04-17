from app.finnish import (
    decompose_finnish_compound,
    finnish_search_text,
    finnish_stems,
    normalize_finnish_chars,
    stem_overlap_ratio,
)


def test_finnish_stems_produces_tokens():
    stems = finnish_stems("Mitkä ovat yrityksen lomatiedot?")
    assert len(stems) >= 3


def test_normalize_finnish_chars_maps_umlauts():
    normalized = normalize_finnish_chars("Työntekijä löytää lomakäytännön")
    assert "ä" not in normalized
    assert "ö" not in normalized


def test_search_text_non_empty_for_finnish_sentence():
    value = finnish_search_text("Yrityksen lomatiedot löytyvät henkilöstöoppaasta.")
    assert isinstance(value, str)
    assert value


def test_stem_overlap_ratio_prefers_similar_terms():
    chunk_high = finnish_search_text("Yrityksen lomatiedot löytyvät henkilöstöoppaasta.")
    chunk_low = finnish_search_text("Tekninen rajapinta käyttää REST-protokollaa.")
    high = stem_overlap_ratio("Mitkä ovat yrityksen lomatiedot?", chunk_high)
    low = stem_overlap_ratio("Mitkä ovat yrityksen lomatiedot?", chunk_low)
    assert high > low


def test_finnish_queries_match_same_policy_theme():
    chunk = finnish_search_text("Vuosilomaa kertyy 2.5 arkipäivää kuukaudessa")
    q1 = stem_overlap_ratio("Paljonko lomaa kertyy?", chunk)
    q2 = stem_overlap_ratio("Mikä on vuosiloman määrä?", chunk)
    q3 = stem_overlap_ratio("Paljonko vuosilomaa kertyy kuukaudessa?", chunk)
    assert q1 > 0
    assert q2 > 0
    assert q3 > 0


def test_stem_overlap_empty_inputs():
    assert stem_overlap_ratio("", "jotain tekstia") == 0.0
    assert stem_overlap_ratio("kysymys", "") == 0.0
    assert stem_overlap_ratio("", "") == 0.0


def test_finnish_search_text_deterministic():
    text = "Työntekijän vuosiloma on 25 arkipäivää"
    assert finnish_search_text(text) == finnish_search_text(text)


def test_decompose_finnish_compound_splits_policy_term():
    parts = decompose_finnish_compound("tietoturvakaytanto")
    assert len(parts) == 2
    assert parts[0].startswith("tieto")


def test_compound_decomposition_improves_overlap():
    chunk = finnish_search_text("Tietoturvakäytäntö määrittelee salasanavaatimukset.")
    score = stem_overlap_ratio("Mikä on tieto turva käytäntö?", chunk)
    assert score > 0
