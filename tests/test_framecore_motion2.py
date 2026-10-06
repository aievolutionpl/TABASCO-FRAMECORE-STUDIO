"""Ruch 2.0: tekst kinetyczny, wyjścia, wygląd elementów i efekty filmowe."""
import shutil

import pytest
from playwright.sync_api import sync_playwright

from framecore.api import API
from framecore.composition import compile_project
from framecore.model import EditorError
from framecore.render import RenderJobs
from framecore.store import Store
from framecore.templates import catalog


@pytest.fixture
def motion_project(tmp_path):
    store = Store(tmp_path / "projects")
    api = API(store, RenderJobs(store))
    pid = api.call("create_project", {"name": "Ruch 2.0", "format": "16:9", "duration": 6})["project"]["id"]
    return store, api, pid


def call(api, store, pid, tool, **args):
    return api.call(tool, {"project_id": pid, "expected_revision": store.read(pid)["project"]["revision"], **args})


def test_kinetic_exit_and_look_contract(motion_project):
    store, api, pid = motion_project
    s = call(api, store, pid, "add_text", text="Ruch słów", start=0, duration=4)
    eid = s["project"]["elements"][-1]["id"]
    s = call(api, store, pid, "apply_motion", element_id=eid, motion_id="char-rise")
    # Component defaults are used when the caller gives no duration or curve.
    assert s["project"]["elements"][-1]["motion"] == {"id": "char-rise", "duration": 1.3, "easing": "back-out"}
    s = call(api, store, pid, "apply_exit", element_id=eid, exit_id="blur-out", duration=.5)
    assert s["project"]["elements"][-1]["exit"] == {"id": "blur-out", "duration": .5, "easing": "cubic-out"}
    s = call(api, store, pid, "set_property", element_id=eid, property="style.gradient", value={"from": "#ffaa00", "to": "#ff0066", "angle": 45})
    s = call(api, store, pid, "set_property", element_id=eid, property="style.shadow", value="neon")
    assert s["project"]["elements"][-1]["style"]["gradient"]["angle"] == 45
    for prop, value in [("style.shadow", "chmura"), ("style.gradient", {"from": "red", "to": "#000000", "angle": 0}),
                        ("style.blend", "plus"), ("style.letterSpacing", 900)]:
        with pytest.raises(EditorError):
            call(api, store, pid, "set_property", element_id=eid, property=prop, value=value)
    shape = call(api, store, pid, "add_shape", start=0, duration=2)["project"]["elements"][-1]["id"]
    with pytest.raises(EditorError, match="tekstem"):
        call(api, store, pid, "apply_motion", element_id=shape, motion_id="type-on")
    with pytest.raises(EditorError, match="wyjścia"):
        call(api, store, pid, "apply_exit", element_id=shape, exit_id="teleport")
    # Splitting keeps the exit only on the part that ends the clip.
    call(api, store, pid, "set_playhead", time=2)
    s = call(api, store, pid, "split_clip", element_id=eid, time=2)
    parts = [e for e in s["project"]["elements"] if e["type"] == "text"]
    assert "exit" not in parts[0] and parts[1]["exit"]["id"] == "blur-out"
    s = call(api, store, pid, "apply_exit", element_id=parts[1]["id"], exit_id="none")
    assert "exit" not in s["project"]["elements"][-1]
    s = call(api, store, pid, "undo")
    assert next(e for e in s["project"]["elements"] if e["id"] == parts[1]["id"])["exit"]["id"] == "blur-out"


