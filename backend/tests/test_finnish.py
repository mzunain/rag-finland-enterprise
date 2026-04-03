from app.finnish import finnish_search_text, finnish_stems, normalize_finnish_chars, stem_overlap_ratio


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
    high = stem_overlap_ratio("Mitkä ovat yrityksen lomatiedot?", "yritys loma tieto henkilosto")
    low = stem_overlap_ratio("Mitkä ovat yrityksen lomatiedot?", "tekninen rajapinta api")
    assert high > low


def test_finnish_queries_match_same_policy_theme():
    chunk = finnish_search_text("Vuosilomaa kertyy 2.5 arkipäivää kuukaudessa")
    q1 = stem_overlap_ratio("Paljonko lomaa kertyy?", chunk)
    q2 = stem_overlap_ratio("Mikä on vuosiloman määrä?", chunk)
    q3 = stem_overlap_ratio("Kerro lomakäytäntö", chunk)
    assert q1 > 0
    assert q2 > 0
    assert q3 > 0
