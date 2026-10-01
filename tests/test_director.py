"""Testy reżysera: biblioteka stylów i plan, assety (w tym bezpieczeństwo pobierania), analiza rytmu/ruchu na danych syntetycznych,
bramka zatwierdzenia oraz przegląd w przeglądarce na filmach z celowo wstrzykniętymi wadami.

Część bez przeglądarki jest szybka. Testy z markerem `browser` potrzebują Chromium i GSAP 3.12.5 (GSAP_JS).
"""
from __future__ import annotations

import http.client
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from vstudio import assets, director, dscan, jobs, ops, registry, skillgen, styles, workspace
from vstudio.registry import CapabilityError

REPO = Path(__file__).resolve().parents[1]


def call(op: str, /, **args):
    return registry.call(op, args, source="api")


# ============================================================ style i plan

class TestStyles:
    def test_every_style_is_complete(self):
        assert len(styles.STYLES) >= 12
        ids = [s["id"] for s in styles.STYLES]
        assert len(ids) == len(set(ids))
        for s in styles.STYLES:
            assert re.fullmatch(r"[a-z0-9-]+", s["id"])
            assert {"bg", "ink", "accent", "accent2"} == set(s["palette"]) and all(re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for c in s["palette"].values())
            assert 1 <= s["energy"] <= 5 and s["tags"] and s["goals"] and s["platforms"] and s["composition"] and s["recipe"].strip()
            assert set(s["pairs_with"]) <= set(ids) and s["id"] not in s["pairs_with"]
            assert set(s["transitions"]) <= set(styles.TRANSITIONS) and set(s["layouts"]) <= set(styles.LAYOUTS)
            assert "latin-ext" in styles.style_text(s)               # polskie znaki to stały punkt uwagi

    def test_recommend_is_deterministic_and_picks_by_tone(self):
        a = styles.recommend("Premiera luksusowych perfum", "premium elegancki", "feed", "calm")
        assert a == styles.recommend("Premiera luksusowych perfum", "premium elegancki", "feed", "calm")
        assert a["main"]["id"] == "dark-luxe"
        b = styles.recommend("szybka promocja w sklepie", "zabawny", "tiktok", "fast")
        assert b["main"]["id"] in ("sticker-pop", "neo-brutal", "kinetic-type")
        assert a["main"]["id"] != b["main"]["id"]

    def test_accents_have_other_layouts_than_main_and_each_other(self):
        for goal in ("aplikacja do planowania treningów", "kawiarnia z domowym ciastem", "raport sprzedaży za kwartał"):
            r = styles.recommend(goal, "", "reels", "fast")
            layouts = [r["main"]["look"]["layout"]] + [x["look"]["layout"] for x in r["accents"]]
            assert len(r["accents"]) == 2 and len(set(layouts)) == 3, (goal, layouts)

    def test_prefer_avoid_and_unknown_ids(self):
        assert styles.recommend("x", prefer=["retro-synth"])["main"]["id"] == "retro-synth"
        assert styles.recommend("premium luksus", "elegancki", avoid=["dark-luxe"])["main"]["id"] != "dark-luxe"
        with pytest.raises(Exception, match="nieznany styl"):
            styles.recommend("x", prefer=["nope"])
        with pytest.raises(Exception, match="nieznany styl"):
            styles.get("nope")

    def test_listing_filters_and_polish_diacritics_in_search(self):
        assert all("reels" in styles.get(s["id"])["platforms"] for s in styles.listing(platform="reels"))
        assert any(s["id"] == "dark-luxe" for s in styles.listing(query="luksus"))
        assert any(s["id"] == "swiss-minimal" for s in styles.listing(query="szwajcarski"))
        assert all(s["energy"] >= 4 for s in styles.listing(energy_min=4))

    def test_transitions_are_deterministic_recipes(self):
        for k, t in styles.TRANSITIONS.items():
            assert t["how"] and t["sound"] in ("hit", "whoosh", "pop", "tick", "reveal", "chime", "click"), k
            assert "random" not in t["how"].lower().replace("no math.random", "")


class TestPlan:
    def _proj(self, studio, duration=8, size="540x960"):
        call("project_create", slug="p", brand="t", size=size, duration=duration)
        return workspace.resolve("t/p")

    @pytest.mark.parametrize("duration,platform", [(6, "reels"), (8, "tiktok"), (15, "feed"), (30, "web"), (3, "reels")])
    def test_beats_tile_the_film_and_no_neighbours_share_a_style(self, studio, duration, platform):
        pdir, pr = self._proj(studio, duration)
        p = director.plan(pdir, pr, "Premiera aplikacji do planowania treningów", platform=platform)
        beats = p["beats"]
        assert beats[0]["role"] == "hook" and beats[-1]["role"] == "cta"
        assert beats[0]["t0"] == 0 and beats[-1]["t1"] == float(duration)
        assert all(abs(a["t1"] - b["t0"]) < 0.02 for a, b in zip(beats, beats[1:]))
        assert all(a["style"] != b["style"] for a, b in zip(beats, beats[1:]))
        assert all(a["layout"] != b["layout"] for a, b in zip(beats, beats[1:]))
        gap = director.PACE_GAP[p["pace"]]
        assert all(b["t1"] - b["t0"] <= gap + 1.0 for b in beats), [b["t1"] - b["t0"] for b in beats]
        assert beats[0]["transition_in"] is None and all(b["transition_in"] for b in beats[1:])
        assert len({b["style"] for b in beats}) >= (2 if duration >= 6 else 1)

    def test_plan_is_saved_deterministic_and_writes_storyboard_without_losing_notes(self, studio):
        pdir, pr = self._proj(studio)
        (pdir / "STORYBOARD.md").write_text("moje notatki o filmie", encoding="utf-8")
        p1 = director.plan(pdir, pr, "Kawiarnia z domowym ciastem", tone="ciepły", platform="reels", write_storyboard=True)
        saved = json.loads((pdir / "director" / "plan.json").read_text(encoding="utf-8"))
        assert saved["beats"] == p1["beats"] and director.load_plan(pdir)["goal"] == "Kawiarnia z domowym ciastem"
        assert "moje notatki" in (pdir / "STORYBOARD.previous.md").read_text(encoding="utf-8")
        assert (pdir / "STORYBOARD.md").read_text(encoding="utf-8").startswith("<!-- director -->")
        p2 = director.plan(pdir, pr, "Kawiarnia z domowym ciastem", tone="ciepły", platform="reels", write_storyboard=True)
        assert p2["beats"] == p1["beats"]
        assert "moje notatki" in (pdir / "STORYBOARD.previous.md").read_text(encoding="utf-8")        # drugi zapis nie nadpisuje kopii naszym planem

    def test_validation_and_brand_tokens(self, studio):
        pdir, pr = self._proj(studio)
        with pytest.raises(Exception, match="goal"):
            director.plan(pdir, pr, "  ")
        with pytest.raises(Exception, match="platform"):
            director.plan(pdir, pr, "x", platform="myspace")
        with pytest.raises(Exception, match="pace"):
            director.plan(pdir, pr, "x", pace="warp")
        call("profile_set", name="Marka", palette={"accent": "#00B894"}, font="Manrope")
        p = director.plan(pdir, pr, "x film")
        assert p["brand"]["palette"]["accent"] == "#00B894" and p["brand"]["font"] == "Manrope"

    def test_platform_is_inferred_from_the_format(self, studio):
        assert director.platform_for({"size": [1080, 1920]}) == "reels"
        assert director.platform_for({"size": [1080, 1350]}) == "reels" or director.platform_for({"size": [1080, 1350]}) == "feed"
        assert director.platform_for({"size": [1080, 1080]}) == "feed"
        assert director.platform_for({"size": [1920, 1080]}) == "web"

    def test_operations_are_registered_and_return_the_plan(self, studio):
        self._proj(studio)
        r = call("director_plan", project="t/p", goal="Premiera aplikacji", platform="reels", prefer=["glass-ui"])
        assert r["plan"]["styles"]["main"]["id"] == "glass-ui"
        assert call("director_latest", project="t/p")["plan"]["goal"] == "Premiera aplikacji"
        with pytest.raises(CapabilityError):
            call("director_plan", project="t/p", goal="x", prefer=["nope"])