def test_canvas_fx_and_templates_direction(motion_project):
    store, api, pid = motion_project
    s = call(api, store, pid, "set_canvas_fx", fx={"grade": "noir", "vignette": .6, "transition": "light-leak"})
    assert s["project"]["canvas"]["fx"]["grade"] == "noir" and s["project"]["canvas"]["fx"]["motionBlur"] is False
    for fx in ({"grade": "sepia"}, {"letterbox": .5}, {"transition": "spin"}, {"motionBlur": "tak"}, {"lut": "x"}):
        with pytest.raises(EditorError):
            call(api, store, pid, "set_canvas_fx", fx=fx)
    pid = api.call("create_project", {"name": "Szablon", "format": "9:16", "duration": 18})["project"]["id"]
    looks = {t["id"]: t["look"] for t in catalog()}
    assert all(look["kinetic"] and look["exit"] and look["fx"] for look in looks.values())
    s = call(api, store, pid, "apply_template", template_id="neon", replace=True)
    p = s["project"]
    titles = [e for e in p["elements"] if e["type"] == "text"]
    assert p["canvas"]["fx"]["transition"] == "blur"
    assert all(e["exit"]["id"] == "zoom-through" for e in titles)
    assert [e["motion"]["id"] for e in titles].count("scramble-in") == 1
    report = api.call("inspect_project", {"project_id": pid})
    assert not [i for i in report["issues"] if i["code"] in {"unfinished_motion", "motion_overlap"}]
    assert {"apply_exit", "set_canvas_fx"} <= {t["name"] for t in api.tools()}
    assert "set_canvas_fx" in api.call("get_editing_guide")["instructions"]


@pytest.mark.browser
def test_runtime_is_deterministic_and_hides_kinetic_text_after_clip(motion_project, tmp_path):
    store, api, pid = motion_project
    call(api, store, pid, "add_scene", name="A", start=0, duration=3, message="a")
    call(api, store, pid, "add_scene", name="B", start=3, duration=3, message="b")
    typer = call(api, store, pid, "add_text", text="Maszyna pisze", start=0, duration=3, motion={"id": "type-on", "duration": 1.3, "easing": "linear"})["project"]["elements"][-1]["id"]
    decoder = call(api, store, pid, "add_text", text="Dekoduj", start=3, duration=3, motion={"id": "scramble-in", "duration": 1.2},
         exit={"id": "zoom-through", "duration": .6}, style={"gradient": {"from": "#ffffff", "to": "#ff6a3d", "angle": 90}, "shadow": "glow"})["project"]["elements"][-1]["id"]
    call(api, store, pid, "add_shape", start=0, duration=6, motion={"id": "glitch-in", "duration": .7})
    call(api, store, pid, "set_canvas_fx", fx={"grade": "cinematic", "vignette": .5, "grain": .4, "letterbox": .1, "transition": "dip"})
    html = tmp_path / "index.html"
    html.write_text(compile_project(store.read(pid)["project"]), encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**({"executable_path": shutil.which("chromium")} if shutil.which("chromium") else {}))
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(html.as_uri())
        page.wait_for_function("window.READY===true")
        typed = f"()=>[...document.querySelectorAll('[data-element-id=\\'{typer}\\'] .fc-char')].filter(c=>c.style.opacity==='1').length"
        page.evaluate("window.seek(0.65)")
        assert 4 <= page.evaluate(typed) <= 8
        page.evaluate("window.seek(1.4)")
        assert page.evaluate(typed) == 12  # every non-space character of "Maszyna pisze"
        # The dip transition peaks on the cut between scenes.
        page.evaluate("window.seek(3.0)")
        assert float(page.evaluate("document.querySelector('.fc-fx > div').style.opacity")) > .95
        page.evaluate("window.seek(3.5)")
        assert page.evaluate(f"[...document.querySelectorAll('[data-element-id=\\'{typer}\\'] .fc-char')].every(c=>!c.checkVisibility({{visibilityProperty:true}}))")
        snapshot = "()=>[...document.querySelectorAll('[data-composition-id] *')].map(n=>n.getAttribute('style')+n.textContent.length).join('|')"
        page.evaluate("window.seek(3.4)");first = page.evaluate(snapshot)
        page.evaluate("window.seek(5.9)");page.evaluate("window.seek(1.1)");page.evaluate("window.seek(3.4)")
        assert page.evaluate(snapshot) == first
        opacity = lambda t: float(page.evaluate(f"(window.seek({t}),document.querySelector('[data-element-id=\\'{decoder}\\']').style.opacity)"))
        assert opacity(5.2) == 1 and opacity(5.7) < 1 and opacity(5.97) < .25
        assert errors == []
        browser.close()


