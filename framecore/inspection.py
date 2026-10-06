"""Kontrola struktury i rzeczywista klatka dla agenta, bez zmian montażu."""
import base64
import shutil
from pathlib import Path
from .model import number

GUIDE = """Pracujesz w TABASCO CREATIVES + FRAMECORE — STUDIO, projekcie współpracy człowieka z agentem.
1. Odczytaj get_project i get_selection. Uwzględnij zaznaczenie, playhead, ścieżki i blokady.
2. Odczytaj list_motion, list_templates, list_icons, list_library, list_fonts i list_backgrounds; używaj wyłącznie dostępnych identyfikatorów.
3. Każda zmiana treści wymaga expected_revision. Po konflikcie odczytaj stan ponownie; nie nadpisuj pracy człowieka.
4. Kilka powiązanych zmian połącz przez propose_changes. Pokaż commands, changes i removed; zastosuj apply_proposal zgodnie z poleceniem użytkownika.
5. inspect_project wykrywa problemy techniczne. capture_frame zwraca rzeczywisty obraz; obejrzyj klatki przed, w trakcie i po animacji. Raport struktury nie zastępuje oceny wizualnej.
6. Klatki kluczowe mają property (x/y/rotation/scale/opacity), time w sekundach względem początku klipu i value. Interpolacja jest liniowa.
7. Dźwięk zmieniaj przez set_audio: gain 0–1, fadeIn i fadeOut w sekundach. Sprawdź cały miks w filmie.
8. Materiały importuj z katalogu imports przy katalogu projektów. Nie wklejaj kodu HTML ani adresów plików z innych lokalizacji.
9. Materiały lokalne dodawaj przez add_library_asset, tło przez set_background. Przekazuj template_id z plan_storyboard do assemble_storyboard, aby zachować wygląd szablonu.
10. Odczytaj get_production_status: brief, requiredAssets, blokery i ważność oceny. annotate_story_beats i set_scene_beat zapisują cel oraz stany scen. apply_motion_rules różnicuje czas i krzywą ruchu.
11. create_review generuje rzeczywiste klatki i planszę; obejrzyj je przed review_verdict. Nie zaznaczaj checklisty bez oceny. Przy błędzie proponuj lokalną poprawkę; najwyżej dwie autonomiczne rundy, potem raport. To instrukcja pracy, nie automatyczny kontroler napraw.
12. create_format_variant tworzy osobny układ startowy; każda kopia wymaga własnego przeglądu. package_delivery pakuje ukończony eksport z artefaktami.
13. Odczytaj get_motion_playbook: zasady historii, sześć reguł ruchu i instrukcja niezależnej oceny. Nie wymyślaj opinii klientów, rezultatów ani ukończonych realizacji.
14. Po ukończeniu eksportu użyj analyze_export z job_id i profile (calm/punchy/mute), a get_quality_report do powrotu do pomiaru. Raport dotyczy zamrożonego MP4 i nie zastępuje oceny ani odsłuchu.
15. replace_clip_asset zmienia źródło, zachowując geometrię, czas i animację. Krótsze źródło wymaga jawnego fit_source. add_track tworzy warstwę; move_clip track_id może wskazać tylko odblokowaną zgodną ścieżkę (obrazy i wideo mogą współdzielić ścieżkę).
16. get_storytelling_playbook opisuje lekcję przez historię. plan_visual_lesson to plan startowy; assemble_visual_lesson zapisuje 7 edytowalnych scen. set_scene_learning dodaje narrację, cel, obraz i przejście. get_lesson_status sprawdza kompletność opisów, nie sens ani audio. Nie przedstawiaj planu jako gotowej lekcji.
17. Eksportuj aktualną rewizję, sprawdź get_job i wynik MP4. Nie twierdź, że brakujący dostawca AI wygenerował materiał.
18. Ruch 2.0: apply_motion przyjmuje wejścia (kind entrance) i tekst kinetyczny (kind kinetic: type-on, word-cascade, char-rise, word-blur, char-wave, scramble-in, word-highlight; tylko tekst i napisy, czas do 4 s). apply_exit nadaje wyjście w ostatnich sekundach klipu (exit_id "none" usuwa). Krzywe: linear, quad-out, cubic-out, quint-out, expo-out, back-out, elastic-out, cubic-in-out.
19. Wygląd elementu ustawisz przez set_property: style.shadow (none/soft/lift/glow/neon/long), style.shadowColor, style.gradient {from,to,angle} lub null, style.letterSpacing, style.strokeWidth, style.strokeColor, style.blend, style.fit (contain/cover).
20. set_canvas_fx ustawia look całego filmu: grade (none/cinematic/warm/cool/mono/vivid/faded/noir), vignette 0–1, grain 0–1, letterbox 0–0.25, transition (none/dip/flash/wipe/light-leak/blur) na cięciach między scenami, transitionDuration oraz motionBlur dla finalnego eksportu.
"""


