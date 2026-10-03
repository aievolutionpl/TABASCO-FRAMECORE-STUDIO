"""Testy warstwy studia: rejestr możliwości, operacje, nadzorca, serwer MCP, dashboard (API, bezpieczeństwo, UI).

Część bez przeglądarki jest szybka. Testy z markerem `browser` potrzebują Chromium (Playwright) i GSAP 3.12.5 (GSAP_JS).
"""
from __future__ import annotations

import http.client
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from vstudio import activity, agentkit, common, docgen, jobs, knowledge, registry, skillgen, supervisor, vendor, workspace
from vstudio import ops  # noqa: F401  (wypełnia rejestr)
from vstudio.mcp_server import McpServer
from vstudio.registry import CapabilityError

REPO = Path(__file__).resolve().parents[1]


def call(op: str, /, **args):
    return registry.call(op, args, source="api")


# ============================================================ rejestr i mapa

class TestRegistry:
    def test_every_capability_is_described(self):
        assert len(registry.REGISTRY) >= 35
        cats = dict(registry.CATEGORIES)
        for c in registry.REGISTRY.values():
            assert c.category in cats and c.title and c.summary and callable(c.handler)
            assert set(c.required) <= set(c.params), c.name
            for k, spec in c.params.items():
                assert spec.get("type") in (None, "string", "integer", "number", "boolean", "array", "object"), (c.name, k)

    def test_validation(self):
        with pytest.raises(CapabilityError, match="brakuje"):
            call("scene_read")
        with pytest.raises(CapabilityError, match="nieznane parametry"):
            call("scene_read", project="a/b", nope=1)
        with pytest.raises(CapabilityError, match="typu integer"):
            call("scene_read", project="a/b", start_line="x")
        with pytest.raises(CapabilityError, match="jednym z"):
            call("check_run", project="a/b", depth="ultra")
        with pytest.raises(CapabilityError, match="nieznana operacja"):
            call("nie_ma_takiej")
        assert registry.validate(registry.REGISTRY["check_run"], {"project": "a/b"})["depth"] == "standard"     # wartość domyślna

    def test_errors_become_capability_errors_not_exits(self, studio):
        with pytest.raises(CapabilityError, match="brak projektu"):
            call("project_get", project="brand/nie-ma")
        with pytest.raises(CapabilityError, match="niepoprawny identyfikator"):
            call("project_get", project="../../etc")

    def test_docs_and_skill_are_in_sync_with_the_registry(self):
        assert (REPO / "docs" / "CAPABILITIES.md").read_text(encoding="utf-8") == docgen.render(), "odśwież: python vstudio.py tools --write-docs"
        assert (REPO / "skills" / "vstudio" / "SKILL.md").read_text(encoding="utf-8") == skillgen.render(), "odśwież: python vstudio.py skill --write"

    def test_readme_numbers_match_the_registry(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        n, cats = len(registry.REGISTRY), len({c.category for c in registry.REGISTRY.values()})
        assert f"({n} operacji)" in readme and f"**{n} narzędzi** w {cats} kategoriach" in readme, "zaktualizuj liczby w README (sekcja Studio)"

    def test_every_capability_is_in_the_docs_and_the_skill(self):
        doc, skill = docgen.render(), skillgen.render()
        for name in registry.REGISTRY:
            assert f"`{name}`" in doc and f"`{name}`" in skill

    def test_every_finding_code_has_a_remedy(self):
        for code, (title, fix) in supervisor.REMEDIES.items():
            assert title and len(fix) > 20
            assert supervisor.explain(code)["fix"] == fix
        with pytest.raises(common.StudioError):
            supervisor.explain("NOPE")

    def test_knowledge_topics(self):
        for topic in knowledge.TOPICS:
            assert knowledge.get(topic)["text"]
        assert "force3D" in knowledge.get("gsap")["text"]


# ============================================================ katalog szablonów

class TestCatalog:
    def test_catalog_matches_files(self):
        data = json.loads((REPO / "templates" / "catalog.json").read_text(encoding="utf-8"))
        ids = [t["id"] for t in data["templates"]]
        assert len(ids) == len(set(ids)) >= 8
        for t in data["templates"]:
            f = REPO / t["file"]
            assert f.is_file(), t["id"]
            html = f.read_text(encoding="utf-8")
            assert "window.seek" in html or "window.draw" in html, t["id"]
            assert 0 <= t["poster_t"] <= t["duration"], t["id"]
            if "motion-graphics" in t["file"]:
                assert re.search(r"var DUR = (\d+)", html).group(1) == str(int(t["duration"])), t["id"]
                assert t["size"] == [1080, 1350]


# ============================================================ operacje na izolowanym studiu

class TestWorkspace:
    def test_profile_roundtrip_and_validation(self, studio):
        assert call("profile_get")["onboarded"] is False
        p = call("profile_set", name="Kawiarnia Ziarno", palette={"accent": "#ff6b4a"}, default_format="9:16")
        assert p["onboarded"] and p["palette"]["accent"] == "#ff6b4a" and p["palette"]["bg"] == "#0B0E24"
        with pytest.raises(CapabilityError, match="#RRGGBB"):
            call("profile_set", palette={"accent": "red"})
        with pytest.raises(CapabilityError, match="default_format"):
            registry.call("profile_set", {"default_format": "2:1"})
        assert "Kawiarnia Ziarno" in call("knowledge_get", topic="brand")["text"]

    def test_create_project_from_template_and_summaries(self, studio):
        r = call("project_create", slug="pierwszy", brand="Demo", template="hide-the-cut", brief="Demo aplikacji")["project"]
        assert r["id"] == "demo/pierwszy" and r["size"] == [1080, 1350] and r["duration"] == 7.0
        src = (studio / "demo" / "pierwszy" / "src" / "index.html").read_text(encoding="utf-8")
        assert "<title>pierwszy</title>" in src and "Demo aplikacji" in (studio / "demo" / "pierwszy" / "BRIEF.md").read_text(encoding="utf-8")
        assert [p["id"] for p in call("projects_list")["projects"]] == ["demo/pierwszy"]
        assert call("project_get", project="pierwszy")["project"]["id"] == "demo/pierwszy"         # sam slug też działa
        assert activity.tail(20)[-1]["project"] == "demo/pierwszy"                     # log aktywności: id, nie cały obiekt
        with pytest.raises(CapabilityError, match="already exists"):
            call("project_create", slug="pierwszy", brand="Demo")
        with pytest.raises(CapabilityError, match="nieznany szablon"):
            call("project_create", slug="x", brand="Demo", template="nie-ma")

    def test_format_defaults_come_from_the_profile(self, studio):
        call("profile_set", name="Marka", default_format="9:16")
        assert call("project_create", slug="pion")["project"]["size"] == [1080, 1920]
        assert call("project_create", slug="kwadrat", format="1:1")["project"]["size"] == [1080, 1080]

    def test_scene_write_patch_history_restore(self, studio):
        call("project_create", slug="s", brand="b", template="hide-the-cut")
        sc = call("scene_read", project="b/s", start_line=1, end_line=2)
        assert sc["range"] == [1, 2] and sc["hooks"]["window.seek"] and sc["vendor"]["needs_network"]
        original = call("scene_read", project="b/s")["content"]
        r = call("scene_patch", project="b/s", edits=[{"find": "Your order", "replace": "Twoje zamówienie", "all": True}], note="pl")
        assert r["backup"] and "Twoje zamówienie" in call("scene_read", project="b/s")["content"]
        with pytest.raises(CapabilityError, match="nie znaleziono"):
            call("scene_patch", project="b/s", edits=[{"find": "NIE MA TEGO", "replace": "x"}])
        with pytest.raises(CapabilityError, match="występuje"):
            call("scene_patch", project="b/s", edits=[{"find": "div", "replace": "span"}])       # wieloznaczne
        with pytest.raises(CapabilityError, match="pusta"):
            call("scene_write", project="b/s", content="   ")
        call("scene_write", project="b/s", content="<html><body>nowa scena</body></html>", note="rewrite")
        hist = call("scene_history", project="b/s")["versions"]
        assert len(hist) == 2 and {h["note"] for h in hist} == {"pl", "rewrite"}
        restored = call("scene_restore", project="b/s", version=next(h["version"] for h in hist if h["note"] == "rewrite"))
        assert restored["restored"] and "Twoje zamówienie" in call("scene_read", project="b/s")["content"]
        assert call("scene_read", project="b/s")["content"] != original
        with pytest.raises(CapabilityError, match="niepoprawna wersja"):
            call("scene_restore", project="b/s", version="../x.html")

    def test_scene_palette_and_recolor(self, studio):
        call("profile_set", name="M", palette={"bg": "#101820", "ink": "#FAFAFA", "accent": "#00B894", "accent2": "#6C5CE7"})
        call("project_create", slug="pal", brand="b", template="hide-the-cut")
        pal = call("scene_palette", project="b/pal")
        hexes = {c["hex"] for c in pal["colors"]}
        assert {"#0B0E24", "#F4F6FF", "#2F5BFF"} <= hexes and all(re.fullmatch(r"#[0-9A-F]{6}", h) for h in hexes)
        assert pal["colors"] == sorted(pal["colors"], key=lambda c: -c["count"]) and pal["brand"]["accent"] == "#00B894"
        sug = {x["role"]: x for x in pal["suggestion"]}
        assert sug["bg"]["from"] == "#0B0E24" and sug["bg"]["to"] == "#101820" and "accent" in sug
        # podmiana jednym przebiegiem: zamiana miejscami A<->B nie łańcuchuje się
        before = call("scene_read", project="b/pal")["content"]
        r = call("scene_recolor", project="b/pal", mapping={"#0b0e24": "#F4F6FF", "#F4F6FF": "#0B0E24"}, note="swap")
        after = call("scene_read", project="b/pal")["content"]
        assert r["replaced"]["#0B0E24"] >= 1 and r["replaced"]["#F4F6FF"] >= 1 and r["backup"]
        assert after.count("#0B0E24") == before.count("#F4F6FF") and after.count("#F4F6FF") == before.count("#0B0E24")
        assert call("scene_history", project="b/pal")["versions"][0]["note"] == "swap"
        with pytest.raises(CapabilityError, match="nie występuje"):
            call("scene_recolor", project="b/pal", mapping={"#123456": "#654321"})
        with pytest.raises(CapabilityError, match="#RRGGBB"):
            call("scene_recolor", project="b/pal", mapping={"#0B0E24": "czerwony"})
        with pytest.raises(CapabilityError, match="mapping"):
            call("scene_recolor", project="b/pal", mapping={})

    def test_recolor_ignores_html_entities_and_short_hex(self, studio):
        call("project_create", slug="ent", brand="b")
        call("scene_write", project="b/ent", content='<style>a{color:#abcdef;b:#fff}</style>&#169; &#xabcdef; <a href="#abcdef1">x</a>')
        assert [c["hex"] for c in call("scene_palette", project="b/ent")["colors"]] == ["#ABCDEF"]
        call("scene_recolor", project="b/ent", mapping={"#ABCDEF": "#111111"})
        out = call("scene_read", project="b/ent")["content"]
        assert "color:#111111" in out and "&#xabcdef;" in out and "#abcdef1" in out and "#fff" in out

    def test_restoring_the_oldest_of_30_versions_works(self, studio):
        call("project_create", slug="h", brand="b")
        for i in range(32):
            call("scene_write", project="b/h", content=f"<html>wersja {i}</html>", note=f"v{i}")
        versions = call("scene_history", project="b/h")["versions"]
        assert len(versions) == 30
        oldest = versions[-1]
        r = call("scene_restore", project="b/h", version=oldest["version"])                  # kopia przycinała historię i kasowała źródło
        assert r["restored"] == oldest["version"] and "wersja" in call("scene_read", project="b/h")["content"]

    def test_task_stores_the_canonical_project_id_and_shows_up_on_the_project(self, studio):
        call("project_create", slug="pierwszy", brand="Demo")
        t = call("task_create", prompt="Skróć film", project="pierwszy")["task"]                # sam slug
        assert t["project"] == "demo/pierwszy"
        assert [x["id"] for x in call("project_get", project="demo/pierwszy")["project"]["tasks"]] == [t["id"]]

    def test_renders_are_listed_newest_first_by_time_not_by_name(self, studio):
        call("project_create", slug="r", brand="b")
        rdir = studio / "b" / "r" / "renders"
        rdir.mkdir(exist_ok=True)
        import os
        old_final, new_draft = rdir / "r_final_20260101-000000.mp4", rdir / "r_draft_20260301-000000.mp4"
        old_final.write_bytes(b"1")
        new_draft.write_bytes(b"2")
        os.utime(old_final, (1_000, 1_000))
        os.utime(new_draft, (2_000, 2_000))
        assert [x["file"] for x in call("project_get", project="b/r")["project"]["renders"]][0].endswith("draft_20260301-000000.mp4")

    def test_recolor_keeps_alpha_and_ignores_fragments_and_url_refs(self, studio):
        call("project_create", slug="a", brand="b")
        call("scene_write", project="b/a", content='<style>.g{box-shadow:0 0 40px #FF6B4A80;color:#ff6b4a}</style><a href="#abcdef">x</a>'
                                                  '<svg><use fill="url(#decade)"/></svg>')
        pal = call("scene_palette", project="b/a")["colors"]
        assert [(c["hex"], c["count"]) for c in pal] == [("#FF6B4A", 2)]                       # alfa liczy się do koloru bazowego
        call("scene_recolor", project="b/a", mapping={"#FF6B4A": "#00B894"})
        out = call("scene_read", project="b/a")["content"]
        assert "#00B89480" in out and "color:#00b894" not in out.lower().replace("#00b894", "") and out.count("#00B894") == 2
        assert 'href="#abcdef"' in out and "url(#decade)" in out

    def test_gates_and_next_step(self, studio):
        call("project_create", slug="g", brand="b")
        r = call("gate_set", project="b/g", action="approve", gate="brief")
        assert "brief" in r["message"] and r["next"].startswith("visual_rules")
        assert call("project_get", project="b/g")["project"]["gates"]["brief"]
        with pytest.raises(CapabilityError):
            call("gate_set", project="b/g", action="approve")                                    # brak nazwy bramki

    def test_tasks_lifecycle(self, studio):
        call("project_create", slug="t", brand="b")
        t = call("task_create", prompt="Skróć do 5 s", project="b/t")["task"]
        assert t["status"] == "open" and call("task_next")["task"]["id"] == t["id"]
        call("task_update", task=t["id"], status="in_progress", note="zaczynam")
        done = call("task_update", task=t["id"], status="done", note="gotowe, zostało ostrzeżenie DEAD_TIME (celowe)")["task"]
        assert done["status"] == "done" and len(done["notes"]) == 2
        assert call("task_next")["task"] is None
        with pytest.raises(CapabilityError, match="brak zadania"):
            call("task_update", task="T-9999", status="done")
        with pytest.raises(CapabilityError, match="brak projektu"):
            call("task_create", prompt="x", project="b/nie-ma")

    def test_studio_status_guides_the_next_step(self, studio):
        st = call("studio_status")
        assert any("profil marki" in n for n in st["next"]) and any("pierwszy film" in n for n in st["next"])
        call("profile_set", name="M")
        call("project_create", slug="p", brand="M")
        st = call("studio_status")
        assert st["onboarded"] and st["projects"] == 1 and any("jeszcze nie sprawdzony" in n for n in st["next"])


# ============================================================ vendor, aktywność, joby, agent

class TestSupportModules:
    def test_vendor_roundtrip_and_rewrite(self, studio, tmp_path):
        lib = tmp_path / "lib.js"
        lib.write_text("window.X = 1;")
        res = vendor.add("gsap", file=str(lib))
        url = vendor.ALIASES["gsap"]
        assert res["url"] == url and vendor.listing()[0]["bytes"] == len("window.X = 1;")
        html, swapped = vendor.rewrite_html(f'<script src="{url}"></script>')
        assert swapped == [url] and "/vendor/" in html and "cdnjs" not in html
        assert vendor.read_file(res["file"]) == b"window.X = 1;" and vendor.read_file("../x") is None
        assert vendor.env()["VSTUDIO_VENDOR_INDEX"].endswith("index.json")
        st = vendor.status_for_html(f'<script src="{url}"></script><link href="https://x.test/a.css">')
        assert st["vendored"] == [url] and st["needs_network"] == ["https://x.test/a.css"]
        assert vendor.remove("gsap")["removed"] and not vendor.listing()
        with pytest.raises(common.StudioError):
            vendor.add("nie-adres")

    def test_activity_ids_survive_a_javascript_number(self, studio):
        for _ in range(5):
            activity.record("mcp", "call", "x")
        ids = [e["id"] for e in activity.tail(10)]
        assert ids == sorted(set(ids)) and all(i < 2 ** 53 for i in ids)
        assert all(int(float(i)) == i for i in ids)                                # round-trip przez double jak w JS
        assert activity.tail(10, since=ids[-1]) == []

    def test_vendor_refuses_arbitrary_local_files_and_wrong_types(self, studio, tmp_path):
        secret = tmp_path / "id_rsa"
        secret.write_text("PRIVATE KEY")
        with pytest.raises(common.StudioError, match="tylko skrypty, style i fonty"):
            vendor.add("https://x.test/a.js", file=str(secret))
        data = tmp_path / "creds.json"
        data.write_text("{}")
        with pytest.raises(common.StudioError, match="tylko skrypty, style i fonty"):
            vendor.add("https://x.test/a.js", file=str(data))
        css = tmp_path / "a.css"
        css.write_text("a{}")
        with pytest.raises(common.StudioError, match="nie pasuje"):
            vendor.add("https://x.test/lib.js", file=str(css))
        big = tmp_path / "big.js"
        big.write_bytes(b"x" * (vendor.MAX_BYTES + 1))
        with pytest.raises(common.StudioError, match="większy"):
            vendor.add("https://x.test/big.js", file=str(big))
        assert not vendor.listing()
        ok = tmp_path / "ok.js"
        ok.write_text("1")
        assert vendor.add("https://x.test/lib.js", file=str(ok))["file"].endswith(".js")

    def test_vendor_derives_the_extension_from_content_type(self, studio):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                body, ctype = (b"a{color:red}", "text/css") if self.path.startswith("/css2") else (b"x", "application/x-unknown")
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            res = vendor.add(f"{base}/css2?family=Inter:wght@800")                      # bez rozszerzenia w adresie
            assert res["file"].endswith(".css") and vendor.content_type(res["file"]) == "text/css"
            with pytest.raises(common.StudioError, match="nie rozpoznano typu"):
                vendor.add(f"{base}/dziwne")
        finally:
            srv.shutdown()

    def test_render_does_not_clobber_gates_approved_while_it_runs(self, studio, monkeypatch):
        """Render trwa minuty: zatwierdzenia z tego czasu muszą przetrwać zapis wyniku (job zapisywał kopię project.json z początku)."""
        from vstudio import project as proj

        call("project_create", slug="g", brand="b")
        pdir, stale = workspace.resolve("b/g")                                      # „kopia z początku joba”
        assert not stale["gates"]["brief"]

        def fake_run(cmd, **kw):
            if "-o" in cmd:                                                          # wywołanie renderera (drugie to video_qa)
                Path(cmd[cmd.index("-o") + 1]).write_bytes(b"mp4")                   # render „powstał”
                proj.cmd_gate(*workspace.resolve("b/g"), "approve", "brief", None)   # w trakcie renderu użytkownik zatwierdza bramkę
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(proj, "run", fake_run)
        proj.render(pdir, stale, final=False, tag=None, subframes=None, audio=None, force=False)
        _, after = workspace.resolve("b/g")
        assert after["gates"]["brief"] and after["gates"]["draft"] and len(after["renders"]) == 1

    def test_activity_log_and_agent_status(self, studio):
        assert activity.agent_status()["connected"] is False
        registry.call("studio_status", {}, source="mcp")
        assert activity.agent_status()["connected"] and activity.agent_status()["last_call"] == "studio_status"
        registry.call("profile_get", {}, source="dashboard")                     # odczyt z dashboardu nie zaśmieca feedu
        names = [e["name"] for e in activity.tail(20)]
        assert names == ["studio_status"]
        with pytest.raises(CapabilityError):
            registry.call("project_get", {"project": "x/y"}, source="dashboard")  # błędy są logowane zawsze
        assert activity.tail(5)[-1]["ok"] is False
        last = activity.tail(1)[0]["id"]
        assert activity.tail(5, since=last) == []

    def test_job_runs_a_subprocess_with_result(self, studio):
        pdir = studio
        j = jobs.start("deliver", "x/y", pdir, ["tools"])
        done = jobs.wait(j["id"], 60)
        assert done["status"] == "done" and done["progress"] == 1.0 and "studio_status" in jobs.log_tail(j["id"], 400)
        assert jobs.listing()[0]["id"] == j["id"]
        bad = jobs.wait(jobs.start("deliver", "x/y", pdir, ["nie-ma-takiej-komendy"])["id"], 60)
        assert bad["status"] == "failed"
        with pytest.raises(common.StudioError):
            jobs.get("../../etc")

    def test_cancelled_or_failed_render_leaves_no_partial_video(self, studio):
        pdir = studio / "m" / "p"
        (pdir / "renders").mkdir(parents=True)
        (pdir / "renders" / "stary.mp4").write_bytes(b"ok")
        job = {"kind": "render", "before": ["stary.mp4"]}                  # migawka renders/ z chwili startu joba
        for name in ("nowy_final.mp4", "nowy_final.qa.json", "notatka.txt"):
            (pdir / "renders" / name).write_bytes(b"x")
        removed = jobs.cleanup_partial(job, pdir)
        assert sorted(removed) == ["nowy_final.mp4", "nowy_final.qa.json"]      # tylko to, co POWSTAŁO w tym jobie
        assert (pdir / "renders" / "stary.mp4").exists() and (pdir / "renders" / "notatka.txt").exists()
        assert jobs.cleanup_partial({"kind": "deliver", "before": []}, pdir) == []     # inne rodzaje jobów nie są ruszane

    def test_jobs_are_visible_and_cancellable_across_processes(self, studio):
        """Agent startuje render w procesie MCP, dashboard (inny proces) widzi go i może anulować; martwy job dostaje `lost` raz, trwale."""
        pdir = studio / "m" / "p"
        cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
        group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
        child = subprocess.Popen(cmd, **group)
        try:
            job = {"id": "J-aaaaaaaa", "kind": "render", "project": "m/p", "cmd": "render", "status": "running", "progress": 0.4, "message": "x",
                   "started": time.time(), "finished": None, "result": None, "source": "mcp", "pid": child.pid, "before": []}
            jobs._save(job)
            seen = jobs.get("J-aaaaaaaa")
            assert seen["status"] == "running" and seen["progress"] == 0.4          # nie „lost”, mimo że nie ten proces go uruchomił
            with pytest.raises(common.StudioError, match="trwa już job"):
                jobs.start("sound", "m/p", pdir, ["tools"])                         # wyłączność: jeden job na projekt
            assert jobs.cancel("J-aaaaaaaa")["status"] == "cancelled"
            child.wait(timeout=10)                                                  # proces faktycznie zabity
            assert jobs.get("J-aaaaaaaa")["status"] == "cancelled"
        finally:
            child.kill()
        job.update(id="J-bbbbbbbb", status="running", pid=child.pid, finished=None)         # PID martwy
        jobs._save(job)
        first = jobs.get("J-bbbbbbbb")
        time.sleep(0.05)
        assert first["status"] == "lost" and jobs.get("J-bbbbbbbb")["finished"] == first["finished"]     # `finished` ustalone raz

    def test_cancel_from_another_process_is_not_overwritten_by_the_owner(self, studio):
        job = {"id": "J-cccccccc", "kind": "deliver", "project": "m/p", "cmd": "x", "status": "running", "progress": 0.0, "message": "m",
               "started": time.time(), "finished": None, "result": None, "source": "mcp", "pid": 1, "before": []}
        jobs._save({**job, "status": "cancelled", "message": "anulowano", "finished": time.time()})     # inny proces anulował
        mine = dict(job)
        jobs._save(mine)                                                                                 # właściciel dalej zapisuje postęp
        assert mine["status"] == "cancelled" and jobs._read("J-cccccccc")["status"] == "cancelled"

    @pytest.mark.skipif(sys.platform == "win32", reason="grupy procesów POSIX; na Windows kill_tree używa taskkill /T")
    def test_cancel_kills_the_whole_process_tree(self, tmp_path):
        """Render to drzewo procesów: zabicie samego rodzica zostawiłoby ffmpeg dokańczający plik w tle."""
        pidfile = tmp_path / "child.pid"
        proc = subprocess.Popen(["sh", "-c", f"sleep 60 & echo $! > {pidfile}; wait"], start_new_session=True)
        for _ in range(50):
            if pidfile.exists() and pidfile.read_text().strip():
                break
            time.sleep(0.1)
        child = int(pidfile.read_text())
        jobs.kill_tree(proc)
        proc.wait(timeout=10)
        import os

        def alive(pid: int) -> bool:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            try:                                                           # zombie (kontener bez reapera na PID 1) to już martwy proces
                return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
            except OSError:
                return True

        for _ in range(30):
            if not alive(child):
                break
            time.sleep(0.1)
        assert not alive(child), "wnuk przeżył zabicie rodzica"

    def test_ops_check_only_the_tools_they_need(self, studio, monkeypatch):
        import shutil
        call("project_create", slug="n", brand="b")
        monkeypatch.setattr(shutil, "which", lambda tool: None)
        for op in ("render_start", "sound_start", "deliver_start"):
            with pytest.raises(CapabilityError, match="nie jest na PATH"):
                call(op, project="b/n")
        monkeypatch.setattr(shutil, "which", lambda tool: "/bin/x" if tool == "ffmpeg" else None)
        with pytest.raises(CapabilityError, match="ffprobe"):
            call("deliver_start", project="b/n")                              # wydanie potrzebuje ffprobe
        monkeypatch.setattr(jobs, "start", lambda *a, **k: {"id": "J-00000000", "status": "running"})
        assert call("render_start", project="b/n")["job"]["id"] == "J-00000000"   # render nie wymaga ffprobe

    def test_agent_install_writes_skill_and_merges_mcp_json(self, studio, tmp_path):
        (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"inny": {"command": "x"}}}))
        r = call("agent_install", scope="project")["installed"]
        cfg = json.loads((tmp_path / ".mcp.json").read_text())
        assert set(cfg["mcpServers"]) == {"inny", "vstudio"} and cfg["mcpServers"]["vstudio"]["args"][-1] == "mcp"
        assert Path(r["skill"]).read_text(encoding="utf-8") == skillgen.render()
        info = call("agent_connect_info")
        assert info["mcp_configured"] and info["skill"]["installed_project"] and info["claude_code"].startswith("claude mcp add vstudio")
        u = call("agent_install", skill=True, mcp_config=False, scope="user")["installed"]
        assert str(tmp_path / "home") in u["skill"]

    def test_mcp_selftest_handshake_works_for_real(self, studio):
        r = agentkit.selftest()
        assert r["ok"] and r["tools"] == len(registry.REGISTRY) and r["protocol"] == "2025-06-18"


