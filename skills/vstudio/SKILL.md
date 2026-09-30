---
name: vstudio
description: Generate, supervise and deliver code-rendered videos and motion graphics with the vstudio studio (deterministic HTML scenes rendered via Playwright/FFmpeg). Use when the user wants a video, animation, motion graphic, product demo or reel made, edited, checked or rendered, or when a vstudio MCP server is connected.
---

# vstudio: studio filmowe dla agenta

vstudio to deterministyczne studio: film to strona HTML, w której obraz jest czystą funkcją czasu. Ty piszesz scenę, a studio
**pilnuje jakości**: po każdej zmianie nadzorca (`check_run`) sprawdza błędy, klatki, pętlę, determinizm, czytelność i kontrast
i mówi, co poprawić. Użytkownik widzi to samo w dashboardzie (`python vstudio.py dashboard`).

## Połączenie

Serwer MCP: `python vstudio.py mcp` (stdio). Z poziomu dashboardu: Agent → Połącz. Albo: `claude mcp add vstudio -- python vstudio.py mcp`.
Zacznij od `studio_status`: mówi, czy środowisko działa, czy jest profil marki i co robić dalej.

## Pętla pracy

# Work loop (follow it; the supervisor is your eyes)

1. `studio_status` first. If the studio is not onboarded, ask the user for brand, palette, font, tone and default format, then `profile_set`.
2. `task_next` returns what the user asked for in the dashboard. `task_update` -> in_progress.
3. Choose a start: `templates_list` then `project_create` (from a template, or blank). Read the brief; `knowledge_get topic=brand|motion|visual|gsap|contract`.
4. Edit the scene: `scene_read`, then `scene_write` / `scene_patch` with `check: "quick"`.
5. LOOK at the film: `frames_view` with times at the opening, the main beat, the fastest transition and the end. Judge hierarchy, spacing, cut-off text, stray shapes.
6. `check_run` (standard). Fix errors first, then warnings, then re-run; read `delta` to see what you resolved and what is new. Repeat until `verdict: pass`.
   If a warning is intentional (e.g. a prompt demands a static hold), say so in `task_update` notes and keep it.
7. `render_start` (draft) then `job_wait`; `gate_set` approve stills/brief/visual_rules when genuinely done; `render_start` final; `deliver_start`.
8. `task_update` -> done with a short note: what was made, which warnings remain and why.

Never report success without a `pass` verdict or an explicit note. After 6 rounds without progress, stop and ask the user. Never overwrite a scene without `scene_write` (it keeps history; `scene_restore` undoes).

## Zasady sceny

# Page contract (html engine)

A film is one HTML page whose picture is a pure function of time. The renderer steps the page frame by frame and screenshots it.

Required on `window`:
- `DURATION` (number): film length in seconds.
- `seek(t)`: draw the frame for time `t` (seconds), deterministically. Must work for any t in [0, DURATION], in any order.
- `__ready` (Promise): resolves when fonts and images are ready (`document.fonts.ready.then(fit)` is enough).
- `__CAPTURE__` (boolean, set by the renderer BEFORE page scripts run): when true, do not start any autoplay loop; only `seek` moves the picture.

Strongly recommended:
- `EV = [{t, type}]` sound events (types: whoosh, hit/impact, pop, click, chime, tick, reveal, type). Sound is generated from these.
- `TEXTS(t) = [{id, text, x0, y0, x1, y1}]` every visible text with its pixel box at time t, so reading time, framing, contrast and
  safe zones can be checked. Read the same source as the drawing code; if you forget a text here the check will say OK for text that is not drawn.

Rules: no Math.random, no timers, no CSS transitions/animations, no state carried between frames. One continuous motion beats cuts.
Layout is relative to the viewport or a fixed stage scaled to fit, so one file exports to 16:9, 9:16 and 1:1.

# Deterministic GSAP recipe

Load GSAP from https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js (call `vendor_add` with `gsap` once so preview,
checks and render also work offline). Skeleton:

