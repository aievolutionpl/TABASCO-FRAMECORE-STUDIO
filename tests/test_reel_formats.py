"""Testy formatów rolek: napisy słowo po słowie, zestaw ruchu, formaty w planie reżysera i szablony `resource-drop` oraz `word-captions`.

Część bez przeglądarki jest szybka. Testy z markerem `browser` potrzebują Chromium i GSAP 3.12.5 (GSAP_JS).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vstudio import assets, captions, director, dscan, registry, styles, supervisor, workspace
from vstudio.registry import CapabilityError

REPO = Path(__file__).resolve().parents[1]
KIT = REPO / "templates" / "motion-kit.js"


def call(op: str, /, **args):
    return registry.call(op, args, source="api")


def words(data: dict) -> list[str]:
    return [w["w"] for ln in data["lines"] for w in ln["words"]]


# ============================================================ napisy: dane

class TestCaptionsData:
    SCRIPT = "Stop scrolling. Ten skill zmienia 3 rzeczy w Twoich filmach, a to jest za darmo!"

    def test_single_style_shows_one_word_and_merges_words_too_short_to_see(self):
        d = captions.build(text=self.SCRIPT, start=1.0, end=7.0, style="single", highlight=["darmo"])
        assert d["style"] == "single" and d["max_words"] == 1 and d["words"] == 15
        assert d["start"] == 1.0 and d["end"] == 7.0
        lines = d["lines"]
        assert all(len(ln["words"]) <= 2 for ln in lines)
        assert [w for ln in lines for w in ln["words"]][0]["w"] == "Stop"
        for ln in lines:
            if len(ln["words"]) == 2:                                    # para tylko wtedy, gdy samo słowo mignęłoby (< MIN_WORD)
                assert ln["words"][0]["t1"] - ln["words"][0]["t0"] < captions.MIN_WORD + 0.05
        assert all(a["t1"] <= b["t0"] + 1e-6 for a, b in zip(lines, lines[1:]))        # linie nie nakładają się w czasie

    def test_numbers_and_listed_words_are_highlighted(self):
        d = captions.build(text=self.SCRIPT, start=0, end=6, style="pop", highlight=["DARMO"])
        hl = {w["w"] for ln in d["lines"] for w in ln["words"] if w["hl"]}
        assert hl == {"3", "darmo!"}                                      # liczba i słowo kluczowe (bez wielkości liter i interpunkcji)
        plain = captions.build(text=self.SCRIPT, start=0, end=6, style="pop", numbers=False)
        assert not any(w["hl"] for ln in plain["lines"] for w in ln["words"])

    def test_pop_groups_words_and_a_sentence_end_starts_a_new_line(self):
        d = captions.build(text="a b c d e f g", style="pop", max_words=3, start=0, end=3.5)
        assert [[w["w"] for w in ln["words"]] for ln in d["lines"]] == [["a", "b", "c"], ["d", "e", "f"], ["g"]]
        s = captions.build(text="Hej tam. Co słychać u was", style="pop", max_words=4, start=0, end=4)
        assert [w["w"] for w in s["lines"][0]["words"]] == ["Hej", "tam."]

    def test_word_times_follow_length_and_punctuation(self):
        ws = captions.spread(["to", "jest", "bardzo,", "długie"], 0.0, 4.0)
        assert ws[0]["t0"] == 0.0 and abs(ws[-1]["t1"] - 4.0) < 1e-2
        assert all(a["t1"] <= b["t0"] + 1e-6 for a, b in zip(ws, ws[1:]))
        d = [w["t1"] - w["t0"] for w in ws]
        assert d[3] > d[0] and d[2] > d[1]                                # dłuższe słowo i słowo z przecinkiem trwają dłużej
        assert captions.words_from_text("raz dwa", 2.0, None, 120)[-1]["t1"] == pytest.approx(3.0, abs=0.01)     # bez końca: wg wpm

    def test_srt_and_vtt_cues_are_spread_inside_each_cue(self):
        srt = "1\n00:00:01,000 --> 00:00:02,500\nTo jest test\n\n2\n00:00:02,500 --> 00:00:04,000\n<i>drugi</i> napis!\n"
        d = captions.build(srt=srt, style="karaoke")
        assert d["start"] == 1.0 and d["end"] == 4.0
        assert [[w["w"] for w in ln["words"]] for ln in d["lines"]] == [["To", "jest", "test"], ["drugi", "napis!"]]
        vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000 align:start\nHej tam\n"
        shifted = captions.build(srt=vtt, start=2)
        assert shifted["start"] == 3.0 and shifted["end"] == 4.0                       # start przesuwa cały plik
        short = captions.build(srt="WEBVTT\n\n00:01.000 --> 00:02.000\nHej\n")
        assert short["start"] == 1.0                                       # mm:ss.mmm bez godzin też się czyta

    def test_exact_word_timestamps_are_sorted_and_accept_common_key_names(self):
        d = captions.build(words=[{"start": 0.5, "end": 0.9, "word": "Cześć"}, {"start": 0.1, "end": 0.4, "text": "Hej"}], style="pop")
        assert words(d) == ["Hej", "Cześć"] and d["start"] == 0.1 and d["end"] == 0.9

    @pytest.mark.parametrize("args, msg", [
        ({}, "dokładnie jedno źródło"),
        ({"text": "a", "srt": "x"}, "dokładnie jedno źródło"),
        ({"text": "a", "style": "wild"}, "style:"),
        ({"text": "a", "wpm": 10}, "wpm"),
        ({"text": "a", "max_words": 9}, "max_words"),
        ({"text": "a", "start": 3, "end": 2}, "koniec"),
        ({"words": [{"t0": 2, "t1": 1, "w": "x"}]}, "t0 <= t1"),
        ({"srt": "brak czasów"}, "brak napisów"),
        ({"srt": "1\n00:00:xx --> 00:00:02,000\nA"}, "brak napisów|nie rozumiem czasu"),
    ])
    def test_bad_input_is_rejected_with_a_reason(self, args, msg):
        import re

        with pytest.raises(Exception) as e:
            captions.build(**args)
        assert re.search(msg, str(e.value)), e.value


class TestCaptionsOps:
    def test_captions_build_writes_data_kit_and_provenance(self, studio):
        call("project_create", slug="c", brand="t", size="1080x1920", duration=8)
        r = call("captions_build", project="t/c", text="Skomentuj ANIMACJA a wyślę Ci link", start=0.5, end=4.5, style="pop", highlight=["animacja"])
        pdir, _ = workspace.resolve("t/c")
        body = (pdir / "src" / "assets" / "captions.js").read_text(encoding="utf-8")
        assert body.startswith("/* vstudio captions") and "window.CAPTIONS = " in body
        data = json.loads(body.split("window.CAPTIONS = ", 1)[1].rstrip().rstrip(";"))
        assert data["style"] == "pop" and data["words"] == 6 and r["words"] == 6 and r["lines"] == len(data["lines"])
        assert (pdir / "src" / "assets" / "motion-kit.js").read_text(encoding="utf-8") == KIT.read_text(encoding="utf-8")
        assert r["rel"] == "assets/captions.js" and r["kit"] == "assets/motion-kit.js" and "VS.captions.mount" in r["snippet"] and "estimated" in r["note"]
        prov = {x["file"]: x for x in assets.listing(pdir)}
        assert {"captions.js", "motion-kit.js"} <= set(prov) and prov["motion-kit.js"]["origin"] == "generated" and prov["captions.js"]["tracked"]

    def test_exact_timings_change_the_note_and_errors_surface_as_capability_errors(self, studio):
        call("project_create", slug="c", brand="t", size="1080x1920", duration=8)
        r = call("captions_build", project="t/c", words=[{"t0": 0, "t1": 0.4, "w": "Hej"}, {"t0": 0.4, "t1": 0.9, "w": "świecie"}])
        assert "Timings taken from your input." == r["note"] and r["words"] == 2
        with pytest.raises(CapabilityError, match="dokładnie jedno"):
            call("captions_build", project="t/c")

    def test_motion_kit_add_installs_the_same_file_everywhere(self, studio):
        call("project_create", slug="k", brand="t")
        r = call("motion_kit_add", project="t/k")
        pdir, _ = workspace.resolve("t/k")
        assert (pdir / "src" / "assets" / "motion-kit.js").read_text(encoding="utf-8") == KIT.read_text(encoding="utf-8")
        assert r["file"] == "motion-kit.js" and "VS.spring" in r["usage"] and "VS.captions" in KIT.read_text(encoding="utf-8")


# ============================================================ formaty w planie

def format_project(dur: float):
    call("project_create", slug=f"p{int(dur)}", brand="t", size="1080x1920", duration=dur)
    return f"t/p{int(dur)}"


class TestFormatPlans:
    @pytest.mark.parametrize("fmt, items, roles", [
        ("tool-drop", 3, ["hook", "demo", "card", "benefit", "cta"]),
        ("talking-head", 3, ["hook", "point", "point", "point", "cta"]),
        ("listicle", 4, ["hook", "item", "item", "item", "item", "cta"]),
    ])
    def test_beats_follow_the_blueprint_and_tile_the_film(self, studio, fmt, items, roles):
        p = call("director_plan", project=format_project(16), goal="Darmowy skill do animacji", format=fmt, items=items)["plan"]
        beats = p["beats"]
        assert [b["role"] for b in beats] == roles and p["format"]["id"] == fmt and p["platform"] == "reels"
        assert beats[0]["t0"] == 0.0 and beats[-1]["t1"] == 16.0
        assert all(a["t1"] == b["t0"] for a, b in zip(beats, beats[1:])) and all(b["t1"] > b["t0"] for b in beats)
        for a, b in zip(beats, beats[1:]):                                  # sąsiednie bity nigdy nie wyglądają tak samo: inny styl albo inny układ
            assert (a["style"], a["layout"]) != (b["style"], b["layout"]), (a, b)
        assert beats[0]["transition_in"] is None and all(b["transition_in"] in styles.TRANSITIONS for b in beats[1:])
        assert set(p["contract"]["styles_used"]) <= {x["id"] for x in styles.STYLES}

    def test_tool_drop_keeps_hook_and_cta_lengths_and_scales_the_rest(self, studio):
        long = call("director_plan", project=format_project(30), goal="Darmowy skill", format="tool-drop")["plan"]["beats"]
        short = call("director_plan", project=format_project(16), goal="Darmowy skill", format="tool-drop")["plan"]["beats"]
        for beats in (long, short):
            assert beats[0]["t1"] - beats[0]["t0"] == pytest.approx(2.4, abs=0.02) and beats[-1]["t1"] - beats[-1]["t0"] >= 3.3 - 0.02
        assert long[2]["t1"] - long[2]["t0"] > short[2]["t1"] - short[2]["t0"]       # kart dostaje większy udział w dłuższym filmie

    def test_items_set_the_number_of_item_beats_and_get_numbered_copy(self, studio):
        p = call("director_plan", project=format_project(20), goal="Pięć nawyków", format="listicle", items=5)["plan"]
        items = [b for b in p["beats"] if b["role"] == "item"]
        assert len(items) == 5 and "Item 1" in items[0]["copy"] and "Item 5" in items[4]["copy"]

    def test_cta_line_goes_into_the_last_beat(self, studio):
        p = call("director_plan", project=format_project(16), goal="Darmowy skill", format="tool-drop", cta="Skomentuj ANIMACJA")["plan"]
        assert p["beats"][-1]["copy"].startswith("Skomentuj ANIMACJA. ")

    def test_long_and_too_short_beats_produce_warnings(self, studio):
        long = call("director_plan", project=format_project(30), goal="Darmowy skill", format="talking-head")["plan"]
        assert any("add a visible change" in w for w in long["warnings"])
        tight = call("director_plan", project=format_project(8), goal="Cztery rzeczy", format="listicle", items=4)["plan"]
        assert any("too short to read" in w for w in tight["warnings"])

    def test_a_film_too_short_for_the_format_is_refused_with_the_minimum(self, studio):
        with pytest.raises(CapabilityError, match="potrzebuje dłuższego filmu"):
            call("director_plan", project=format_project(5), goal="Darmowy skill", format="tool-drop")
        with pytest.raises(CapabilityError, match="minimum 12.6 s"):
            call("director_plan", project=format_project(8), goal="Siedem rzeczy", format="listicle", items=7)

    def test_unknown_format_and_bad_items_are_rejected(self, studio):
        pid = format_project(16)
        with pytest.raises(CapabilityError):
            call("director_plan", project=pid, goal="x", format="podcast")
        with pytest.raises(CapabilityError):
            call("director_plan", project=pid, goal="x", format="listicle", items=1)

    def test_a_plan_without_format_has_no_format_and_formats_are_documented(self, studio):
        p = call("director_plan", project=format_project(16), goal="Premiera aplikacji")["plan"]
        assert p["format"] is None and isinstance(p["warnings"], list)
        text = styles.formats_text()
        assert all(f in text for f in styles.FORMATS)


# ============================================================ szablony i znacznik zestawu ruchu

class TestTemplates:
    def test_kit_marker_is_expanded_in_place_and_plain_html_is_untouched(self):
        html = "<html><body><!--@motion-kit--><p>x</p></body></html>"
        out = workspace.expand_template(html)
        assert workspace.KIT_MARK not in out and "VS.captions" in out and out.count("<script>") == 1 and out.endswith("<p>x</p></body></html>")
        plain = "<html><body>bez znacznika</body></html>"
        assert workspace.expand_template(plain) == plain

    @pytest.mark.parametrize("tid", ["resource-drop", "word-captions"])
    def test_reel_templates_are_in_the_catalog_and_expand_the_kit(self, tid):
        cat = {t["id"]: t for t in json.loads((REPO / "templates" / "catalog.json").read_text(encoding="utf-8"))["templates"]}
        t = cat[tid]
        assert t["size"] == [1080, 1920] and 0 < t["poster_t"] < t["duration"]
        html = workspace.template_html(tid)
        assert workspace.KIT_MARK not in html and "VS.spring" in html and "window.seek" in html and "window.TEXTS" in html
        assert (REPO / t["file"]).read_text(encoding="utf-8").count(workspace.KIT_MARK) == 1
        assert tid in [x["id"] for x in workspace.templates()]

    def test_same_text_matches_partial_typing_but_not_single_characters(self):
        assert director._same_text("hello", "hello") and director._same_text("hel", "hello") and director._same_text("hello world", "hello")
        assert director._same_text("3", "3") and not director._same_text("3", "13") and not director._same_text("", "x")


# ============================================================ zdarzenia: narastające zbocze

class TestRisingEdgeEvents:
    TIMES = [round(i * 0.25, 2) for i in range(40)]

    def test_a_jump_inside_continuous_change_is_a_new_event_but_steady_change_is_not(self):
        steady = [0.2] * 40                                              # równy ruch przez cały film: nic nowego się nie zaczyna
        assert dscan.find_events(self.TIMES, steady) == [0.0]
        s = list(steady)
        for i in range(20, 40):
            s[i] = 0.5                                                   # nowy bit z gwałtownym skokiem w środku ruchu
        assert dscan.find_events(self.TIMES, s) == [0.0, 5.0]

    def test_events_closer_than_min_sep_merge_and_below_threshold_is_ignored(self):
        s = [0.0] * 40
        s[8] = s[9] = 0.4
        s[20] = 0.05
        assert dscan.find_events(self.TIMES, s, min_sep=0.7) == [0.0, 2.0]


# ============================================================ przeglądarka: zestaw ruchu i napisy

@pytest.mark.browser
class TestMotionKitInBrowser:
    @pytest.fixture
    def kit_page(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            br = pw.chromium.launch()
            pg = br.new_page(viewport={"width": 540, "height": 960})
            pg.set_content("<html><body style='margin:0;background:#000'><div id='cap' style='top:40%'></div></body></html>")
            pg.add_script_tag(content=KIT.read_text(encoding="utf-8"))
            yield pg
            br.close()

    def test_spring_and_bezier_curves_start_at_zero_end_at_one_and_behave_physically(self, kit_page):
        r = kit_page.evaluate("""() => {
            const s = VS.spring(170, 12), crit = VS.spring(170, 2 * Math.sqrt(170)), b = VS.ease.out, lin = VS.bezier(0, 0, 1, 1);
            let peak = 0, critPeak = 0;
            for (let i = 0; i <= 200; i++) { peak = Math.max(peak, s(i / 200)); critPeak = Math.max(critPeak, crit(i / 200)); }
            return { s0: s(0), s1: s(1), peak, critPeak, dur: VS.springDuration(170, 12), durSlow: VS.springDuration(1, 0.1),
                     out0: b(0), out1: b(1), outHalf: b(0.5), lin: lin(0.3), clamp: [s(-1), s(2)],
                     count: VS.count(1, 0, 2, 0, 100, p => p), type: VS.type('abcdef', 0.25, 0, 8), blink: [VS.blink(0.1, 2), VS.blink(0.6, 2)] };
        }""")
        assert r["s0"] == 0 and r["s1"] == 1 and r["clamp"] == [0, 1]
        assert r["peak"] > 1.02                                           # sprężyna niedotłumiona lekko przestrzela
        assert r["critPeak"] <= 1.0 + 1e-6                                # tłumienie krytyczne nie przestrzela
        assert 0.1 < r["dur"] <= 4 and r["durSlow"] == 4                   # czas ustalenia jest ograniczony
        assert r["out0"] == 0 and r["out1"] == 1 and r["outHalf"] > 0.85   # mocny ease-out: większość drogi w pierwszej połowie
        assert r["lin"] == pytest.approx(0.3, abs=1e-3)
        assert r["count"] == 50 and r["type"] == "ab" and r["blink"] == [True, False]

    def test_word_by_word_captions_pop_in_with_the_voice_and_report_their_text(self, kit_page):
        data = captions.build(words=[{"t0": 1.0, "t1": 1.4, "w": "Cześć"}, {"t0": 1.4, "t1": 2.0, "w": "świecie"}, {"t0": 3.0, "t1": 3.5, "w": "Koniec"}], style="pop", max_words=2)
        kit_page.evaluate("(d) => VS.captions.mount(document.getElementById('cap'), d, { style: 'pop' })", data)
        state = kit_page.evaluate("""() => {
            const out = {};
            for (const t of [0.5, 1.05, 1.5, 2.6, 3.2, 4.5]) {
                VS.captions.draw(t);
                const spans = [].slice.call(document.querySelectorAll('#cap .vs-w'));
                out[t] = { shown: spans.filter(s => s.style.opacity === '1').map(s => s.textContent), n: spans.length, texts: VS.captions.texts(t) };
            }
            return out;
        }""")
        assert state["0.5"]["n"] == 0 and state["0.5"]["texts"] == []                     # przed pierwszym słowem nic nie ma
        assert state["1.05"]["shown"] == ["Cześć"] and state["1.5"]["shown"] == ["Cześć", "świecie"]
        assert state["2.6"]["n"] == 0                                                      # linia znika po krótkim wyhamowaniu
        assert state["3.2"]["shown"] == ["Koniec"] and state["4.5"]["n"] == 0
        entry = state["1.5"]["texts"][0]
        assert entry["id"] == "cap" and entry["caption"] is True and entry["text"] == "Cześć świecie"
        assert 0 <= entry["x0"] < entry["x1"] <= 540 and 0 <= entry["y0"] < entry["y1"] <= 960

    def test_captions_are_a_pure_function_of_time(self, kit_page):
        data = captions.build(text="Jeden dwa trzy cztery pięć", start=0, end=3, style="karaoke", max_words=3)
        kit_page.evaluate("(d) => VS.captions.mount(document.getElementById('cap'), d, { style: 'karaoke' })", data)
        run = """() => [0.2, 0.9, 1.4, 2.2, 0.9].map(t => { VS.captions.draw(t); return document.getElementById('cap').innerHTML; })"""
        first = kit_page.evaluate(run)
        assert first[1] == first[4] and kit_page.evaluate(run) == first                  # ten sam czas daje ten sam obraz, także po powrocie


@pytest.mark.browser
class TestCaptionReadingRule:
    PAGE = ("<!doctype html><html><body style='margin:0;background:#000'><div id='a' style='position:absolute;left:40px;top:300px;font:700 48px sans-serif;color:#fff'>Szybko</div>"
            "<script>window.DURATION=2;window.__ready=Promise.resolve();window.seek=function(t){};"
            "window.TEXTS=function(t){var r=document.getElementById('a').getBoundingClientRect();"
            "return (t>=0.5&&t<0.8)?[{id:'x',text:'Szybko',x0:r.left,y0:r.top,x1:r.right,y1:r.bottom%s}]:[];};</script></body></html>")

    def test_a_caption_may_be_shorter_than_reading_time_but_ordinary_text_may_not(self, tmp_path):
        from vstudio import pages

        plain = tmp_path / "plain.html"
        plain.write_text(self.PAGE % "", encoding="utf-8")
        cap = tmp_path / "cap.html"
        cap.write_text(self.PAGE % ",caption:true", encoding="utf-8")
        bad = pages.readcheck(plain, size=(540, 960))
        good = pages.readcheck(cap, size=(540, 960))
        assert not bad["ok"] and any("needs" in f and "to be read" in f for f in bad["failures"])
        assert good["ok"], good["failures"]


# ============================================================ przeglądarka: szablony rolek przechodzą nadzorcę i reżysera

@pytest.mark.browser
class TestReelTemplatesAreClean:
    @pytest.mark.parametrize("tid", ["resource-drop", "word-captions"])
    def test_the_template_passes_the_supervisor_and_the_director(self, vendored_studio, monkeypatch, tid):
        # Strona 1080x1920 jest ciężka: przy domyślnym budżecie czasu "quick" wolniejszy runner rzadziej próbkuje albo pomija ruch. Test ma dawać ten sam
        # wynik na każdej maszynie, więc dostaje budżet jak przy "deep" (gęstość próbkowania zostaje "quick").
        monkeypatch.setitem(director.DEPTHS["quick"], "budget", 120)
        monkeypatch.setitem(director.DEPTHS["quick"], "motion_budget", 60)
        monkeypatch.setitem(director.DEPTHS["quick"], "ink_budget", 30)
        call("project_create", slug="t1", brand="t", template=tid)
        pdir, pr = workspace.resolve("t/t1")
        sup = supervisor.check(pdir, pr, depth="quick", save=False)
        if sup["metrics"].get("thinned"):
            pytest.skip("runner zbyt wolny: nadzorca rzadziej próbkuje klatki, więc wynik nie jest porównywalny")
        assert sup["verdict"] == "pass" and not [f for f in sup["findings"] if f["severity"] in ("error", "warn")], sup["findings"]
        rep = director.review(pdir, pr, depth="quick", save=False)
        bad = [f for f in rep["findings"] if f["severity"] in ("error", "warn")]
        assert rep["verdict"] == "pass" and not bad, bad
        m = rep["metrics"]
        assert m["gaps"] == [] and m["looks"] >= dscan.required_looks(pr["duration"]) and m["hook"] >= 0.08
        assert not m.get("thinned") and not m.get("motion_skipped"), m
        assert m["motion"]["linear"] == 0 and m["motion"]["moves"] > 0 and m["assets_visible"] >= 1


# ============================================================ nakładka z przezroczystością (ProRes 4444)

OVERLAY_PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;background:#101820}#stage{position:absolute;inset:0;background:#202830}
#card{position:absolute;left:30px;top:40px;width:100px;height:80px;background:#3A6BFF}#card.alpha{background:#2ECC71}
</style></head><body><div id="stage"><div data-alpha="hide" style="position:absolute;inset:0;background:#c00"></div><div id="card"></div></div>
<script>window.DURATION=1;window.EV=[];window.TEXTS=function(){return [];};window.__ready=Promise.resolve();
if(window.__ALPHA__)document.getElementById('card').className='alpha';window.seek=function(t){};</script></body></html>"""