# ============================================================ analiza na danych syntetycznych

class TestDscan:
    def test_events_and_gaps(self):
        step = 0.1
        times = [round(i * step, 3) for i in range(80)]
        series = [0.0] * 80
        for i in range(21, 27):
            series[i] = 0.5                                  # nowa sytuacja około 2.1-2.6 s
        for i in range(60, 64):
            series[i] = 0.4                                  # i około 6.0 s
        ev = dscan.find_events(times, series)
        assert ev[0] == 0.0 and len(ev) == 3 and 2.0 <= ev[1] <= 2.2 and 5.9 <= ev[2] <= 6.1
        assert dscan.slow_gaps(ev, 8.0, 3.5) == [(ev[1], ev[2])] or dscan.slow_gaps(ev, 8.0, 3.5)[0][0] == ev[1]
        assert dscan.slow_gaps([0.0, 2.0, 4.0, 6.0], 8.0, 2.5) == []
        assert dscan.slow_gaps([0.0], 6.0, 2.5) == [(0.0, 6.0)]
        assert dscan.slow_gaps([0.0, 3.0], 5.0, 2.5, tail_bonus=1.0) == [(0.0, 3.0)]        # końcowy odcinek ma dodatkowy margines na CTA

    def test_close_events_are_merged(self):
        times = [i * 0.1 for i in range(50)]
        series = [0.0] * 50
        series[10] = series[14] = 0.5
        assert len(dscan.find_events(times, series, min_sep=0.7)) == 2

    def test_look_clusters_separate_distinct_colours_and_layouts(self):
        import numpy as np

        def frame(bg, block=None):
            f = np.full((80, 64, 3), bg, dtype=np.uint8)
            if block:
                f[10:30, 5:55] = block
            return f

        times = [round(i * 0.5, 2) for i in range(8)]
        same = [frame((20, 20, 30)) for _ in times]
        _, n_same, _ = dscan.look_clusters(same, times)
        assert n_same == 1
        mixed = [frame((20, 20, 30))] * 2 + [frame((250, 220, 60), (30, 30, 30))] * 2 + [frame((60, 110, 250), (255, 255, 255))] * 2 + [frame((20, 20, 30))] * 2
        labels, n, _ = dscan.look_clusters(mixed, times)
        assert n == 3 and labels[0] == labels[3]
        assert [dscan.required_looks(d) for d in (3, 7, 14, 30)] == [1, 2, 3, 4]

    def test_block_change_counts_extent_not_stroke_area(self):
        import numpy as np

        a = np.zeros((80, 64, 3), np.uint8)
        headline = a.copy()
        for row in range(30, 42):
            headline[row, 6:58:3] = 255                                   # kreski liter: tylko kilka % pikseli, ale szeroko w kadrze
        corner = a.copy()
        corner[2:8, 2:8] = 255                                            # drobny licznik w rogu
        assert dscan.chg(a, headline) < 0.06 and dscan.block_change(a, headline) >= 0.12
        assert dscan.block_change(a, corner) <= 0.03
        assert dscan.block_change(a, np.full_like(a, 255)) == 1.0 and dscan.block_change(a, a) == 0.0

    def test_hook_strength_and_chg(self):
        import numpy as np

        a = np.zeros((40, 32, 3), np.uint8)
        b = a.copy()
        b[:20] = 200
        assert dscan.chg(a, a) == 0 and dscan.chg(a, b) == pytest.approx(0.5, abs=0.02)
        assert dscan.hook_strength([a, a, b], [0.0, 0.5, 1.0]) == pytest.approx(0.5, abs=0.02)
        assert dscan.hook_strength([a, a, b], [0.0, 0.5, 2.0]) == 0.0                    # zmiana po 1.5 s nie liczy się do haka

    def test_flash_windows(self):
        steady = [0.5 + 0.01 * (i % 2) for i in range(40)]
        assert dscan.flash_windows(steady, 0.1) == []
        strobing = [0.1 if i % 2 else 0.9 for i in range(40)]
        assert dscan.flash_windows(strobing, 0.1)
        slow = [0.1 if (i // 8) % 2 else 0.9 for i in range(80)]                       # zmiana co 0.8 s: bezpieczna
        assert dscan.flash_windows(slow, 0.1) == []

    @staticmethod
    def _rows(positions, n=40):
        return [[[1, -1, positions(f), 100.0, 50.0, 50.0, 1.0]] for f in range(n)]

    def test_linear_and_eased_motion_are_told_apart(self):
        linear = dscan.motion_segments(self._rows(lambda f: 10.0 * min(f, 30)), 30, 1000.0)
        eased = dscan.motion_segments(self._rows(lambda f: 300.0 * (1 - (1 - min(f, 30) / 30) ** 3)), 30, 1000.0)
        assert [s["easing"] for s in linear if s["kind"] == "pos"] == ["linear"]
        assert [s["easing"] for s in eased if s["kind"] == "pos"] == ["eased"]
        assert dscan.easing_summary(linear)["share"] == 1.0 and dscan.easing_summary(eased)["share"] == 0.0

    def test_long_drifts_do_not_count_as_linear_moves(self):
        drift = dscan.motion_segments(self._rows(lambda f: 4.0 * f, n=100), 30, 1000.0)
        assert dscan.easing_summary(drift)["moves"] == 0                                # >2 s: dryf liniowy jest normalny

    def test_child_motion_is_relative_to_its_parent(self):
        rows = [[[1, -1, 10.0 * f, 100.0, 400.0, 100.0, 1.0], [2, 1, 10.0 * f + 5, 100.0, 50.0, 50.0, 1.0]] for f in range(30)]
        segs = dscan.motion_segments(rows, 30, 1000.0)
        assert {s["el"] for s in segs if s["kind"] == "pos"} == {1}                    # dziecko jedzie razem z rodzicem: nie ma własnego ruchu

    def test_stagger_groups(self):
        def fade(start):
            return ([0.0] * start + [min(1.0, 0.1 * (i + 1)) for i in range(10)] + [1.0] * 60)[:60]

        def rows(starts, parent=-1):
            return [[[100 + k, parent, 50.0, 50.0 + 20 * k, 40.0, 10.0, fade(s)[f]] for k, s in enumerate(starts)] for f in range(35)]

        together = dscan.stagger_groups(dscan.motion_segments(rows([5] * 8), 30, 1000.0))
        assert together and together[0]["count"] == 8
        spread = dscan.stagger_groups(dscan.motion_segments(rows([5 + 3 * k for k in range(8)]), 30, 1000.0))
        assert spread == []

    def test_overlap_fraction_and_text_norm(self):
        assert dscan.overlap_fraction((0, 0, 10, 10), (5, 0, 15, 10)) == 0.5
        assert dscan.overlap_fraction((0, 0, 10, 10), (20, 20, 30, 30)) == 0
        assert dscan.overlap_fraction((0, 0, 100, 100), (10, 10, 20, 20)) == 1.0       # mniejszy w całości przykryty
        assert dscan.norm_text("  Ala  MA\nkota ") == "alamakota"


# ============================================================ assety

class TestAssets:
    def test_builtin_icons_are_valid_svg_and_survive_the_sanitizer(self):
        assert len(assets.ICONS) >= 60
        for iid in assets.ICONS:
            svg = assets.sanitize_svg(assets._icon_svg(iid))
            assert svg.startswith("<svg") and "viewBox" in svg and "currentColor" in svg, iid

    def test_search_in_english_and_polish(self):
        assert assets.search_builtin("koszyk")[0]["name"] == "cart"
        assert assets.search_builtin("rocket")[0]["name"] == "rocket"
        assert assets.search_builtin("ŻARÓWKA pomysł")[0]["name"] == "bulb"                # polskie znaki i wielkość liter
        assert assets.search_builtin("zzzxxy") == []
        assert len(assets.search_builtin("", 5)) == 5

    def test_generators_are_deterministic_valid_and_in_the_given_colours(self, studio):
        call("project_create", slug="g", brand="t")
        pdir, _ = workspace.resolve("t/g")
        colours = ["#FF0066", "#00CCAA", "#FFFFFF", "#101820"]
        for kind, (fn, _d, (w, h)) in assets.GENERATORS.items():
            a, b, c = fn(3, colours, w, h), fn(3, colours, w, h), fn(4, colours, w, h)
            assert a == b, kind
            assets.sanitize_svg(a)
            if kind not in ("rays", "grid", "grain", "arrow", "squiggle", "starburst"):
                assert a != c, f"{kind}: inne ziarno ma dawać inną grafikę"
        r = assets.generate(pdir, "blob", seed=5, colors=colours, name="Moja plama")
        assert r["file"] == "moja-plama.svg" and (pdir / "src" / "assets" / r["file"]).read_text(encoding="utf-8").count("#FF0066") >= 1
        again = assets.generate(pdir, "blob", seed=5, colors=colours, name="Moja plama")
        assert again["file"] == "moja-plama-2.svg"                                        # nie nadpisujemy
        with pytest.raises(Exception, match="nieznany generator"):
            assets.generate(pdir, "nope")
        with pytest.raises(Exception, match="width/height"):
            assets.generate(pdir, "blob", width=5)

    def test_svg_sanitizer_removes_active_content(self):
        dirty = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10" onload="alert(1)">'
                 '<script>alert(1)</script><foreignObject><div>x</div></foreignObject><style>@import url(http://evil/x.css)</style>'
                 '<image href="http://evil/p.png"/><a href="javascript:alert(1)"><circle cx="5" cy="5" r="4" onclick="x()" style="fill:url(http://evil/g)"/></a>'
                 '<use href="http://evil/s.svg#a"/><use xlink:href="#ok"/><rect id="ok" width="3" height="3" fill="url(#g)"/></svg>')
        clean = assets.sanitize_svg(dirty)
        low = clean.lower()
        for bad in ("script", "foreignobject", "onload", "onclick", "evil", "javascript", "<style", "<image", "<a "):
            assert bad not in low, bad
        assert "<circle" in clean or "<rect" in clean and 'url(#g)' in clean

    def test_svg_sanitizer_rejects_entities_garbage_and_huge_files(self):
        with pytest.raises(assets.FetchError, match="DOCTYPE"):
            assets.sanitize_svg('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">&a;</svg>')
        with pytest.raises(assets.FetchError, match="poprawny"):
            assets.sanitize_svg("<svg><g></svg>")
        with pytest.raises(assets.FetchError, match="svg"):
            assets.sanitize_svg("<html xmlns='http://www.w3.org/1999/xhtml'></html>")
        with pytest.raises(assets.FetchError, match="większy"):
            assets.sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">' + "<g/>" * 90_000 + "</svg>")
        assert 'viewBox="0 0 20 10"' in assets.sanitize_svg('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="5" height="5"/></svg>')

    @pytest.mark.parametrize("url,why", [
        ("http://example.com/a.png", "https"), ("ftp://example.com/a.png", "https"), ("https://user:pw@example.com/a.png", "logowania"),
        ("https://localhost/a.png", "lokalny"), ("https://printer.local/a.png", "lokalny"), ("https://example.com:8443/a.png", "443"),
        ("https://127.0.0.1/a.png", "publiczny"), ("https://10.1.2.3/a.png", "publiczny"), ("https://192.168.0.5/a.png", "publiczny"),
        ("https://169.254.169.254/latest/meta-data", "publiczny"), ("https://[::1]/a.png", "publiczny"), ("https://[::ffff:127.0.0.1]/a.png", "publiczny"),
        ("https://100.64.0.1/a.png", "publiczny"), ("https://0.0.0.0/a.png", "publiczny"),
    ])
    def test_unsafe_urls_are_rejected_before_any_connection(self, url, why):
        with pytest.raises(assets.FetchError, match=why):
            assets.check_url(url)

    def test_a_hostname_resolving_to_a_private_address_is_rejected(self, monkeypatch):
        monkeypatch.setattr(assets.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.0.0.7", 443))])
        with pytest.raises(assets.FetchError, match="publiczny"):
            assets.check_url("https://innocent.example.com/x.png")
        monkeypatch.setattr(assets.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("127.0.0.1", 443))])
        with pytest.raises(assets.FetchError, match="publiczny"):
            assets.check_url("https://mixed.example.com/x.png")                              # wystarczy jeden zły adres
        monkeypatch.setattr(assets.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
        assert assets.check_url("https://ok.example.com/x.png") == ["93.184.216.34"]

    def _fake_http(self, monkeypatch, body: bytes, ctype="image/png", length=None):
        class Resp:
            headers = {"Content-Type": ctype, **({"Content-Length": str(length)} if length is not None else {})}

            def __init__(self):
                self.pos = 0

            def read(self, n=-1):
                chunk = body[self.pos:self.pos + (n if n > 0 else len(body))]
                self.pos += len(chunk)
                return chunk

            def geturl(self):
                return "https://cdn.example.com/x"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class Opener:
            def open(self, req, timeout=None):
                return Resp()

        monkeypatch.setattr(assets, "check_url", lambda url: ["93.184.216.34"])
        monkeypatch.setattr(assets, "_opener", lambda: Opener())

    def test_download_limits_are_enforced(self, monkeypatch):
        self._fake_http(monkeypatch, b"x" * 5000, length=10_000_000)
        with pytest.raises(assets.FetchError, match="limit"):
            assets.http_get("https://cdn.example.com/x", max_bytes=1000)
        self._fake_http(monkeypatch, b"x" * 5000)                                             # brak Content-Length: liczymy przy czytaniu
        with pytest.raises(assets.FetchError, match="limit"):
            assets.http_get("https://cdn.example.com/x", max_bytes=1000)
        self._fake_http(monkeypatch, b"x" * 500)
        assert assets.http_get("https://cdn.example.com/x", max_bytes=1000)[0] == b"x" * 500

    @staticmethod
    def _png(size=(3000, 2000), alpha=False) -> bytes:
        import io

        from PIL import Image

        im = Image.new("RGBA" if alpha else "RGB", size, (200, 30, 60, 128) if alpha else (200, 30, 60))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()

    def test_raster_is_resized_reencoded_and_content_is_sniffed(self):
        data, ext, size = assets.process_raster(self._png())
        assert ext == "jpg" and max(size) == assets.MAX_SIDE and data[:3] == b"\xff\xd8\xff"        # bez alfy: JPEG
        data, ext, _ = assets.process_raster(self._png((200, 100), alpha=True))
        assert ext == "png"                                                                       # z alfą zostaje PNG
        with pytest.raises(assets.FetchError, match="obraz"):
            assets.process_raster(b"not an image at all")
        assert assets.sniff(self._png((4, 4))) == "png" and assets.sniff(b'<svg xmlns="http://www.w3.org/2000/svg"/>') == "svg"
        with pytest.raises(assets.FetchError, match="nie jest obrazem"):
            assets.sniff(b"<html><script>alert(1)</script></html>")

    def test_add_from_url_records_licence_credits_and_snippet(self, studio, monkeypatch):
        call("project_create", slug="a", brand="t")
        pdir, _ = workspace.resolve("t/a")
        self._fake_http(monkeypatch, self._png((400, 300)))
        r = assets.add(pdir, "https://cdn.example.com/photo.png", name="Zdjęcie kawiarni")
        assert r["file"].startswith("zdjecie-kawiarni") and r["kind"] == "photo" and r["snippet"]["mode"] == "img"
        assert 'src="assets/zdjecie-kawiarni' in r["snippet"]["html"] and r["snippet"]["size"] == [400, 300]
        rows = assets.listing(pdir)
        assert rows[0]["origin"] == "url" and "sprawdź prawa" in rows[0]["license"]
        assert assets.credits(pdir) and "assets/zdjecie-kawiarni" in assets.credits(pdir)[0]
        removed = assets.remove(pdir, r["file"])
        assert removed == {"removed": r["file"]} and assets.listing(pdir) == [] and assets.credits(pdir) == []
        for bad in ("../project.json", "ASSETS.json", "nope.png"):
            with pytest.raises(Exception, match="brak assetu"):
                assets.remove(pdir, bad)

    def test_html_disguised_as_an_image_is_refused(self, studio, monkeypatch):
        call("project_create", slug="a", brand="t")
        pdir, _ = workspace.resolve("t/a")
        self._fake_http(monkeypatch, b"<html><script>alert(1)</script></html>", ctype="image/png")
        with pytest.raises(assets.FetchError):
            assets.add(pdir, "https://cdn.example.com/evil.png")
        assert assets.listing(pdir) == []

    def test_iconify_and_openverse_filter_licences(self, studio, monkeypatch):
        call("project_create", slug="a", brand="t")
        pdir, _ = workspace.resolve("t/a")

        def fake_json(url):
            if "api.iconify.design/search" in url:
                return {"icons": ["lucide:rocket", "weird:rocket", "twemoji:rocket"], "collections": {
                    "lucide": {"name": "Lucide", "license": {"spdx": "ISC"}, "author": {"name": "Lucide Contributors"}},
                    "weird": {"name": "Weird", "license": {"spdx": "CC-BY-NC-4.0"}},
                    "twemoji": {"name": "Twemoji", "license": {"spdx": "CC-BY-4.0"}, "author": {"name": "Twitter"}}}}
            if "collection?prefix=lucide" in url:
                return {"info": {"license": {"spdx": "ISC", "url": "https://isc"}, "author": {"name": "Lucide Contributors"}}}
            if "collection?prefix=weird" in url:
                return {"info": {"license": {"spdx": "CC-BY-NC-4.0"}}}
            if "api.openverse.org/v1/images/?" in url:
                return {"results": [{"id": "a1b2c3d4-0000-0000-0000-000000000001", "title": "Tea", "license": "by", "license_version": "4.0", "creator": "Ola", "url": "https://img/t.jpg", "attribution": "Tea by Ola"},
                                    {"id": "a1b2c3d4-0000-0000-0000-000000000002", "title": "NC", "license": "by-nc", "url": "https://img/n.jpg"}]}
            if "api.openverse.org/v1/images/a1b2c3d4-0000-0000-0000-000000000002/" in url:
                return {"id": "x", "license": "by-nc", "url": "https://img/n.jpg"}
            raise AssertionError(url)

        monkeypatch.setattr(assets, "get_json", fake_json)
        res = assets.search("rocket", "iconify")["results"]
        assert [r["id"] for r in res] == ["iconify:lucide:rocket", "iconify:twemoji:rocket"]          # NC odrzucone
        assert res[1]["attribution"] == "Twitter" and res[0]["attribution"] is None
        ov = assets.search("tea", "openverse")["results"]
        assert [r["name"] for r in ov] == ["Tea"] and ov[0]["attribution"] == "Tea by Ola"
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M1 1h5v5z"/></svg>'
        self._fake_http(monkeypatch, svg, ctype="image/svg+xml")
        r = assets.add(pdir, "iconify:lucide:rocket")
        assert r["file"] == "rocket.svg" and r["license"] == "ISC" and r["snippet"]["mode"] == "inline"
        assert "Lucide Contributors" in assets.credits(pdir)[0] and "ISC" in assets.credits(pdir)[0]
        with pytest.raises(assets.FetchError, match="nie jest na liście"):
            assets.add(pdir, "iconify:weird:rocket")
        with pytest.raises(assets.FetchError, match="nie jest dozwolona"):
            assets.add(pdir, "openverse:a1b2c3d4-0000-0000-0000-000000000002")
        with pytest.raises(Exception, match="iconify:<zestaw>"):
            assets.add(pdir, "iconify:../etc")
        with pytest.raises(Exception, match="ref:"):
            assets.add(pdir, "file:///etc/passwd")
        with pytest.raises(Exception, match="source"):
            assets.search("x", "bing")

    def test_builtin_add_recolours_and_snippets_are_inline(self, studio):
        call("project_create", slug="a", brand="t")
        r = call("assets_add", project="t/a", ref="builtin:cart", color="#FF0066")
        assert r["file"] == "cart.svg" and 'stroke="#FF0066"' in r["snippet"]["html"] and r["snippet"]["mode"] == "inline"
        assert call("assets_snippet", project="t/a", file="cart.svg", mode="img")["html"].startswith("<img")
        listing = call("assets_list", project="t/a")
        assert listing["assets"][0]["origin"] == "builtin" and listing["builtin_icons"] == len(assets.ICONS) and len(listing["generators"]) == len(assets.GENERATORS)
        with pytest.raises(CapabilityError, match="color"):
            call("assets_add", project="t/a", ref="builtin:cart", color="red")
        with pytest.raises(CapabilityError, match="wbudowanej"):
            call("assets_add", project="t/a", ref="builtin:nope")
        g = call("assets_generate", project="t/a", kind="mesh", seed=2)                          # kolory z profilu marki
        assert g["file"].startswith("mesh-2") and "<feGaussianBlur" in (workspace.resolve("t/a")[0] / "src" / "assets" / g["file"]).read_text(encoding="utf-8")
        assert call("assets_remove", project="t/a", file="cart.svg") == {"removed": "cart.svg"}


# ============================================================ stan, sign-off i bramka

REPORT_BASE = {"round": 1, "at": "2026-01-01T00:00:00", "depth": "standard", "verdict": "pass", "score": 99, "counts": {"error": 0, "warn": 0, "info": 0}, "findings": [],
               "delta": None, "next_actions": [], "metrics": {}, "assets": None, "checklist": director.CHECKLIST}
ALL_CHECKED = {k: True for k in director.CHECKLIST}


def _fake_review(pdir: Path, findings=()):
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("error", "warn", "info")}
    rep = {**REPORT_BASE, "project": "t/s", "counts": counts, "findings": list(findings), "scene_hash": director.scene_hash(pdir),
           "verdict": "blocked" if counts["error"] else "needs_fixes" if counts["warn"] else "pass"}
    (pdir / "director").mkdir(exist_ok=True)
    (pdir / "director" / "latest.json").write_text(json.dumps(rep), encoding="utf-8")
    return rep