```js
var DUR = 7, CAPTURE = !!window.__CAPTURE__;
gsap.config({ force3D: false });                       // 2D transforms: no compositor layer promotion, frames do not depend on history
var tl = gsap.timeline({ repeat: -1, paused: CAPTURE });
tl.set('#a', { opacity: 0, x: 0 }, 0);                 // EVERY start state set at time 0 of the timeline: loops reset cleanly
tl.to('#a', { opacity: 1, duration: 0.6 }, 0.5);
tl.set({}, {}, DUR);                                   // timeline lasts exactly DUR
if (CAPTURE) { tl.totalTime(DUR - 0.001, false); tl.totalTime(0, false); }   // warm-up: initialise every tween in order
window.DURATION = DUR;
window.seek = function (t) { tl.pause(); tl.totalTime(((t % DUR) + DUR) % DUR, false); };
```

Pitfalls (each one produces a finding):
1. Never let two tweens of the SAME property on the SAME element overlap in time. The earlier one keeps writing after the later one
   ends, so the final value depends on seek order (NONDETERMINISTIC). Use `tl.set` at a computed time instead.
2. No `yoyo`/`repeat` inside tweens, no `onUpdate`/`.call()` for state, no timers, no Math.random. Write a fixed sequence of explicit tweens.
3. `from()`/`fromTo()` render their start values immediately; build "hidden until later" states with `tl.set(..., 0)` then `.to()`.
4. Centre with flexbox or explicit left/top, never `transform: translate(-50%)` (GSAP owns transform). Animate size and border-radius in px, not %.
5. Toggle visibility with `autoAlpha` through `tl.set`; make TEXTS read the DOM (Range rect + opacity + visibility) so it never lies.
6. To sync one motion to another, pass a function as `ease` computed from the other motion's progress (see examples/motion-graphics/03).
7. Holds over 1 s need a slow push-in or drift (DEAD_TIME), and a looping film must end where it starts (NOT_LOOPING) unless a hard reset is intended.
8. 3D: put `perspective` on the PARENT, rotate a child with `rotationY`; fake thickness with a stack of planes at different translateZ.

## Narzędzia

Każde narzędzie jest zarejestrowane w jednym miejscu (`vstudio/registry.py`); ta tabela jest generowana.

### Start i połączenie agenta

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `studio_status` | - | Jedno wywołanie: środowisko, profil marki, agent, projekty, zadania i co zrobić dalej. |
| `profile_get` | - | Nazwa, paleta, font, ton, odbiorcy i domyślny format użytkownika. |
| `profile_set` | `name`?, `palette`?, `font`?, `tone`?, `audience`?, `default_format`?, `fps`?, `auto_supervise`? | Ustawia profil marki (częściowo). Uzupełnienie nazwy kończy onboarding. (zmienia pliki) |
| `agent_connect_info` | - | Polecenie MCP, fragment .mcp.json, ścieżki skilla i stan połączenia agenta. |
| `agent_selftest` | - | Uruchamia serwer MCP i robi handshake jak prawdziwy klient: dowód, że agent się połączy. |
| `agent_install` | `skill`?, `mcp_config`?, `scope`? | Zapisuje skill (SKILL.md) i wpis vstudio w .mcp.json. (zmienia pliki) |

### Biblioteka szablonów

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `templates_list` | - | Katalog szablonów: opis, technika, format, czas, tagi i czy wymagają sieci. |
| `project_create` | `slug`, `brand`?, `template`?, `format`?, `size`?, `fps`?, `duration`?, `brief`? | Tworzy projekt (opcjonalnie z szablonu) z briefem; format z szablonu lub profilu marki. (zmienia pliki) |

### Projekty i bramki jakości

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `projects_list` | - | Wszystkie projekty z postępem bramek, następnym krokiem i wynikiem ostatniego nadzoru. |
| `project_get` | `project` | Bramki, rendery, zadania, pokrycie vendorem i podsumowanie nadzoru jednego projektu. |
| `gate_set` | `project`, `action`, `gate`?, `score`? | Zatwierdza/resetuje bramkę (brief, visual_rules, stills, draft, sound, critic, final) albo ustawia wynik krytyka. (zmienia pliki) |