def inspect(p):
    issues = []
    width, height = p["canvas"]["width"], p["canvas"]["height"]
    hidden = {t["id"] for t in p["tracks"] if t["hidden"]}
    for e in p["elements"]:
        if e["type"] == "audio" or e["trackId"] in hidden: continue
        points = [(e["x"], e["y"], e["scale"])]
        # Conservative bounds at each property keyframe; motion/rotation need visual review.
        times = sorted({k["time"] for k in e.get("keyframes", [])})
        for t in times:
            values = dict(x=e["x"], y=e["y"], scale=e["scale"])
            for prop in values:
                ks = sorted((k for k in e["keyframes"] if k["property"]==prop), key=lambda k:k["time"])
                if ks:
                    values[prop] = ks[-1]["value"]
                    if t <= ks[0]["time"]: values[prop] = ks[0]["value"]
                    else:
                        for a,b in zip(ks,ks[1:]):
                            if t <= b["time"]:
                                values[prop] = a["value"]+(b["value"]-a["value"])*(t-a["time"])/(b["time"]-a["time"])
                                break
            points.append((values["x"],values["y"],values["scale"]))
        if any(x-e["width"]*(scale-1)/2 < 0 or y-e["height"]*(scale-1)/2 < 0 or
               x+e["width"]*(scale+1)/2 > width or y+e["height"]*(scale+1)/2 > height for x,y,scale in points):
            issues.append({"code": "outside_canvas", "element_id": e["id"], "message": "Element wychodzi poza obszar filmu"})
        if e["type"] in {"text", "caption"} and e["style"]["fontSize"] < width*.018:
            issues.append({"code": "small_text", "element_id": e["id"], "message": "Tekst może być zbyt mały na telefonie"})
        if e.get("motion") and e["motion"]["duration"] > e["duration"]:
            issues.append({"code": "unfinished_motion", "element_id": e["id"], "message": "Klip kończy się przed zakończeniem wejścia"})
        if e.get("motion") and e.get("exit") and e["motion"]["duration"] + e["exit"]["duration"] > e["duration"] + 1e-6:
            issues.append({"code": "motion_overlap", "element_id": e["id"], "message": "Wejście i wyjście nakładają się; wydłuż klip lub skróć ruch"})
    return {"project_id": p["id"], "revision": p["revision"], "issues": issues,
            "summary": {"elements": len(p["elements"]), "scenes": len(p["scenes"]), "assets": len(p["assets"])},
            "limitations": "Kontrola geometrii bez pomiaru łamania tekstu, obrotów, kolizji i kontrastu. Obejrzyj capture_frame."}


def capture(store, pid, time=None):
    from .server import start_background
    from playwright.sync_api import sync_playwright
    from .composition import compile_project
    import json
    # Freeze content in memory rather than rereading the composition after browser startup.
    p = store.read(pid)["project"]
    t = number(time if time is not None else store.context(pid)["playhead"], "time", 0, p["duration"])
    server, _ = start_background(store)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**({"executable_path": shutil.which("chromium")} if shutil.which("chromium") else {}))
            try:
                page = browser.new_page(viewport={"width":p["canvas"]["width"], "height":p["canvas"]["height"]})
                base = f"http://127.0.0.1:{server.server_port}"
                page.goto(base)
                page.set_content(compile_project(p, f"{base}/assets/{pid}/"))
                page.evaluate("window.__CAPTURE__=true")
                page.evaluate("window.__ready")
                page.evaluate("t=>window.seek(t)", t)
                data = page.screenshot()
                return {"project_id":pid, "revision":p["revision"], "time":t, "mimeType":"image/png", "data":base64.b64encode(data).decode()}
            finally: browser.close()
    finally:
        server.shutdown(); server.server_close()