def _finding(code, severity):
    return {"code": code, "severity": severity, "title": code, "detail": "d", "t": 1.0, "box": None, "fix": "f", "id": ""}


class TestSignoff:
    def _proj(self, studio):
        call("project_create", slug="s", brand="t", template="hide-the-cut")
        return workspace.resolve("t/s")

    def test_state_machine(self, studio):
        pdir, _ = self._proj(studio)
        assert director.state(pdir)["state"] == "none"
        _fake_review(pdir)
        assert director.state(pdir)["state"] == "reviewed" and director.state(pdir)["review_fresh"]
        director.signoff(pdir, True, "Obejrzałem taśmę: hak w 0.3 s, zmiany co 2 s.", ALL_CHECKED)
        assert director.state(pdir)["state"] == "approved"
        call("scene_patch", project="t/s", edits=[{"find": "<title>", "replace": "<title>x "}]) if "<title>" in (pdir / "src" / "index.html").read_text(encoding="utf-8") else (pdir / "src" / "index.html").write_text((pdir / "src" / "index.html").read_text(encoding="utf-8") + "\n<!-- zmiana -->", encoding="utf-8")
        st = director.state(pdir)
        assert st["state"] == "stale" and not st["review_fresh"]                                # zmiana sceny unieważnia decyzję
        with pytest.raises(Exception, match="zmieniła się"):
            director.signoff(pdir, True, "Obejrzałem taśmę, wszystko gra.", ALL_CHECKED)
        _fake_review(pdir)
        director.signoff(pdir, False, "Hak za słaby: nic się nie dzieje do 2 s.", {})
        assert director.state(pdir)["state"] == "rejected"

    def test_approval_rules(self, studio):
        pdir, _ = self._proj(studio)
        with pytest.raises(Exception, match="najpierw director_review"):
            director.signoff(pdir, True, "Obejrzałem wszystko dokładnie.", ALL_CHECKED)
        _fake_review(pdir, [_finding("TEXT_CLIPPED", "error")])
        with pytest.raises(Exception, match="błędami.*TEXT_CLIPPED"):
            director.signoff(pdir, True, "Obejrzałem wszystko dokładnie.", ALL_CHECKED)
        director.signoff(pdir, False, "Tekst przycięty w 2 s: popraw kontener.", {})              # odrzucenie z błędami jest dozwolone
        _fake_review(pdir, [_finding("SLOW_PACE", "warn"), _finding("NO_VISUAL_ASSETS", "info")])
        with pytest.raises(Exception, match="ostrzeżenia bez decyzji.*SLOW_PACE"):
            director.signoff(pdir, True, "Obejrzałem wszystko dokładnie.", ALL_CHECKED)
        with pytest.raises(Exception, match="powód"):
            director.signoff(pdir, True, "Obejrzałem wszystko dokładnie.", ALL_CHECKED, {"SLOW_PACE": "ok"})
        with pytest.raises(Exception, match="checklista.*rhythm"):
            director.signoff(pdir, True, "Obejrzałem wszystko dokładnie.", {**ALL_CHECKED, "rhythm": False}, {"SLOW_PACE": "celowa cisza w otwarciu"})
        with pytest.raises(Exception, match="12 znaków"):
            director.signoff(pdir, True, "ok", ALL_CHECKED, {"SLOW_PACE": "celowa cisza w otwarciu"})
        r = director.signoff(pdir, True, "Obejrzałem wszystko: cisza w otwarciu jest celowa.", ALL_CHECKED, {"SLOW_PACE": "celowa cisza w otwarciu"})
        assert r["state"] == "approved" and r["signoff"]["accepted"] == {"SLOW_PACE": "celowa cisza w otwarciu"}

    def test_signoff_records_who_decided_from_the_call_source_not_from_arguments(self, studio):
        pdir, _ = self._proj(studio)
        _fake_review(pdir)
        r = registry.call("director_signoff", {"project": "t/s", "approve": True, "notes": "Obejrzałem klatki: wszystko gra.", "checklist": ALL_CHECKED}, source="mcp")
        assert r["signoff"]["by"] == "agent (MCP)"
        _fake_review(pdir)
        r = registry.call("director_signoff", {"project": "t/s", "approve": True, "notes": "Obejrzałem klatki: wszystko gra.", "checklist": ALL_CHECKED}, source="dashboard")
        assert r["signoff"]["by"] == "człowiek (dashboard)"
        with pytest.raises(CapabilityError, match="nieznane parametry"):
            registry.call("director_signoff", {"project": "t/s", "approve": True, "notes": "x" * 20, "by": "człowiek"}, source="mcp")

    def test_final_render_and_delivery_are_gated(self, studio, monkeypatch):
        pdir, _ = self._proj(studio)
        started = []
        monkeypatch.setattr(ops, "_need", lambda *t: None)
        monkeypatch.setattr(jobs, "start", lambda kind, pid, d, args, source="api": started.append((kind, args)) or {"id": "J-00000000", "kind": kind})
        call("render_start", project="t/s")                                                         # draft nie jest objęty bramką
        for op, kw in (("render_start", {"final": True}), ("deliver_start", {})):
            with pytest.raises(CapabilityError, match="brak zatwierdzenia reżysera.*none"):
                call(op, project="t/s", **kw)
        _fake_review(pdir)
        with pytest.raises(CapabilityError, match="reviewed"):
            call("render_start", project="t/s", final=True)
        director.signoff(pdir, True, "Obejrzałem klatki: wszystko gra.", ALL_CHECKED)
        r = call("render_start", project="t/s", final=True)
        assert all("check_run" in w for w in r["warnings"]) and call("deliver_start", project="t/s")["warnings"] == []      # tylko uwaga nadzorcy, nie reżysera
        (pdir / "src" / "index.html").write_text((pdir / "src" / "index.html").read_text(encoding="utf-8") + "\n<!-- edit -->", encoding="utf-8")
        with pytest.raises(CapabilityError, match="stale"):
            call("render_start", project="t/s", final=True)
        r = call("render_start", project="t/s", final=True, skip_review=True)
        assert "skip_review" in r["warnings"][0]
        call("profile_set", require_director=False)
        assert call("deliver_start", project="t/s")["warnings"] == []
        assert [k for k, _ in started].count("render") == 3

    def test_director_state_shows_up_in_project_summaries(self, studio):
        pdir, _ = self._proj(studio)
        assert call("projects_list")["projects"][0]["director"]["state"] == "none"
        _fake_review(pdir)
        director.signoff(pdir, True, "Obejrzałem klatki: wszystko gra.", ALL_CHECKED)
        p = call("projects_list")["projects"][0]
        assert p["director"] == {"state": "approved", "verdict": "pass", "score": 99}
        assert any("director_review" in n for n in call("studio_status")["next"]) is False        # zatwierdzony: brak przypomnienia