# ============================================================ serwer MCP

class TestMcp:
    def _srv(self):
        s = McpServer()
        s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        return s

    def test_initialize_negotiates_protocol(self):
        s = McpServer()
        r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})["result"]
        assert r["protocolVersion"] == "2024-11-05" and r["serverInfo"]["name"] == "vstudio" and "tools" in r["capabilities"]
        r2 = McpServer().handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})["result"]
        assert r2["protocolVersion"] == "2025-06-18"

    def test_tools_list_matches_registry_and_has_valid_schemas(self):
        tools = self._srv().handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        assert [t["name"] for t in tools] == list(registry.REGISTRY)
        for t in tools:
            assert t["inputSchema"]["type"] == "object" and t["inputSchema"]["additionalProperties"] is False and t["description"]
        ro = {t["name"]: t["annotations"]["readOnlyHint"] for t in tools}
        assert ro["studio_status"] and not ro["scene_write"] and not ro["render_start"]

    def test_tool_call_success_error_and_unknown(self, studio):
        s = self._srv()
        ok = s.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "studio_status", "arguments": {}}})["result"]
        assert ok["isError"] is False and "next" in ok["structuredContent"] and json.loads(ok["content"][0]["text"])["ready"] in (True, False)
        err = s.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "project_get", "arguments": {"project": "x/y"}}})["result"]
        assert err["isError"] is True and "brak projektu" in err["content"][0]["text"]
        unk = s.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "nie_ma", "arguments": {}}})
        assert unk["error"]["code"] == -32602
        assert activity.agent_status()["connected"]                     # wywołania z MCP zapalają „agent połączony”

    def test_resources_and_prompts(self, studio):
        call("project_create", slug="r", brand="b")
        s = self._srv()
        uris = [r["uri"] for r in s.handle({"jsonrpc": "2.0", "id": 6, "method": "resources/list"})["result"]["resources"]]
        assert "vstudio://skill" in uris and "vstudio://knowledge/gsap" in uris and "vstudio://project/b/r/brief" in uris
        skill = s.handle({"jsonrpc": "2.0", "id": 7, "method": "resources/read", "params": {"uri": "vstudio://skill"}})["result"]["contents"][0]["text"]
        assert skill.startswith("---\nname: vstudio")
        brief = s.handle({"jsonrpc": "2.0", "id": 8, "method": "resources/read", "params": {"uri": "vstudio://project/b/r/brief"}})["result"]["contents"][0]["text"]
        assert "Brief" in brief or "brief" in brief
        assert s.handle({"jsonrpc": "2.0", "id": 9, "method": "resources/read", "params": {"uri": "vstudio://nie-ma"}})["error"]["code"] == -32002
        pr = s.handle({"jsonrpc": "2.0", "id": 10, "method": "prompts/get", "params": {"name": "make-video", "arguments": {"idea": "kawa"}}})["result"]
        assert "kawa" in pr["messages"][0]["content"]["text"]

    def test_notifications_get_no_reply_and_bad_method_errors(self):
        s = self._srv()
        assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        assert s.handle({"jsonrpc": "2.0", "id": 11, "result": {}}) is None                 # odpowiedź klienta
        assert s.handle({"jsonrpc": "2.0", "id": 12, "method": "foo/bar"})["error"]["code"] == -32601
        assert s.handle({"jsonrpc": "2.0", "id": 13, "method": "ping"})["result"] == {}

    def test_stdout_stays_clean_protocol_only(self):
        p = subprocess.run([sys.executable, str(REPO / "vstudio.py"), "mcp"], input='{"jsonrpc":"2.0","id":1,"method":"ping"}\nto nie jest json\n',
                           capture_output=True, text=True, timeout=30)
        lines = [json.loads(line) for line in p.stdout.splitlines()]
        assert lines[0]["result"] == {} and lines[1]["error"]["code"] == -32700 and len(lines) == 2