### Scena (kod filmu)

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `scene_read` | `project`, `start_line`?, `end_line`? | Kod sceny (src/index.html) z informacją o haczykach kontraktu i zasobach z sieci. |
| `scene_write` | `project`, `content`, `note`?, `check`? | Zapisuje całą scenę (z kopią w historii). Z `check` od razu uruchamia nadzorcę i zwraca werdykt. (zmienia pliki) (obrazy) |
| `scene_patch` | `project`, `edits`, `note`?, `check`? | Zamienia dokładne fragmenty tekstu (każdy musi wystąpić raz, chyba że all=true). Atomowo, z historią. (zmienia pliki) (obrazy) |
| `scene_history` | `project` | Ostatnie wersje sceny (do 30) z notatkami. |
| `scene_restore` | `project`, `version` | Cofa scenę do wersji z historii (obecna trafia do historii). (zmienia pliki) |

### Wiedza dla agenta

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `knowledge_get` | `topic` | Zasady: kontrakt strony, deterministyczny GSAP, pętla pracy, kody znalezisk, ruch, wizualia, marka. |

### Podgląd klatek i osi czasu

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `frames_view` | `project`, `times`, `width`? | Klatki filmu w podanych chwilach (obraz dla agenta i dashboardu): tak oceniasz kompozycję. (obrazy) |
| `filmstrip` | `project`, `count`? | Równomierny przekrój całego filmu (do 12 klatek) jednym obrazem. (obrazy) |
| `timeline_get` | `project`, `step`? | Zdarzenia dźwiękowe (EV) i przedziały, w których widać poszczególne teksty (z boksami). |

### Nadzór jakości

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `check_run` | `project`, `depth`? | Runda nadzoru: błędy, klatki, pętla, determinizm, czytelność, kontrast. Zwraca werdykt, znaleziska, delta i taśmę. (zmienia pliki) (obrazy) |
| `check_latest` | `project` | Zwraca ostatni raport bez uruchamiania nowej rundy. |
| `check_history` | `project` | Wynik i werdykt każdej rundy: widać, czy praca idzie do przodu. |
| `check_explain` | `code` | Co znaczy kod (np. NONDETERMINISTIC) i jak to naprawić. |

### Render, dźwięk, wydanie

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `render_start` | `project`, `final`?, `audio`?, `force`? | Uruchamia render jako job (draft w połowie rozdzielczości albo final). Zwraca job; postęp przez job_get/job_wait. (job) |
| `sound_start` | `project` | Buduje cue sheet z EV, miksuje do -14 LUFS i podkłada pod najnowszy render (job). (job) |
| `deliver_start` | `project`, `strict`? | QA pliku, plakat, paczka wydania i DELIVERY.md (job). (job) |
| `jobs_list` | `project`? | Ostatnie joby (render, dźwięk, wydanie) z postępem. |
| `job_get` | `job` | Status, postęp, wynik i ogon logu. |
| `job_wait` | `job`, `timeout`? | Blokuje do zakończenia joba albo do `timeout` s (maks. 600) i zwraca jego stan. |
| `job_cancel` | `job` | Przerywa działający job. (zmienia pliki) |

### Zadania dla agenta

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `task_create` | `prompt`, `project`? | Zapisuje prośbę użytkownika dla agenta (dashboard: „poproś agenta”). (zmienia pliki) |
| `task_list` | `status`? | Zadania dla agenta (open, in_progress, done, blocked). |
| `task_next` | - | Najstarsze otwarte zadanie użytkownika z kontekstem projektu i instrukcją, co dalej. |
| `task_update` | `task`, `status`?, `note`? | Zmienia status (open, in_progress, done, blocked) i/lub dopisuje notatkę (np. świadomie zostawione ostrzeżenie). (zmienia pliki) |

### Środowisko i aktywność

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `doctor` | - | Python, FFmpeg, Playwright, Chromium, renderery, szablony: co działa, a czego brakuje. |
| `activity_tail` | `limit`?, `since`?, `source`? | Ostatnie wywołania operacji przez agenta, dashboard i joby. |
| `vendor_list` | - | Które zewnętrzne zasoby (np. GSAP z CDN) mają lokalną kopię do pracy offline. |
| `vendor_add` | `url`, `file`? | Zapisuje lokalną kopię URL-a (skrót: gsap); `file` = lokalny plik zamiast pobierania. (zmienia pliki) |
| `vendor_remove` | `url` | Usuwa lokalną kopię. (zmienia pliki) |
| `capabilities_list` | - | Pełna lista operacji studia: kategoria, parametry, czy zmienia pliki, czy to job. |

