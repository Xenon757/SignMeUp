"""Tests for matching words to ASL Signbank entries. Uses a hand-built gloss list."""

from asl_util.signbank import (
    GlossIndex,
    SignMedia,
    VideoResolver,
    entry_page_url,
    gloss_root,
    video_url_from_page,
)
from asl_util.translate import Sign
from conftest import FakePages

GLOSSES = {
    "CAT8": 347,
    "CATf": 1037,
    "HELLO": 482,
    "HELLOb": 900,
    "ICE-CREAMix": 2770,
    "WALK3": 1407,
    "WALKb": 314,
    "COMEroll": 55,
}


def test_gloss_root_strips_variant_suffix():
    assert gloss_root("CATf") == "CAT"
    assert gloss_root("WALK3") == "WALK"
    assert gloss_root("ICE-CREAMix") == "ICE-CREAM"
    assert gloss_root("HELLO") == "HELLO"


def test_gloss_root_keeps_all_lowercase_gloss():
    assert gloss_root("ix") == "ix"


def test_exact_gloss_comes_first():
    assert GlossIndex(GLOSSES).candidates("hello") == [("HELLO", 482), ("HELLOb", 900)]


def test_variants_are_found_when_there_is_no_exact_gloss():
    assert GlossIndex(GLOSSES).candidates("cat") == [("CAT8", 347), ("CATf", 1037)]


def test_multi_word_lemma_matches_hyphenated_gloss():
    assert GlossIndex(GLOSSES).candidates("ice cream") == [("ICE-CREAMix", 2770)]


def test_unknown_word_has_no_candidates():
    index = GlossIndex(GLOSSES)
    assert index.candidates("go") == []
    assert index.candidates("") == []


def test_bundled_gloss_file_loads():
    index = GlossIndex.load()
    assert index.candidates("hello")


ENTRY_PAGE = """<table><td id='annotation_idgloss_en_US'>CATf</td></table>
<video id='videoplayer' src="/dictionary/protected_media/glossvideo/ASL/CA/CAT-1037.mp4" controls></video>"""
CAT_VIDEO = "https://aslsignbank.com/dictionary/protected_media/glossvideo/ASL/CA/CAT-1037.mp4"


def test_video_url_is_read_from_entry_page():
    assert video_url_from_page(ENTRY_PAGE) == CAT_VIDEO
    assert video_url_from_page("<html></html>") is None


def test_resolver_fetches_each_entry_once():
    pages = FakePages({entry_page_url(1037): ENTRY_PAGE})
    resolver = VideoResolver(fetch=pages)
    assert resolver.video_url(1037) == CAT_VIDEO
    assert resolver.video_url(1037) == CAT_VIDEO
    assert pages.fetched == ["https://aslsignbank.com/dictionary/gloss/1037.html"]


def test_resolver_remembers_entries_without_video():
    pages = FakePages()
    resolver = VideoResolver(fetch=pages)
    assert resolver.video_url(5) is None
    assert resolver.video_url(5) is None
    assert len(pages.fetched) == 1


def test_resolver_retries_after_network_error():
    pages = FakePages(error=OSError("offline"))
    resolver = VideoResolver(fetch=pages)
    assert resolver.video_url(1037) is None
    assert not resolver.is_cached(1037)


def test_resolver_cache_survives_restart(tmp_path):
    cache = tmp_path / "cache" / "signbank_videos.json"
    VideoResolver(cache, fetch=FakePages({entry_page_url(1037): ENTRY_PAGE})).video_url(1037)

    offline = FakePages(error=OSError("offline"))
    assert VideoResolver(cache, fetch=offline).video_url(1037) == CAT_VIDEO
    assert offline.fetched == []


def test_resolver_ignores_corrupt_cache(tmp_path):
    cache = tmp_path / "signbank_videos.json"
    cache.write_text("not json")
    resolver = VideoResolver(cache, fetch=FakePages({entry_page_url(1037): ENTRY_PAGE}))
    assert resolver.video_url(1037) == CAT_VIDEO


def media(pages):
    return SignMedia(GlossIndex(GLOSSES), VideoResolver(fetch=FakePages(pages)))


def test_sign_gets_first_variant_with_a_video():
    # CAT8 (347) has no video page, so CATf (1037) is used.
    found = media({entry_page_url(1037): ENTRY_PAGE}).for_sign(Sign("cats", "cat", "sign"))
    assert found == {
        "type": "video",
        "url": CAT_VIDEO,
        "gloss": "CATf",
        "page": "https://aslsignbank.com/dictionary/gloss/1037.html",
        "source": "ASL Signbank (CC BY-NC-SA 4.0)",
    }


def test_sign_without_signbank_entry_has_no_media():
    assert media({}).for_sign(Sign("go", "go", "sign")) is None


def test_fingerspelled_letter_uses_bundled_image():
    found = media({}).for_sign(Sign("a", "a", "fingerspell"))
    assert found["type"] == "image"
    assert found["url"] == "/static/img/fingerspelling/a.svg"


def test_non_letter_fingerspelling_has_no_media():
    assert media({}).for_sign(Sign("é", "é", "fingerspell")) is None


def test_for_signs_keeps_order_and_looks_up_repeated_words_once():
    pages = FakePages({entry_page_url(1037): ENTRY_PAGE})
    finder = SignMedia(GlossIndex(GLOSSES), VideoResolver(fetch=pages))
    signs = [Sign("cat", "cat", "sign"), Sign("b", "b", "fingerspell"), Sign("cat", "cat", "sign"), Sign("go", "go", "sign")]
    found = finder.for_signs(signs)
    assert [m and m["type"] for m in found] == ["video", "image", "video", None]
    assert pages.fetched.count(entry_page_url(1037)) == 1