# ============================================================ agent-recenzent, skill, MCP

class TestAgentSurface:
    def test_reviewer_agent_file_matches_the_generator_and_has_no_edit_tools(self):
        text = skillgen.render_agent()
        assert (REPO / "agents" / "vstudio-director.md").read_text(encoding="utf-8") == text, "odśwież: python vstudio.py skill --write"
        front = text.split("---")[1]
        tools = [t.strip() for t in re.search(r"tools: (.*)", front).group(1).split(",")]
        mcp = {t.removeprefix("mcp__vstudio__") for t in tools if t.startswith("mcp__vstudio__")}
        assert mcp <= set(registry.REGISTRY), mcp - set(registry.REGISTRY)
        assert not {t for t in mcp if registry.REGISTRY[t].mutates and t not in ("director_review", "director_signoff", "check_run")}
        assert not {"scene_write", "scene_patch", "scene_recolor", "scene_restore", "assets_add", "render_start", "gate_set"} & mcp
        assert all(k in text for k in director.CHECKLIST) and "name: vstudio-director" in text

    def test_install_writes_the_agent_next_to_the_skill(self, studio):
        from vstudio import agentkit

        assert agentkit.connect_info()["director_agent"]["installed"] is False
        r = call("agent_install", mcp_config=False)
        dest = Path(r["installed"]["director_agent"])
        assert dest.name == "vstudio-director.md" and dest.read_text(encoding="utf-8") == skillgen.render_agent()
        assert agentkit.connect_info()["director_agent"]["installed"] is True
        assert "director_agent" not in call("agent_install", mcp_config=False, director=False)["installed"]

    def test_skill_and_knowledge_teach_the_director_loop(self):
        skill = skillgen.render()
        for needle in ("director_plan", "director_review", "director_signoff", "vstudio-director", "assets_search", "SLOW_PACE", "GLYPH_MISSING", "refuse to start"):
            assert needle in skill, needle
        from vstudio import knowledge

        assert {"direction", "styles", "assets"} <= set(knowledge.TOPICS)
        assert "kinetic-type" in knowledge.get("styles")["text"] and "every 2-3 s" in knowledge.get("direction")["text"]
        assert "MONOTONE_STYLE" in knowledge.get("findings")["text"]
        assert registry.call("check_explain", {"code": "SLOW_PACE"}, source="api")["fix"].startswith("Nothing visibly new")
        assert registry.call("check_explain", {"code": "NONDETERMINISTIC"}, source="api")["title"]

    def test_mcp_exposes_director_tools_and_prompts(self):
        from vstudio.mcp_server import McpServer

        srv = McpServer()
        srv.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
        names = {t["name"] for t in srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]}
        assert {"director_plan", "director_review", "director_signoff", "director_latest", "styles_list", "style_get", "assets_search", "assets_add", "assets_generate"} <= names
        prompts = {p["name"] for p in srv.handle({"jsonrpc": "2.0", "id": 3, "method": "prompts/list"})["result"]["prompts"]}
        assert {"direct-video", "review-video"} <= prompts
        got = srv.handle({"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "direct-video", "arguments": {"idea": "premiera apki"}}})
        assert "director_plan" in json.dumps(got) and "premiera apki" in json.dumps(got)

    def test_cli_styles_assets_and_director_plan(self, studio):
        run = lambda *a: subprocess.run([sys.executable, str(REPO / "vstudio.py"), *a], capture_output=True, text=True, cwd=REPO, timeout=60)  # noqa: E731
        assert "kinetic-type" in run("styles").stdout
        assert "Naklejki" in run("styles", "sticker-pop").stdout or "Sticker" in run("styles", "sticker-pop").stdout
        assert "builtin:cart" in run("assets", "search", "koszyk").stdout
        r = run("--json", "assets", "search", "shopping", "--limit", "2")
        assert r.returncode == 0 and len(json.loads(r.stdout)["results"]) == 2
        assert run("styles", "nope").returncode != 0


# ============================================================ serwer: SVG bez uprawnień dashboardu

class TestSvgServing:
    def test_svg_and_html_served_from_files_cannot_run_with_dashboard_origin(self, studio):
        from vstudio.dashboard import server

        call("project_create", slug="v", brand="t")
        pdir, _ = workspace.resolve("t/v")
        assets.add(pdir, "builtin:star")
        (pdir / "src" / "page.html").write_text("<script>1</script>", encoding="utf-8")
        srv, _ = server.start_background()
        try:
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1])
            c.request("GET", "/files/t/v/src/assets/star.svg")
            r = c.getresponse()
            body = r.read()
            assert r.status == 200 and r.getheader("Content-Type") == "image/svg+xml" and r.getheader("Content-Security-Policy") == "sandbox"
            assert r.getheader("X-Content-Type-Options") == "nosniff" and body.startswith(b"<svg")
            c.request("GET", "/files/t/v/src/page.html")
            r = c.getresponse()
            r.read()
            assert r.getheader("Content-Security-Policy") == "sandbox allow-scripts"
            c.request("GET", "/preview/t/v/assets/star.svg")
            r = c.getresponse()
            r.read()
            assert r.status == 200 and r.getheader("Content-Security-Policy") == "sandbox"
        finally:
            srv.shutdown()