# ============================================================ serwer dashboardu: API i bezpieczeństwo

@pytest.fixture
def dash(studio):
    from vstudio.dashboard import server

    srv, _ = server.start_background()
    port = srv.server_address[1]

    def req(method, path, body=None, headers=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        c.request(method, path, body=body, headers={"Host": host or f"127.0.0.1:{port}", **(headers or {})})
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, dict(r.getheaders()), data

    token = re.search(rb'name="token" content="([^"]+)"', req("GET", "/")[2]).group(1).decode()
    hdr = {"Content-Type": "application/json", "X-Studio-Token": token, "Origin": f"http://127.0.0.1:{port}"}
    yield type("D", (), {"req": staticmethod(req), "token": token, "hdr": hdr, "port": port, "studio": studio})
    srv.shutdown()


class TestDashboardServer:
    def test_index_and_static(self, dash):
        st, h, body = dash.req("GET", "/")
        assert st == 200 and b"vstudio" in body and h["Cache-Control"] == "no-store" and h["X-Content-Type-Options"] == "nosniff"
        for f in ("app.css", "core.js", "views-home.js", "views-project.js", "views-agent.js", "views-misc.js"):
            assert dash.req("GET", f"/static/{f}")[0] == 200
        assert dash.req("GET", "/static/../server.py")[0] == 404

    def test_post_requires_token_origin_content_type_and_host(self, dash):
        body = b"{}"
        assert dash.req("POST", "/api/call/studio_status", body, {"Content-Type": "application/json"})[0] == 403           # brak tokenu
        assert dash.req("POST", "/api/call/studio_status", body, {**dash.hdr, "X-Studio-Token": "zly"})[0] == 403
        assert dash.req("POST", "/api/call/studio_status", body, {**dash.hdr, "Origin": "http://evil.example"})[0] == 403
        assert dash.req("POST", "/api/call/studio_status", body, {**dash.hdr, "Content-Type": "text/plain"})[0] == 415
        assert dash.req("POST", "/api/call/studio_status", body, dash.hdr, host="evil.example")[0] == 403                # DNS rebinding
        assert dash.req("GET", "/api/pulse", host="evil.example")[0] == 403
        assert dash.req("POST", "/api/call/studio_status", b"{zle", dash.hdr)[0] == 400
        st, _, data = dash.req("POST", "/api/call/studio_status", body, dash.hdr)
        assert st == 200 and "next" in json.loads(data)

    def test_api_errors_are_400_with_messages(self, dash):
        st, _, data = dash.req("POST", "/api/call/project_get", json.dumps({"project": "../../etc"}).encode(), dash.hdr)
        assert st == 400 and "niepoprawny identyfikator" in json.loads(data)["error"]
        assert dash.req("POST", "/api/call/nie_ma", b"{}", dash.hdr)[0] == 400
        assert dash.req("POST", "/api/zle", b"{}", dash.hdr)[0] == 404

    def test_capabilities_and_pulse(self, dash):
        data = json.loads(dash.req("GET", "/api/capabilities")[2])
        assert len(data["capabilities"]) == len(registry.REGISTRY) and data["categories"]
        pulse = json.loads(dash.req("GET", "/api/pulse")[2])
        assert {"events", "agent", "jobs", "projects", "open_tasks", "now"} <= set(pulse)

    def test_file_serving_is_confined_and_supports_range(self, dash):
        call("project_create", slug="f", brand="b", template="hide-the-cut")
        pdir = dash.studio / "b" / "f"
        (pdir / "renders").mkdir(exist_ok=True)
        (pdir / "renders" / "x.mp4").write_bytes(bytes(range(200)))
        (pdir / "src" / ".history").mkdir(exist_ok=True)
        (pdir / "src" / ".history" / "sekret.html").write_text("tajne")
        assert dash.req("GET", "/files/b/f/renders/x.mp4")[0] == 200
        st, h, data = dash.req("GET", "/files/b/f/renders/x.mp4", headers={"Range": "bytes=10-19"})
        assert st == 206 and h["Content-Range"] == "bytes 10-19/200" and data == bytes(range(10, 20))
        assert dash.req("GET", "/files/b/f/renders/x.mp4", headers={"Range": "bytes=500-"})[0] == 416
        for bad in ("/files/b/f/../../../../etc/passwd", "/files/b/f/src/.history/sekret.html", "/files/b/f/%2e%2e/%2e%2e/output/x", "/files/b/nie-ma/x.png",
                    "/files/b/f/src/index.py", "/preview/b/f/../../x.html", "/vendor/..%2fproject.json", "/template/../etc/"):
            assert dash.req("GET", bad)[0] == 404, bad

    def test_preview_injects_capture_and_vendor(self, dash, tmp_path):
        lib = tmp_path / "g.js"
        lib.write_text("window.gsapFake = 1;")
        vendor.add("gsap", file=str(lib))
        call("project_create", slug="pv", brand="b", template="hide-the-cut")
        st, h, html = dash.req("GET", "/preview/b/pv/")
        assert st == 200 and b"window.__CAPTURE__ = true" in html and b"/vendor/" in html and h["Content-Type"].startswith("text/html")
        assert b"__CAPTURE__ = true" not in dash.req("GET", "/preview/b/pv/?live=1")[2]
        assert b"window.__CAPTURE__ = true" in dash.req("GET", "/template/hide-the-cut/")[2]
        assert dash.req("GET", "/vendor/" + vendor.listing()[0]["file"])[2] == b"window.gsapFake = 1;"

    def test_preview_is_sandboxed_and_vendor_has_no_cors(self, dash, tmp_path):
        lib = tmp_path / "g.js"
        lib.write_text("1;")
        vendor.add("gsap", file=str(lib))
        call("project_create", slug="sb", brand="b", template="hide-the-cut")
        for path in ("/preview/b/sb/", "/template/hide-the-cut/"):
            st, h, html = dash.req("GET", path)
            assert st == 200 and h["Content-Security-Policy"] == "sandbox allow-scripts"       # nieprzezroczysty origin: bez dostępu do tokenu
            assert b"vstudio: 'req'" in html or b"vstudio !== 'req'" in html                # most postMessage wstrzyknięty
        st, h, _ = dash.req("GET", "/vendor/" + vendor.listing()[0]["file"])
        assert st == 200 and "Access-Control-Allow-Origin" not in h

    def test_calls_from_the_dashboard_return_image_urls(self, dash):
        res = registry.REGISTRY["studio_status"]
        assert not res.images
        st, _, data = dash.req("POST", "/api/call/templates_list", b"{}", dash.hdr)
        assert st == 200 and len(json.loads(data)["templates"]) >= 8


# ============================================================ watcher

class TestWatcher:
    def test_watcher_only_reacts_to_real_changes(self, studio, monkeypatch):
        from vstudio.dashboard.watcher import Watcher

        call("project_create", slug="w", brand="b", template="hide-the-cut")
        ran = []
        monkeypatch.setattr(supervisor, "check", lambda pdir, pr, depth="standard", save=True: ran.append(depth) or
                            {"verdict": "pass", "score": 100, "counts": {"error": 0, "warn": 0, "info": 0}, "round": 1})
        w = Watcher()
        assert w.tick() == []                                   # pierwszy przebieg tylko „uzbraja”
        w.primed = True
        assert w.tick() == []                                   # nic się nie zmieniło
        src = studio / "b" / "w" / "src" / "index.html"
        time.sleep(0.05)
        src.write_text(src.read_text(encoding="utf-8") + "\n<!-- zmiana -->", encoding="utf-8")
        assert w.tick() == ["b/w"] and ran == ["quick"]
        assert w.tick() == []                                   # ta sama zmiana nie wyzwala drugi raz
        call("profile_set", name="M", auto_supervise=False)
        time.sleep(0.05)
        src.write_text(src.read_text(encoding="utf-8") + "\n<!-- druga -->", encoding="utf-8")
        assert w.tick() == [] and ran == ["quick"]              # wyłączone w profilu


# ============================================================ nadzorca w przeglądarce

pytestmark_browser = pytest.mark.browser


@pytest.mark.browser
class TestSupervisorInBrowser:
    def _mk(self, studio, template="three-colours-only"):
        call("project_create", slug="b1", brand="t", template=template)
        return "t/b1"

    def test_clean_template_passes_core_checks_and_reports_rounds(self, vendored_studio):
        pid = self._mk(vendored_studio)
        r1 = call("check_run", project=pid, depth="quick")
        codes = {f["code"] for f in r1["findings"]}
        assert r1["round"] == 1 and r1["delta"] is None and r1["metrics"]["deterministic"] is True
        assert not codes & {"PAGE_ERROR", "NET_FAILED", "NO_SEEK", "NONDETERMINISTIC", "SEEK_FAILED"}
        assert r1["metrics"]["samples"] >= 28 and r1["score"] <= 100 and r1["images"] and Path(r1["images"][0]["path"]).is_file()
        r2 = call("check_run", project=pid, depth="quick")
        assert r2["round"] == 2 and r2["delta"]["since_round"] == 1 and r2["delta"]["new"] == [] and r2["delta"]["persisting"] >= 1
        assert [h["round"] for h in call("check_history", project=pid)["rounds"]] == [1, 2]
        assert call("check_latest", project=pid)["report"]["round"] == 2

    def test_missing_library_is_reported_with_the_fix(self, studio, monkeypatch):
        from vstudio import vendor

        real = vendor.install_routes

        def offline(target):                                     # bez vendora i bez sieci: CDN odrzuca żądania (CI ma dostęp do sieci)
            real(target)
            target.route(re.compile(r"https?://(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|unpkg\.com)/"), lambda route: route.abort())
            return False

        monkeypatch.setattr(vendor, "install_routes", offline)
        pid = self._mk(studio)
        r = call("check_run", project=pid, depth="quick")
        assert r["verdict"] == "blocked" and {"PAGE_ERROR", "NET_FAILED"} & {f["code"] for f in r["findings"]}
        assert any("vendor_add" in a for a in r["next_actions"])

    def test_injected_js_error_and_nondeterminism_are_caught(self, vendored_studio):
        pid = self._mk(vendored_studio)
        call("scene_patch", project=pid, edits=[{"find": "window.DURATION = DUR;", "replace": "window.DURATION = DUR; null.boom();"}])
        r = call("check_run", project=pid, depth="quick")
        assert any(f["code"] == "PAGE_ERROR" and "boom" in f["detail"] for f in r["findings"])
        call("scene_restore", project=pid, version=call("scene_history", project=pid)["versions"][0]["version"])
        call("scene_patch", project=pid, edits=[{"find": "window.seek = function (t) { tl.pause();",
                                                 "replace": "window.seek = function (t) { t = t + (window.__n = (window.__n || 0) + 1) * 0.013; tl.pause();"}])
        r = call("check_run", project=pid, depth="quick")
        assert r["metrics"]["deterministic"] is False and any(f["code"] == "NONDETERMINISTIC" for f in r["findings"])
        assert r["verdict"] == "blocked"

    def test_frames_timeline_and_scene_write_with_check(self, vendored_studio):
        pid = self._mk(vendored_studio, "one-hero-one-world")
        fv = call("frames_view", project=pid, times=[1.0, 3.0])
        assert len(fv["images"]) == 2 and all(Path(i["path"]).is_file() for i in fv["images"])
        sheet = call("frames_view", project=pid, times=[0.5, 2, 4, 6])["images"]
        assert len(sheet) == 1 and Path(sheet[0]["path"]).name == "sheet.jpg"
        tl = call("timeline_get", project=pid)
        assert tl["duration"] == 7 and tl["events"] and any(t["text"] == "NOIR" for t in tl["texts"])
        content = call("scene_read", project=pid)["content"]
        w = call("scene_write", project=pid, content=content, note="bez zmian", check="quick")
        assert w["check"]["round"] == 1 and w["images"]

    def test_unsupported_engine_is_reported_not_crashed(self, vendored_studio, monkeypatch):
        pid = self._mk(vendored_studio)
        pdir, pr = workspace.resolve(pid)
        pr["engine"] = "remotion"
        rep = supervisor.check(pdir, pr, "quick", save=False)
        assert [f["code"] for f in rep["findings"]] == ["ENGINE_UNSUPPORTED"] and rep["verdict"] == "pass"


# ============================================================ interfejs: smoke test w przeglądarce

@pytest.mark.browser
class TestDashboardUi:
    def test_all_views_render_without_errors(self, vendored_studio):
        from playwright.sync_api import sync_playwright
        from vstudio.dashboard import server

        call("profile_set", name="Test")
        call("project_create", slug="ui", brand="t", template="three-colours-only")
        srv, _ = server.start_background()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        problems: list[str] = []
        try:
            with sync_playwright() as pw:
                br = pw.chromium.launch(args=["--disable-gpu-rasterization", "--disable-partial-raster"])
                pg = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
                pg.on("pageerror", lambda e: problems.append(str(e)))
                pg.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
                pg.goto(base + "/#/")
                pg.evaluate("sessionStorage.setItem('onboardSkipped','1')")
                for route, marker in (("#/", "Co dziś tworzymy"), ("#/library", "Biblioteka szablonów"), ("#/agent", "Aktywność na żywo"), ("#/map", "Mapa możliwości"),
                                      ("#/onboarding", "Sprawdzam środowisko"), ("#/p/t/ui", "Uruchom nadzór"), ("#/p/t/ui/zrodlo", "Zapisz i sprawdź"),
                                      ("#/p/t/ui/render", "Render roboczy"), ("#/p/t/ui/potok", "NASTĘPNY KROK"), ("#/p/t/ui/agent", "Wyślij do agenta")):
                    pg.goto(base + "/" + route)
                    pg.wait_for_function("(m) => document.body.innerText.includes(m)", arg=marker, timeout=20000)
                # podgląd sceny: zasłona znika, a scena reaguje na seek z transportu
                pg.goto(base + "/#/p/t/ui")
                pg.wait_for_function("document.querySelector('#veil') && document.querySelector('#veil').hidden", timeout=20000)
                pg.click("#tFwd")
                assert "kl. 1" in pg.inner_text("#tFrame")
                pg.keyboard.press("ArrowRight")
                assert "kl. 2" in pg.inner_text("#tFrame")
                # nadzór z interfejsu
                pg.click("#runCheck")
                pg.wait_for_function("document.body.innerText.includes('runda 1')", timeout=90000)
                # XSS: napisy z agenta są escapowane
                call("task_create", prompt="<img src=x onerror=window.__xss=1>", project="t/ui")
                pg.goto(base + "/#/agent")
                pg.wait_for_function("document.body.innerText.includes('<img src=x')", timeout=20000)
                assert pg.evaluate("window.__xss") is None
                br.close()
        finally:
            srv.shutdown()
        assert problems == []


@pytest.mark.browser
class TestPaletteUi:
    def test_changing_a_swatch_recolors_the_scene_and_brand_modal_works(self, vendored_studio):
        from playwright.sync_api import sync_playwright
        from vstudio.dashboard import server

        call("profile_set", name="Marka", palette={"bg": "#101820", "accent": "#00B894"})
        call("project_create", slug="pal", brand="t", template="hide-the-cut")
        srv, _ = server.start_background()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        problems: list[str] = []
        try:
            with sync_playwright() as pw:
                br = pw.chromium.launch(args=["--disable-gpu-rasterization", "--disable-partial-raster"])
                pg = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
                pg.on("pageerror", lambda e: problems.append(str(e)))
                pg.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
                pg.goto(base + "/#/")
                pg.evaluate("sessionStorage.setItem('onboardSkipped','1')")
                pg.goto(base + "/#/p/t/pal/zrodlo")
                pg.wait_for_selector("#swatches input[type=color]", timeout=30000)
                assert pg.locator("#swatches input[type=color]").count() >= 5
                pg.evaluate("""() => { const i = document.querySelector('#swatches input[data-from="#2F5BFF"]'); i.value = '#ff0066'; i.dispatchEvent(new Event('change', {bubbles: true})); }""")
                pg.wait_for_function("document.body.innerText.includes('Zmieniono kolory')", timeout=20000)
                src = call("scene_read", project="t/pal")["content"]
                assert "#FF0066" in src and "#2F5BFF" not in src
                pg.wait_for_selector("#swatches input[data-from='#FF0066']", timeout=20000)          # paleta odświeżona po zmianie
                pg.click("#brandBtn")
                pg.wait_for_selector(".modal .map-row", timeout=10000)
                assert "Tło" in pg.inner_text(".modal")
                pg.click("#mApply")
                pg.wait_for_function("!document.querySelector('.modal')", timeout=20000)
                assert "#101820" in call("scene_read", project="t/pal")["content"]
                br.close()
        finally:
            srv.shutdown()
        assert problems == []


@pytest.mark.browser
class TestUxExtras:
    def _page(self, studio_dir, pw, base, problems):
        br = pw.chromium.launch(args=["--disable-gpu-rasterization", "--disable-partial-raster"])
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: problems.append(str(e)))
        pg.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        pg.goto(base + "/#/")
        pg.evaluate("sessionStorage.setItem('onboardSkipped','1')")
        return br, pg

    def test_job_toast_vendor_row_and_copy_prompt(self, vendored_studio):
        from playwright.sync_api import sync_playwright
        from vstudio.dashboard import server

        call("profile_set", name="M")
        call("project_create", slug="ux", brand="t", template="hide-the-cut")
        pdir = vendored_studio / "t" / "ux"
        (pdir / "supervisor").mkdir()
        finding = {"code": "DEAD_TIME", "severity": "warn", "title": "Martwy czas", "detail": "obraz stoi 1-3 s", "t": 1.0, "box": None, "fix": "Add a slow push-in.", "id": ""}
        (pdir / "supervisor" / "latest.json").write_text(json.dumps({
            "project": "t/ux", "round": 1, "depth": "quick", "at": "2026-01-01T00:00:00", "verdict": "needs_fixes", "score": 92, "counts": {"error": 0, "warn": 1, "info": 0},
            "findings": [finding], "delta": None, "next_actions": [], "metrics": {"elapsed_s": 1.0}, "assets": None}))
        srv, _ = server.start_background()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        problems: list[str] = []
        try:
            with sync_playwright() as pw:
                br, pg = self._page(vendored_studio, pw, base, problems)
                pg.wait_for_function("window.V && V.S.pulse", timeout=20000)
                j = jobs.start("deliver", "t/ux", pdir, ["tools"])                          # job krótszy niż okres odpytywania
                pg.wait_for_function("document.querySelector('#toasts').innerText.includes('Wydanie ux: gotowe')", timeout=20000)
                pg.goto(base + "/#/onboarding")
                pg.wait_for_function("document.body.innerText.includes('Biblioteki offline') && document.body.innerText.includes('lokalna kopia')", timeout=20000)
                pg.goto(base + "/#/p/t/ux")
                pg.wait_for_selector(".finding", timeout=20000)
                pg.click(".finding")
                pg.click("[data-copy]")
                clip = pg.evaluate("navigator.clipboard.readText()")
                assert "DEAD_TIME" in clip and "scene_patch" in clip and "Add a slow push-in." in clip and j["id"]
                br.close()
        finally:
            srv.shutdown()
        assert problems == []