def _renderer(*args: str, cwd: Path | None = None):
    import subprocess
    import sys

    return subprocess.run([sys.executable, str(REPO / "vstudio" / "renderers" / "html_to_video.py"), *args], capture_output=True, text=True, timeout=240, cwd=cwd)


def _has_prores() -> bool:
    import shutil
    import subprocess

    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    out = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
    return "prores_ks" in out


class TestOverlayOps:
    def _project(self):
        call("project_create", slug="o", brand="t", size="1080x1920", duration=8)
        return workspace.resolve("t/o")

    def test_overlay_is_gated_like_a_final_render_and_never_mixes_with_final_or_audio(self, studio, monkeypatch):
        from vstudio import jobs, ops

        self._project()
        started = []
        monkeypatch.setattr(ops, "_need", lambda *t: None)
        monkeypatch.setattr(jobs, "start", lambda kind, pid, d, args, source="api": started.append(args) or {"id": "J-00000000", "kind": kind})
        with pytest.raises(CapabilityError, match="overlay nie łączy się"):
            call("render_start", project="t/o", overlay=True, final=True)
        with pytest.raises(CapabilityError, match="overlay nie łączy się"):
            call("render_start", project="t/o", overlay=True, audio="x.wav")
        with pytest.raises(CapabilityError, match="brak zatwierdzenia reżysera"):
            call("render_start", project="t/o", overlay=True)                      # nakładka trafia do użytkownika, więc też wymaga zatwierdzenia
        r = call("render_start", project="t/o", overlay=True, skip_review=True)
        assert "skip_review" in r["warnings"][0] and "--overlay" in started[-1] and "--final" not in started[-1]
        call("profile_set", require_director=False)
        call("render_start", project="t/o", overlay=True)
        assert started[-1][:3] == ["render", "-p", started[-1][2]] and "--overlay" in started[-1]

    def test_the_project_layer_refuses_overlay_with_final_or_audio_and_non_html_engines(self, studio):
        from vstudio import project
        from vstudio.common import StudioError

        pdir, pr = self._project()
        with pytest.raises(StudioError, match="nie łączy się"):
            project.render(pdir, pr, final=True, tag=None, subframes=None, audio=None, force=True, overlay=True)
        with pytest.raises(StudioError, match="nie łączy się"):
            project.render(pdir, pr, final=False, tag=None, subframes=None, audio="a.wav", force=False, overlay=True)
        with pytest.raises(StudioError, match="engine: html"):
            project.render_overlay(pdir, {**pr, "engine": "remotion"})

    def test_mov_overlays_are_listed_flagged_and_reported_as_job_results(self, studio):
        from vstudio import jobs

        pdir, _ = self._project()
        (pdir / "renders").mkdir(exist_ok=True)
        (pdir / "renders" / "o_draft_20260101-000000.mp4").write_bytes(b"x" * 10)
        (pdir / "renders" / "o_overlay_20260101-000100.mov").write_bytes(b"y" * 20)
        rows = {r["file"]: r for r in call("project_get", project="t/o")["project"]["renders"]}
        assert rows["renders/o_overlay_20260101-000100.mov"]["overlay"] is True and rows["renders/o_draft_20260101-000000.mp4"]["overlay"] is False
        res = jobs._result({"kind": "render", "before": ["o_draft_20260101-000000.mp4"]}, pdir, "ok")
        assert res["file"] == "renders/o_overlay_20260101-000100.mov"
        removed = jobs.cleanup_partial({"kind": "render", "before": ["o_draft_20260101-000000.mp4"]}, pdir)
        assert removed == ["o_overlay_20260101-000100.mov"] and (pdir / "renders" / "o_draft_20260101-000000.mp4").exists()