# ============================================================ przegląd w przeglądarce: filmy z wstrzykniętymi wadami

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;height:100%;overflow:hidden;background:{bg};font-family:{font}}}
.abs{{position:absolute}} .t{{position:absolute;margin:0;white-space:nowrap}}
{css}</style></head><body>{body}
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script>
var DUR={dur}, CAPTURE=!!window.__CAPTURE__;
gsap.config({{force3D:false}});
var tl=gsap.timeline({{repeat:-1,paused:CAPTURE}});
{js}
tl.set({{}},{{}},DUR);
if(CAPTURE){{tl.totalTime(DUR-0.001,false);tl.totalTime(0,false);}}
window.DURATION=DUR; window.EV=[];
window.seek=function(t){{tl.pause();tl.totalTime(((t%DUR)+DUR)%DUR,false);}};
window.TEXTS=function(t){{ {texts} }};
window.__ready=Promise.all([document.fonts.ready].concat([].slice.call(document.images).map(function(i){{return i.decode().catch(function(){{}});}})));
</script></body></html>"""

TEXTS_FROM_DOM = """
  function eff(e){var o=1;for(;e&&e.nodeType===1;e=e.parentElement){o*=parseFloat(getComputedStyle(e).opacity);}return o;}
  return [].slice.call(document.querySelectorAll('.t')).filter(function(e){return eff(e)>0.05;}).map(function(e,i){var r=e.getBoundingClientRect();
    return {id:e.id||('t'+i),text:e.textContent,x0:r.left,y0:r.top,x1:r.right,y1:r.bottom};});"""


def page(body="", js="", *, dur=6, bg="#ffffff", css="", font="sans-serif", texts="return [];"):
    return PAGE.format(body=body, js=js, dur=dur, bg=bg, css=css, font=font, texts=texts)


def dynamic_film() -> str:
    """6 s, trzy sceny po 2 s z twardym cięciem: różne tło, układ, ikona i tekst; wszystko animowane z wygładzeniem."""
    body = """