## Kody znalezisk nadzorcy

- `PAGE_ERROR`: Read the error text, fix the script error in src/index.html (undefined variable, typo, missing library), then re-run check. Nothing else is trustworthy until the page loads clean.
- `NET_FAILED`: An external resource (usually a CDN script such as GSAP) did not load. Call vendor_add for that URL (or pass a local file) so preview, checks and render work offline; the HTML itself stays unchanged.
- `NET_HTTP`: Fix the URL or vendor the resource with vendor_add.
- `CONSOLE_WARN`: Read the warning; in GSAP it often means an unsupported property or a missing plugin. Remove or replace it.
- `NO_SEEK`: Add window.seek = function (t) {...} that draws the frame for time t deterministically (for GSAP: tl.pause(); tl.totalTime(t % DUR)). See knowledge_get topic=contract.
- `NO_DURATION`: Set window.DURATION to the film length in seconds.
- `DURATION_MISMATCH`: Make window.DURATION equal to the project duration (or update the project) so the render is not cut or padded.
- `NO_TEXTS`: Expose window.TEXTS(t) returning every visible text with its pixel box so readability can be checked (see knowledge_get topic=contract).
- `NO_EV`: Expose window.EV = [{t, type}] (whoosh, hit, pop, click, chime) so sound can be generated from the scene.
- `BLANK_FRAMES`: A stretch of the film shows a flat, empty frame. Start something moving earlier, or shorten the gap. Short gaps at the very start or end of a loop are fine.
- `DEAD_TIME`: Nothing changes for too long. Add a slow push-in (about 0.25% per frame), a drift, or bring the next beat forward. Static holds over 1 s read as a frozen video.
- `NOT_LOOPING`: The last frame differs from the first, so a looping player will jump. Ease the end state back to the start state, or fade everything out at the end. Ignore if a hard reset is intended.
- `NONDETERMINISTIC`: The same time renders differently depending on what was drawn before. Remove Math.random, timers, CSS transitions, yoyo/repeat in tweens and overlapping tweens of one property; build state only from t.
- `HARD_CUT`: The picture changes abruptly between two samples. If this is meant to be a cut, fine; if the brief says one continuous motion, morph the object instead (size, radius, colour).
- `TEXT_READ`: Keep the text on screen at least characters/15 + 1.5 s, or shorten it. Do not animate text while it is being read.
- `OFF_FRAME`: Move or scale the element so its box stays inside the frame.
- `TEXT_MOVES`: Let the text stand still for at least 8 frames after it lands before it moves again.
- `LOW_CONTRAST`: Raise contrast to at least 3:1 for large text (4.5:1 for small): darken the background behind the text or change the text colour.
- `TEXT_TINY`: Increase the font size; on a phone, text under about 2.5% of the frame height is hard to read.
- `SAFE_ZONE`: Keep text out of the top 10% and bottom 20% of vertical video (Reels/Shorts/TikTok UI covers them) and 5% from the edges.
- `SEEK_FAILED`: Fix the error thrown by seek(t); the film cannot be sampled or rendered until it works for every t in [0, DURATION].
- `ENGINE_UNSUPPORTED`: Deep checks need the html engine (window.seek contract). Use still/render for this engine.

## Zasady pracy

- Patrz na klatki (`frames_view`), nie zgaduj z kodu: początek, główny moment, najszybsze przejście, koniec.
- Nie twierdź, że film jest gotowy bez werdyktu `pass` albo jawnej notatki o świadomie zostawionym ostrzeżeniu.
- Nie wymyślaj kolorów ani fontów: bierz z `knowledge_get topic=brand`.
- Edytuj sceny przez `scene_write` / `scene_patch` (zachowują historię, `scene_restore` cofa). Nie nadpisuj `src/index.html` inaczej.
- Po 6 rundach bez postępu zatrzymaj się i zapytaj użytkownika. Nic nie publikuj bez jego wyraźnej zgody.