@pytest.mark.browser
class TestOverlayRenderer:
    def test_alpha_options_are_validated_before_any_browser_work(self, tmp_path):
        page = tmp_path / "p.html"
        page.write_text(OVERLAY_PAGE, encoding="utf-8")
        audio = _renderer(str(page), "--alpha", "--audio", "x.wav", "-o", str(tmp_path / "o.mov"))
        assert audio.returncode != 0 and "--alpha does not take --audio" in audio.stderr
        name = _renderer(str(page), "--alpha", "-o", str(tmp_path / "o.mp4"))
        assert name.returncode != 0 and ".mov" in name.stderr

    def test_a_transparent_still_has_no_backdrop_and_an_opaque_card_and_the_page_knows_it_is_an_overlay(self, tmp_path):
        from PIL import Image

        page = tmp_path / "p.html"
        page.write_text(OVERLAY_PAGE, encoding="utf-8")
        out = tmp_path / "s.png"
        r = _renderer(str(page), "--alpha", "--still", "0.2", "--size", "200x300", "-o", str(out))
        assert r.returncode == 0, r.stderr
        im = Image.open(out).convert("RGBA")
        assert im.getpixel((5, 5))[3] == 0 and im.getpixel((190, 290))[3] == 0              # tło i #stage zniknęły
        r_, g_, b_, a_ = im.getpixel((60, 80))
        assert a_ == 255 and g_ > r_ and g_ > b_                                            # karta jest kryjąca i zielona: strona zobaczyła window.__ALPHA__
        normal = tmp_path / "n.png"
        assert _renderer(str(page), "--still", "0.2", "--size", "200x300", "-o", str(normal)).returncode == 0
        n = Image.open(normal).convert("RGBA")
        assert n.getpixel((5, 5))[3] == 255 and n.getpixel((60, 80))[2] > n.getpixel((60, 80))[1]    # bez --alpha: tło jest, karta niebieska

    @pytest.mark.skipif(not _has_prores(), reason="ffmpeg z kodekiem prores_ks nie jest dostępny")
    def test_the_encoded_mov_is_prores_4444_with_a_real_alpha_plane(self, tmp_path):
        import shutil
        import subprocess

        from PIL import Image

        page = tmp_path / "p.html"
        page.write_text(OVERLAY_PAGE, encoding="utf-8")
        out = tmp_path / "o.mov"
        r = _renderer(str(page), "--alpha", "--size", "200x300", "--fps", "10", "--duration", "0.5", "--subframes", "3", "-o", str(out))
        assert r.returncode == 0, r.stderr
        probe = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-i", str(out)], capture_output=True, text=True).stderr
        assert "prores (4444" in probe and "yuva444p" in probe and "200x300" in probe, probe
        png = tmp_path / "f.png"
        subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(out), "-frames:v", "1", "-vf", "format=rgba", str(png)], check=True, timeout=60)
        im = Image.open(png).convert("RGBA")
        assert im.getpixel((5, 5))[3] <= 2 and im.getpixel((60, 80))[3] >= 253


