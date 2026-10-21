"""Tests for the built-in demo (Me at the zoo): written transcript, same job flow as uploads."""

from asl_util.demo import SENTENCES, YOUTUBE_ID, demo_segments, timed_words

from test_jobs import wait_for


def test_words_are_spread_in_order_across_their_sentence():
    words = timed_words(1.0, 3.0, "All right so here")
    assert [w.text for w in words] == ["All", "right", "so", "here"]
    assert words[0].start == 1.0 and abs(words[-1].end - 3.0) < 0.02
    assert all(a.end <= b.start + 1e-6 for a, b in zip(words, words[1:]))


def test_demo_segments_match_the_written_sentences():
    segments = demo_segments()
    assert [s.text for s in segments] == [text for _, _, text in SENTENCES]
    assert all(s.words for s in segments)


def test_demo_endpoint_runs_as_a_job_and_is_cached(client):
    first = client.post("/api/demo")
    assert first.status_code == 202
    assert first.get_json()["demo"]["youtube_id"] == YOUTUBE_ID
    done = wait_for(lambda: client.get(f"/api/jobs/{first.get_json()['id']}").get_json())
    assert done["status"] == "done"
    assert len(done["result"]["segments"]) == len(SENTENCES)
    second_id = client.post("/api/demo").get_json()["id"]
    again = wait_for(lambda: client.get(f"/api/jobs/{second_id}").get_json())
    assert again["result"] == done["result"]


def test_demo_page_is_served(frontend):
    assert frontend.get("/demo").status_code == 200


def test_demo_result_is_kept_only_when_every_sign_is_animated():
    from app import all_animated

    def result(*media):
        return {"segments": [{"signs": [{"media": m} for m in media]}]}

    animated = {"type": "video", "pose": "/poses/482.json"}
    assert all_animated(result(animated, {"type": "image"}, None))
    assert not all_animated(result(animated, {"type": "video"}))