@pytest.mark.browser
def test_motion_panel_exit_look_and_film_preset(tmp_path):
    from framecore.server import start_background
    store = Store(tmp_path / "projects")
    p = store.create("Panel ruchu", "16:9", 6)["project"];pid = p["id"]
    p = store.execute(pid, "add_scene", {"name": "A", "start": 0, "duration": 3, "message": "a"}, 0)["project"]
    p = store.execute(pid, "add_text", {"text": "Ruch słów", "duration": 4}, p["revision"])["project"]
    store.execute(pid, "set_selection", {"element_ids": [p["elements"][0]["id"]]})
    srv, _ = start_background(store);base = f"http://127.0.0.1:{srv.server_port}";errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**({"executable_path": shutil.which("chromium")} if shutil.which("chromium") else {}))
            page = browser.new_page(viewport={"width": 1512, "height": 982})
            page.add_init_script("localStorage.setItem('framecore-onboarding-v2', 'done')")
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base);page.wait_for_function('document.querySelector("#player").ready')
            page.click('[data-tab="Motion"]')
            page.click('[data-motion-filter="kinetic"]')
            assert page.locator("[data-motion]").count() == 7 and page.locator("[data-exit]").count() == 0
            page.click('[data-motion="word-cascade"]')
            page.wait_for_function("document.querySelector('[data-anim=\"motion-id\"]')?.value==='word-cascade'")
            page.click('[data-motion-filter="exit"]');page.click('[data-exit="rise-out"]')
            page.wait_for_function("document.querySelector('[data-anim=\"exit-id\"]')?.value==='rise-out'")
            page.select_option('[data-property="style.shadow"]', "glow")
            page.wait_for_function("document.querySelector('[data-property=\"style.shadowColor\"]')")
            e = store.read(pid)["project"]["elements"][0]
            assert e["motion"]["id"] == "word-cascade" and e["exit"]["id"] == "rise-out" and e["style"]["shadow"] == "glow"
            page.select_option('[data-anim="exit-id"]', "none")
            page.wait_for_function("!document.querySelector('[data-anim=\"exit-duration\"]')")
            store.execute(pid, "set_selection", {"element_ids": []})
            page.locator("[data-fx-preset=cinema]").wait_for()
            page.click("[data-fx-preset=cinema]")
            page.wait_for_function("document.querySelector('[data-fx=\"grade\"]')?.value==='cinematic'")
            assert store.read(pid)["project"]["canvas"]["fx"]["letterbox"] == .12
            page.emulate_media(reduced_motion="reduce");page.click('[data-motion-filter="kinetic"]')
            assert page.locator('[data-motion="char-rise"] .motion-demo i').first.evaluate("el=>getComputedStyle(el).animationName") == "none"
            assert errors == []
            browser.close()
    finally:
        srv.shutdown();srv.server_close()


@pytest.mark.parametrize("name", ["showreel", "reel"])
def test_showcase_projects_are_editable_and_clean(tmp_path, name):
    from framecore.showcase import SHOWCASES
    store = Store(tmp_path / "projects")
    p = SHOWCASES[name][0](store)["project"]
    api = API(store, RenderJobs(store))
    assert api.call("inspect_project", {"project_id": p["id"]})["issues"] == []
    kinds = {m["id"]: m["kind"] for m in api.call("list_motion")["components"]}
    used = {e["motion"]["id"] for e in p["elements"] if e.get("motion")}
    assert sum(kinds.get(m) == "kinetic" for m in used) >= 4
    assert any(e.get("exit") for e in p["elements"]) and p["canvas"]["fx"]["motionBlur"] is True
    assert sum(e["type"] == "audio" for e in p["elements"]) == 1
    assert store.read(p["id"])["history"], "built through the shared command history"