# ============================================================ CLI: te same operacje z terminala

def cli(*argv: str) -> int:
    """vstudio.py w tym samym procesie (żeby działały podmienione katalogi studia z fixture'a `studio`)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("vstudio_cli", REPO / "vstudio.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(list(argv))


class TestCli:
    def test_director_plan_takes_a_format_and_prints_it_with_warnings(self, studio, capsys):
        call("project_create", slug="c", brand="t", size="1080x1920", duration=30)
        assert cli("director", "plan", "-p", "t/c", "--goal", "Darmowy skill", "--format", "talking-head") == 0
        out = capsys.readouterr().out
        assert "format: Mówiąca głowa" in out and "point" in out and "uwaga:" in out          # 30 s: długie bity dostają uwagę
        assert cli("--json", "director", "plan", "-p", "t/c", "--goal", "Pięć rzeczy", "--format", "listicle", "--items", "5") == 0
        assert json.loads(capsys.readouterr().out)["format"]["id"] == "listicle"

    def test_captions_from_text_srt_and_word_files_and_the_kit(self, studio, tmp_path, capsys):
        call("project_create", slug="c", brand="t", size="1080x1920", duration=8)
        pdir, _ = workspace.resolve("t/c")
        assert cli("assets", "captions", "-p", "t/c", "--text", "Skomentuj ANIMACJA a wyślę Ci link", "--style", "pop", "--end", "4", "--highlight", "animacja") == 0
        assert "assets/captions.js" in capsys.readouterr().out and (pdir / "src" / "assets" / "captions.js").exists()
        srt = tmp_path / "a.srt"
        srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nCześć wszystkim\n", encoding="utf-8")
        assert cli("--json", "assets", "captions", "-p", "t/c", "--srt", str(srt)) == 0
        assert json.loads(capsys.readouterr().out)["words"] == 2
        wf = tmp_path / "w.json"
        wf.write_text(json.dumps([{"t0": 0, "t1": 0.5, "w": "Hej"}, {"t0": 0.5, "t1": 1.0, "w": "tu"}]), encoding="utf-8")
        assert cli("--json", "assets", "captions", "-p", "t/c", "--words", str(wf), "--style", "karaoke") == 0
        assert json.loads(capsys.readouterr().out)["style"] == "karaoke"
        assert cli("assets", "kit", "-p", "t/c") == 0 and "VS.spring" in capsys.readouterr().out
        assert (pdir / "src" / "assets" / "motion-kit.js").exists()

    def test_render_overlay_is_a_flag_and_bad_caption_sources_are_refused(self, studio):
        import importlib.util

        spec = importlib.util.spec_from_file_location("vstudio_cli", REPO / "vstudio.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.build_parser().parse_args(["render", "--overlay"]).overlay is True
        with pytest.raises(SystemExit):                                       # dokładnie jedno źródło napisów
            mod.build_parser().parse_args(["assets", "captions", "--text", "a", "--srt", "x.srt"])
