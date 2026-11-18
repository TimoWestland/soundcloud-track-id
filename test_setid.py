"""Self-check for the merge logic. Run: python3 test_setid.py"""
import argparse
from pathlib import Path

import setid
from setid import Entry, MIN_STEP, REQUEST_OVERHEAD, UNKNOWN, Hit, auto_step, hms, merge, parse_time, render_markdown, split_title, spotify_track_list, to_hit, with_spotify_tracks

A = dict(key="a", title="A", artist="X")
B = dict(key="b", title="B", artist="Y")


def test_merges_runs_and_flags_long_gaps() -> None:
    hits = [
        Hit(0, **A), Hit(30, **A), Hit(60, **A),
        Hit(90), Hit(120), Hit(150),          # 90s gap -> Unknown ID
        Hit(180, **B), Hit(210, **B),
    ]
    got = [(e.start, e.title) for e in merge(hits, step=30)]
    assert got == [(0, "A"), (90, UNKNOWN), (180, "B")], got


def test_strict_drops_lone_hit_and_default_keeps_it() -> None:
    hits = [Hit(0, **A), Hit(30, **A), Hit(60, **B), Hit(90, **A), Hit(120, **A)]
    got = [(e.start, e.title) for e in merge(hits, step=30, strict=True)]
    assert got == [(0, "A")], got
    loose = [(e.start, e.title) for e in merge(hits, step=30)]
    assert loose == [(0, "A"), (60, "B"), (90, "A")], loose


def test_trailing_gap_and_hms() -> None:
    hits = [Hit(0, **A), Hit(30, **A), Hit(60), Hit(90), Hit(120)]
    got = [(e.start, e.title) for e in merge(hits, step=30)]
    assert got == [(0, "A"), (60, UNKNOWN)], got
    assert hms(3725) == "01:02:05"


def test_to_hit_keeps_only_real_links() -> None:
    track = {"key": 1, "title": "T", "subtitle": "A", "url": "https://www.shazam.com/track/1/t",
             "hub": {"options": [{"caption": "OPEN IN", "actions": [{"uri": "https://music.apple.com/subscribe"}]}],
                     "providers": [{"type": "SPOTIFY"}]}}
    hit = to_hit(0, {"matches": [1], "track": track})
    assert set(hit.links) == {"shazam", "spotify"}, hit.links
    assert to_hit(0, {"matches": []}).key is None


def test_auto_step_fits_budget() -> None:
    for duration in (1800, 3082, 5400, 4 * 3600):
        step = auto_step(duration, pace=15, budget_min=20)
        snippets = (duration - 12) // step + 1
        assert snippets * (15 + REQUEST_OVERHEAD) <= 20 * 60, (duration, step, snippets)
    assert auto_step(600, pace=15, budget_min=20) == MIN_STEP  # short sets keep the minimum spacing


def test_parse_time() -> None:
    assert parse_time("1:57:00") == 7020
    assert parse_time("57:30") == 3450
    assert parse_time("90") == 90
    for bad in ("1:2:3:4", "1h57", "", "-5"):
        try:
            parse_time(bad)
        except argparse.ArgumentTypeError:
            continue
        raise AssertionError(bad)


def test_render_markdown_template() -> None:
    entries = [Entry(0, UNKNOWN, "", {}),
               Entry(540, "A|B", "X", {"shazam": "https://sz/1", "apple_music": "https://am/1", "spotify": "https://sp/1"})]
    md = render_markdown("Set", "https://soundcloud.com/a/b", 12980, 145, 12, entries).splitlines()
    assert md[:8] == ["# Set", "", "[Open in soundcloud →](https://soundcloud.com/a/b)", "",
                      "* Set duration: 03:36:20", "", "* Snippet count: 145", "* Snippet length: 12s"], md
    assert md[-2] == "| 00:00:00 | Unknown ID |  |  |", md[-2]
    assert md[-1] == "| 00:09:00 | X - A\\|B | [Spotify](https://sp/1) | [Shazam](https://sz/1) |", md[-1]


def test_spotify_lookup_once_per_isrc_and_copy_list() -> None:
    search = {"spotify": "https://open.spotify.com/search/A"}
    entries = [Entry(0, "A", "X", dict(search), "ISRC1"), Entry(90, UNKNOWN, "", {}),
               Entry(180, "B", "Y", dict(search), "ISRC2"), Entry(270, "A", "X", dict(search), "ISRC1")]
    calls = []
    def lookup(isrc):
        calls.append(isrc)
        return "https://open.spotify.com/track/1" if isrc == "ISRC1" else None
    got = with_spotify_tracks(entries, lookup)
    assert calls == ["ISRC1", "ISRC2"], calls
    assert got[0].links["spotify"] == "https://open.spotify.com/track/1"
    assert got[2].links == search, "no track found keeps the search link"
    assert entries[0].links == search, "input entries are not mutated"
    assert spotify_track_list(got) == "https://open.spotify.com/track/1", "deduplicated, search links left out"
    assert to_hit(0, {"matches": [1], "track": {"key": 1, "title": "T", "subtitle": "A", "isrc": "C1"}}).isrc == "C1"


def test_split_title() -> None:
    title, body = split_title(render_markdown("Set | Name", "https://soundcloud.com/a/b", 60, 1, 12, []))
    assert title == "Set | Name", title
    assert body.startswith("[Open in soundcloud →](https://soundcloud.com/a/b)"), body
    assert split_title("no heading\n") == ("", "no heading\n")


def test_output_and_cache_dirs() -> None:
    assert setid.OUT_DIR == Path.home() / "Music" / "setid"
    assert setid.CACHE_DIR == Path.home() / "Library" / "Caches" / "setid"
    assert not hasattr(setid, "PROJECT_DIR")


def test_pcm_to_wav_has_real_length() -> None:
    import io, wave
    pcm = b"\x01\x00" * 16000  # one second of 16-bit mono at 16 kHz
    with wave.open(io.BytesIO(setid.pcm_to_wav(pcm, 16000))) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.getnframes() == 16000, w.getnframes()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