<div id="s1" class="abs" style="inset:0;background:#101820;opacity:0"><p class="t" id="a1" style="left:6%;top:12%;font:700 11vw sans-serif;color:#fff">Zażółć gęślą</p></div>
<div id="s2" class="abs" style="inset:0;background:#FFD93D;opacity:0"><p class="t" id="a2" style="left:8%;bottom:30%;font:700 9vw sans-serif;color:#111">Jaźń i ćma</p><div class="abs" id="i2" style="right:10%;top:12%;width:20vw;height:20vw;color:#111">{rocket}</div></div>
<div id="s3" class="abs" style="inset:0;background:#3A6BFF;opacity:0"><p class="t" id="a3" style="left:20%;top:44%;font:700 10vw sans-serif;color:#fff">Dołącz dziś</p><div class="abs" id="b3" style="left:20%;top:62%;width:40vw;height:8vw;background:#fff;border-radius:99px"></div></div>"""
    from vstudio import assets as a

    body = body.replace("{rocket}", a._icon_svg("rocket"))
    js = """
tl.set('#s1',{opacity:1},0); tl.set('#s2',{opacity:0},0); tl.set('#s3',{opacity:0},0);
tl.fromTo('#a1',{y:60,opacity:0},{y:0,opacity:1,duration:.6,ease:'expo.out'},0.05);
tl.set('#s1',{opacity:0},2); tl.set('#s2',{opacity:1},2);
tl.fromTo('#a2',{x:-80,opacity:0},{x:0,opacity:1,duration:.6,ease:'power3.out'},2.05);
tl.fromTo('#i2',{scale:.2,opacity:0},{scale:1,opacity:1,duration:.5,ease:'back.out(1.6)'},2.2);
tl.set('#s2',{opacity:0},4); tl.set('#s3',{opacity:1},4);
tl.fromTo('#a3',{y:-60,opacity:0},{y:0,opacity:1,duration:.6,ease:'expo.out'},4.05);
tl.fromTo('#b3',{scaleX:0,transformOrigin:'left'},{scaleX:1,duration:.7,ease:'power2.out'},4.3);"""
    return page(body, js, texts=TEXTS_FROM_DOM)


def static_film() -> str:
    body = '<p class="t" id="a" style="left:10%;top:40%;font:700 9vw sans-serif;color:#eee">Cały czas to samo</p>'
    return page(body, "tl.to('#a',{y:-3,duration:DUR,ease:'none'},0);", bg="#14181f", texts=TEXTS_FROM_DOM)


def flicker_film() -> str:
    return ("<!doctype html><html><body style='margin:0'><script>window.DURATION=3;window.EV=[];window.TEXTS=function(){return [];};"
            "window.__ready=Promise.resolve();window.seek=function(t){document.body.style.background=(Math.floor(t*10)%2)?'#fff':'#000';};</script></body></html>")


@pytest.fixture
def film(vendored_studio):
    """Tworzy projekt 540x960 (9:16, 30 fps, 6 s) i zwraca funkcję wgrywającą scenę."""
    call("project_create", slug="f", brand="t", size="540x960", duration=6)

    def put(html: str) -> tuple[Path, dict]:
        call("scene_write", project="t/f", content=html)
        return workspace.resolve("t/f")

    return put


def codes(rep: dict) -> set[str]:
    return {f["code"] for f in rep["findings"]}


@pytest.mark.browser
class TestReviewInBrowser:
    def test_a_dynamic_film_has_events_looks_and_no_pacing_findings(self, film):
        pdir, pr = film(dynamic_film())
        rep = director.review(pdir, pr, depth="standard")
        m = rep["metrics"]
        assert len(m["events"]) >= 3 and any(1.8 <= e <= 2.3 for e in m["events"]) and any(3.8 <= e <= 4.3 for e in m["events"]), m["events"]
        assert m["looks"] >= 3 and m["gaps"] == [], (m["looks"], m["gaps"])
        assert not codes(rep) & {"SLOW_PACE", "MONOTONE_STYLE", "TEXT_CLIPPED", "TEXT_HIDDEN", "TEXT_OVERLAP", "TEXTS_INCOMPLETE", "GLYPH_MISSING", "ASSET_BROKEN", "FLASH_RISK"}, rep["findings"]
        assert m["assets_visible"] >= 1 and "NO_VISUAL_ASSETS" not in codes(rep)
        assert m["texts"] >= 3 and m["platform"] == "reels" and m["max_gap"] == 2.5
        assert rep["verdict"] in ("pass", "needs_fixes") and rep["scene_hash"] == director.scene_hash(pdir)
        assert (pdir / "director" / "latest.json").exists() and (pdir / "director" / "review-001" / "rhythm.png").stat().st_size > 2000
        assert set(rep["checklist"]) == set(director.CHECKLIST)

    def test_a_static_film_is_flagged_for_pace_hook_and_monotony(self, film):
        pdir, pr = film(static_film())
        rep = director.review(pdir, pr, depth="quick")
        assert {"SLOW_PACE", "WEAK_HOOK", "MONOTONE_STYLE"} <= codes(rep), rep["findings"]
        assert rep["verdict"] == "needs_fixes" and rep["metrics"]["gaps"] == [[0.0, 6.0]]
        slow = next(f for f in rep["findings"] if f["code"] == "SLOW_PACE")
        assert slow["t"] == 0.0 and "limit dla reels" in slow["detail"]
        again = director.review(pdir, pr, depth="quick")
        assert again["round"] == 2 and again["delta"]["persisting"] >= 3 and again["delta"]["resolved"] == []

    def test_pace_follows_the_platform(self, film):
        pdir, pr = film(dynamic_film())
        calm = director.review(pdir, pr, platform="web", depth="quick", save=False)
        assert calm["metrics"]["max_gap"] == 5.0 and calm["metrics"]["pace"] == "calm"
        with pytest.raises(Exception, match="platform"):
            director.review(pdir, pr, platform="myspace")
        with pytest.raises(Exception, match="depth"):
            director.review(pdir, pr, depth="forever")

    def test_text_that_is_not_really_visible_is_caught(self, film):
        body = """
<div class="abs" style="left:20px;top:60px;width:110px;height:34px;overflow:hidden"><p class="t" id="clip" style="position:static;font:28px sans-serif;color:#111">Bardzo długi tekst przycięty</p></div>
<p class="t" id="hid" style="left:30px;top:200px;font:44px sans-serif;color:#111">Zasłonięty napis</p><div class="abs" style="left:20px;top:190px;width:420px;height:70px;background:#c00;z-index:5"></div>
<p class="t" id="o1" style="left:30px;top:400px;font:44px sans-serif;color:#111">Pierwszy napis</p><p class="t" id="o2" style="left:60px;top:410px;font:44px sans-serif;color:#06c">Drugi napis</p>
<p class="t" id="ell" style="left:30px;top:560px;width:120px;overflow:hidden;text-overflow:ellipsis;font:30px sans-serif;color:#111">Bardzo długi napis z wielokropkiem</p>
<p class="t" id="fnt" style="left:30px;top:700px;font:30px 'NoSuchFont123', serif;color:#111">Zły font</p>"""
        pdir, pr = film(page(body, "tl.to('#hid',{x:0,duration:DUR,ease:'none'},0);"))
        rep = director.review(pdir, pr, depth="standard")
        got = codes(rep)
        assert {"TEXT_CLIPPED", "TEXT_HIDDEN", "TEXT_OVERLAP", "TEXT_TRUNCATED", "TEXTS_INCOMPLETE", "FONT_FALLBACK"} <= got, rep["findings"]
        by = {f["code"]: f for f in rep["findings"]}
        assert "Zasłonięty" in by["TEXT_HIDDEN"]["detail"] and by["TEXT_HIDDEN"]["severity"] == "error"
        assert "Pierwszy" in by["TEXT_OVERLAP"]["detail"] and by["TEXT_OVERLAP"]["box"]
        assert "NoSuchFont123" in by["FONT_FALLBACK"]["detail"] and by["FONT_FALLBACK"]["severity"] == "info"
        assert not [f for f in rep["findings"] if f["code"] == "TEXT_HIDDEN" and "Pierwszy" in f["detail"]]      # widoczne napisy nie są „ukryte”
        assert rep["verdict"] == "blocked"

    def test_glyph_check_tells_available_fonts_from_missing_ones(self, film):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            br = pw.chromium.launch()
            pg = br.new_page()
            pg.set_content("<html><body>x</body></html>")
            absent = pg.evaluate(dscan.GLYPH_JS, {"family": "'NoSuchFont123', serif", "weight": "400", "style": "normal", "chars": "ąłabc"})
            generic = pg.evaluate(dscan.GLYPH_JS, {"family": "sans-serif", "weight": "400", "style": "normal", "chars": "ąłabc"})
            sans = pg.evaluate(dscan.GLYPH_JS, {"family": "'Liberation Sans', sans-serif", "weight": "400", "style": "normal", "chars": "ąęłńóśźżabc漢"})
            br.close()
        assert absent["available"] is False and absent["missing"] == [] and generic["generic"] is True and generic["missing"] == []
        if not sans["available"]:
            pytest.skip("brak fontu Liberation Sans w systemie")
        assert "ł" not in sans["missing"] and "ą" not in sans["missing"]                      # polskie znaki są w foncie
        assert "漢" in sans["missing"]                                                         # a CJK nie: rysuje je zamiennik

    def test_flashing_is_an_error(self, film):
        pdir, pr = film(flicker_film())
        rep = director.review(pdir, pr, depth="standard", save=False)
        f = next(f for f in rep["findings"] if f["code"] == "FLASH_RISK")
        assert f["severity"] == "error" and rep["verdict"] == "blocked"

    def test_broken_and_working_images(self, film):
        pdir, pr = film(page('<img class="abs" id="bad" src="assets/nope.png" style="left:40px;top:80px;width:200px;height:200px">', texts=TEXTS_FROM_DOM))
        rep = director.review(pdir, pr, depth="quick", save=False)
        assert "ASSET_BROKEN" in codes(rep) and any("nope.png" in f["detail"] for f in rep["findings"])
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (80, 80), (200, 40, 80)).save(buf, "PNG")
        (pdir / "src" / "assets").mkdir(exist_ok=True)
        (pdir / "src" / "assets" / "ok.png").write_bytes(buf.getvalue())
        call("scene_write", project="t/f", content=page('<img class="abs" src="assets/ok.png" style="left:40px;top:80px;width:200px;height:200px">', texts=TEXTS_FROM_DOM))
        rep = director.review(pdir, pr, depth="quick", save=False)
        assert "ASSET_BROKEN" not in codes(rep) and rep["metrics"]["assets_visible"] == 1

    def test_no_assets_is_noticed_and_motion_quality_is_measured(self, film):
        boxes = "".join(f'<div class="abs" id="b{i}" style="left:20px;top:{40 + i * 150}px;width:90px;height:90px;background:hsl({i * 60},70%,50%)"></div>' for i in range(5))
        linear = "".join(f"tl.to('#b{i}',{{x:300,duration:1,ease:'none'}},{0.3 + i * 1.1});" for i in range(5))
        eased = "".join(f"tl.to('#b{i}',{{x:300,duration:1,ease:'power3.out'}},{0.3 + i * 1.1});" for i in range(5))
        pdir, pr = film(page(boxes, linear, texts=TEXTS_FROM_DOM))
        rep = director.review(pdir, pr, depth="standard", save=False)
        assert "LINEAR_MOTION" in codes(rep) and rep["metrics"]["motion"]["share"] >= 0.5 and "NO_VISUAL_ASSETS" in codes(rep)
        call("scene_write", project="t/f", content=page(boxes, eased, texts=TEXTS_FROM_DOM))
        rep = director.review(pdir, pr, depth="standard", save=False)
        assert "LINEAR_MOTION" not in codes(rep) and rep["metrics"]["motion"]["moves"] >= 4

    def test_elements_entering_together_are_reported_unless_staggered(self, film):
        items = "".join(f'<div class="abs" id="e{i}" style="left:{30 + (i % 2) * 220}px;top:{60 + (i // 2) * 110}px;width:180px;height:80px;background:#06c;opacity:0"></div>' for i in range(8))
        together = "".join(f"tl.to('#e{i}',{{opacity:1,duration:.4}},1);" for i in range(8))
        spread = "".join(f"tl.to('#e{i}',{{opacity:1,duration:.4}},{1 + i * 0.12});" for i in range(8))
        pdir, pr = film(page(items, together, texts=TEXTS_FROM_DOM))
        assert "NO_STAGGER" in codes(director.review(pdir, pr, depth="standard", save=False))
        call("scene_write", project="t/f", content=page(items, spread, texts=TEXTS_FROM_DOM))
        assert "NO_STAGGER" not in codes(director.review(pdir, pr, depth="standard", save=False))

    def test_the_film_is_checked_against_the_saved_plan(self, film):
        pdir, pr = film(dynamic_film())
        (pdir / "director").mkdir(exist_ok=True)
        beats = [{"n": i + 1, "role": r, "t0": t0, "t1": t1} for i, (r, t0, t1) in enumerate([("hook", 0, 1.0), ("reveal", 1.0, 5.0), ("cta", 5.0, 6.0)])]
        (pdir / "director" / "plan.json").write_text(json.dumps({"duration": 6, "beats": beats}), encoding="utf-8")
        rep = director.review(pdir, pr, depth="quick", save=False)
        missing = [f for f in rep["findings"] if f["code"] == "BEAT_MISSING"]
        assert len(missing) == 2 and rep["metrics"]["plan_adherence"] == 0.0 and all(f["severity"] == "warn" for f in missing)
        good = director.plan(pdir, pr, "Premiera aplikacji", platform="reels")
        assert good["beats"][0]["t0"] == 0
        (pdir / "director" / "plan.json").write_text(json.dumps({"duration": 9, "beats": beats}), encoding="utf-8")
        assert "PLAN_STALE" in codes(director.review(pdir, pr, depth="quick", save=False))

    def test_pages_that_cannot_be_reviewed_say_why(self, film):
        pdir, pr = film("<!doctype html><html><body>nic</body></html>")
        with pytest.raises(Exception, match="kontraktu"):
            director.review(pdir, pr, depth="quick")
        pdir, pr = film("<!doctype html><html><body><script>window.DURATION=2;window.seek=function(){};window.__ready=Promise.resolve();null.boom();</script></body></html>")
        with pytest.raises(Exception, match="błędy JavaScript"):
            director.review(pdir, pr, depth="quick")

    def test_end_to_end_review_signoff_and_gate_through_the_operations(self, film, monkeypatch):
        film(dynamic_film())
        monkeypatch.setattr(ops, "_need", lambda *t: None)
        monkeypatch.setattr(jobs, "start", lambda kind, pid, d, args, source="api": {"id": "J-00000000", "kind": kind})
        r = registry.call("director_review", {"project": "t/f", "depth": "standard"}, source="mcp")
        assert r["state"]["state"] == "reviewed" and r["counts"]["error"] == 0 and "director_signoff" in r["how_to_continue"]
        labels = [i["label"] for i in r["images"]]
        assert any("taśma" in x for x in labels) and any("rytm" in x for x in labels) and all(Path(i["path"]).is_file() for i in r["images"])
        accept = {c: "celowo w teście" for c in {f["code"] for f in r["findings"] if f["severity"] == "warn"}}
        signed = registry.call("director_signoff", {"project": "t/f", "approve": True, "notes": "Obejrzałem taśmę: trzy sceny, hak w 0.3 s.", "checklist": ALL_CHECKED, "accept": accept}, source="mcp")
        assert signed["state"] == "approved"
        assert registry.call("render_start", {"project": "t/f", "final": True}, source="mcp")["job"]["kind"] == "render"
        call("scene_patch", project="t/f", edits=[{"find": "Dołącz dziś", "replace": "Dołącz teraz"}])
        with pytest.raises(CapabilityError, match="stale"):
            registry.call("render_start", {"project": "t/f", "final": True}, source="mcp")
        latest = call("director_latest", project="t/f")
        assert latest["review"]["round"] == 1 and latest["state"]["state"] == "stale" and latest["history"][0]["verdict"] == r["verdict"]
        assert director.review(*workspace.resolve("t/f"), depth="quick")["delta"]["since_round"] == 1


# ============================================================ interfejs: zakładka Reżyser

@pytest.mark.browser
class TestDirectorUi:
    def test_director_tab_plan_review_assets_and_signoff(self, vendored_studio):
        from playwright.sync_api import sync_playwright

        from vstudio.dashboard import server

        call("profile_set", name="Marka")
        call("project_create", slug="ui", brand="t", template="hide-the-cut")
        srv, _ = server.start_background()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        problems: list[str] = []
        try:
            with sync_playwright() as pw:
                br = pw.chromium.launch(args=["--disable-gpu-rasterization", "--disable-partial-raster"])
                pg = br.new_context(viewport={"width": 1440, "height": 1000}).new_page()
                pg.on("pageerror", lambda e: problems.append(str(e)))
                pg.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
                pg.goto(base + "/#/")
                pg.evaluate("sessionStorage.setItem('onboardSkipped','1')")
                pg.wait_for_function("window.V && V.route_")                           # start aplikacji zakończony: drugi render nie skasuje wpisanych danych
                pg.goto(base + "/#/p/t/ui/rezyser")
                pg.wait_for_selector("#dRun", timeout=30000)
                assert "Brak przeglądu" in pg.inner_text("#pbody") and pg.locator("#dApprove").count() == 0
                # plan
                pg.fill("#pGoal", "Premiera aplikacji do planowania treningów, zachęć do zapisu")
                pg.click("#pGo")
                pg.wait_for_selector(".beats .bt", timeout=20000)
                assert pg.locator(".beats .bt").count() >= 3 and pg.locator(".schip").count() == 3
                assert call("director_latest", project="t/ui")["plan"]["goal"].startswith("Premiera")
                # biblioteka stylów (formularz po zaplanowaniu jest zwinięty: człowiek najpierw go rozwija)
                assert not pg.locator("#pStyles").is_visible()
                pg.click("details summary")
                pg.click("#pStyles")
                pg.wait_for_selector(".modal .scard", timeout=10000)
                assert pg.locator(".modal .scard").count() >= 12
                pg.click(".modal .scard >> nth=0")
                pg.keyboard.press("Escape")
                # assety: wbudowane, wygenerowane
                pg.fill("#aQ", "koszyk")
                pg.click("#aGo")
                pg.wait_for_selector(".aitem [data-add]", timeout=15000)
                assert pg.locator(".aitem .aprev svg").count() >= 1
                pg.click(".aitem [data-add] >> nth=0")
                pg.wait_for_selector(".modal .code", timeout=15000)
                assert "<svg" in pg.inner_text(".modal .code")
                pg.keyboard.press("Escape")
                pg.select_option("#gKind", "blob")
                pg.click("#gGo")
                pg.wait_for_function("document.body.innerText.includes('blob-1.svg')", timeout=15000)
                files = {a["file"] for a in call("assets_list", project="t/ui")["assets"]}
                assert {"cart.svg", "blob-1.svg"} <= files
                # przegląd
                pg.select_option("#dDepth", "quick")
                pg.click("#dRun")
                pg.wait_for_selector("#rchart", timeout=120000)
                assert pg.locator("#rchart .ev").count() >= 1 and pg.locator("#dApprove").count() == 1
                pg.click("#rchart", position={"x": 200, "y": 40})
                assert pg.locator("#rhead").get_attribute("visibility") == "visible"
                # zatwierdzenie: najpierw bez checklisty (błąd), potem poprawnie
                pg.fill("#dNotes", "Obejrzałem taśmę klatek i wykres rytmu.")
                for el in pg.locator("[data-acc]").all():
                    el.fill("celowo: spokojne otwarcie")
                pg.click("#dApprove")
                pg.wait_for_function("document.body.innerText.includes('checklista')", timeout=15000)
                assert call("director_latest", project="t/ui")["state"]["state"] == "reviewed"
                for c in pg.locator("[data-chk]").all():
                    c.check()
                pg.click("#dApprove")
                pg.wait_for_function("document.querySelector('#pbody').innerText.includes('Zatwierdzone')", timeout=20000)
                st = call("director_latest", project="t/ui")["state"]
                assert st["state"] == "approved" and st["signoff"]["by"] == "człowiek (dashboard)"
                br.close()
        finally:
            srv.shutdown()
        # jedyny dozwolony „błąd” w konsoli to odrzucone żądanie z celowo niepełną checklistą (400 z czytelnym komunikatem)
        assert [p for p in problems if "status of 400" not in p and "checklist" not in p.lower() and "approve" not in p.lower()] == [], problems
