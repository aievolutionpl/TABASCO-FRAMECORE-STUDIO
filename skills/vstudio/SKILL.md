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

# Work loop (follow it; the supervisor and the director are your eyes)

1. `studio_status` first. If the studio is not onboarded, ask the user for brand, palette, font, tone and default format, then `profile_set`.
2. `task_next` returns what the user asked for in the dashboard. `task_update` -> in_progress.
3. DIRECT before you build: `project_create` (from the closest template or blank), then `director_plan` (goal, platform, tone). It picks a main style plus two
   accents with different layouts and returns a beat sheet with a visible change every 2-3 s. Read `knowledge_get topic=direction`, and `style_get` for each style used.
4. Build beat by beat: `scene_read`, then `scene_write` / `scene_patch` with `check: "quick"`. Fetch icons and stickers with `assets_search` / `assets_add` /
   `assets_generate` instead of leaving beats text-only.
5. LOOK at the film: `frames_view` at the opening, each beat, the fastest transition and the end. Judge hierarchy, spacing, cut-off text, stray shapes.
6. `check_run` (standard): technical correctness. Fix errors first, then warnings, then re-run; read `delta`. Repeat until `verdict: pass`.
   If a warning is intentional (e.g. a prompt demands a static hold), say so in `task_update` notes and keep it.
7. `director_review`: pacing, hook, variety, motion, text rendering. LOOK at the filmstrip and the rhythm chart it returns. Fix findings, re-run.
   Best: hand this step to the `vstudio-director` agent (fresh eyes, no edit tools). When the checklist honestly holds: `director_signoff` (approve true, notes of what you saw,
   accept: {CODE: reason} for warnings kept on purpose). Any later edit to the scene invalidates the sign-off.
8. Only now `render_start` (draft, then final once brief, visual_rules and stills are approved) and `deliver_start`: final render and delivery refuse to start without the
   director's sign-off for the current scene. Tell the user the film is ready only after that.
9. `task_update` -> done with a short note: what was made, which styles, which warnings remain and why.

Never report success without `pass` from the supervisor, an approved director sign-off and a note about warnings kept on purpose. After 6 rounds without progress, stop and
ask the user. Never overwrite a scene without `scene_write` (it keeps history; `scene_restore` undoes).

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
  Word-by-word captions that follow a voice add `caption: true` to their entry (`VS.captions.texts(t)` does it): they are only checked for staying inside
  the frame, not for reading time or holding still, because the viewer hears them. Never mark ordinary text as a caption.
- `window.__ALPHA__` (boolean, set by the renderer in overlay mode, see `render_start overlay`): true when the film is rendered as a transparent layer to be placed over
  the user's own footage. Hide full-bleed backdrops and the footage placeholder when it is set (or mark them `data-alpha="hide"`); keep cards, captions and effects.

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
| `profile_set` | `name`?, `palette`?, `font`?, `tone`?, `audience`?, `default_format`?, `fps`?, `auto_supervise`?, `require_director`? | Ustawia profil marki (częściowo). Uzupełnienie nazwy kończy onboarding. (zmienia pliki) |
| `agent_connect_info` | - | Polecenie MCP, fragment .mcp.json, ścieżki skilla i stan połączenia agenta. |
| `agent_selftest` | - | Uruchamia serwer MCP i robi handshake jak prawdziwy klient: dowód, że agent się połączy. |
| `agent_install` | `skill`?, `director`?, `mcp_config`?, `scope`? | Zapisuje skill (SKILL.md), subagenta `vstudio-director` (recenzent przed wysyłką) i wpis vstudio w .mcp.json. (zmienia pliki) |

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
| `scene_palette` | `project` | Kolory #RRGGBB użyte w scenie (liczność, jasność) i propozycja mapowania na kolory marki z profilu. |
| `scene_recolor` | `project`, `mapping`, `note`?, `check`? | Podmienia kolory #RRGGBB w całej scenie jednym przebiegiem (z historią). Z `check` od razu uruchamia nadzorcę. (zmienia pliki) (obrazy) |
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

### Reżyser: styl, plan i przegląd przed wysyłką

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `styles_list` | `platform`?, `energy_min`?, `query`? | 14 stylów (kinetyczna typografia, szkło, neo-brutalizm, luksus, retro, naklejki, dane, 3D...) z tonem, energią, platformami, plus przejścia i układy bitów. |
| `style_get` | `id` | Pełny opis jednego stylu: paleta, typografia, język ruchu, przejścia, zasady kompozycji i gotowa receptura CSS/GSAP. |
| `director_plan` | `project`, `goal`, `tone`?, `platform`?, `pace`?, `prefer`?, `avoid`?, `cta`?, `loop`?, `write_storyboard`?, `format`?, `items`? | Dobiera styl główny i dwa akcenty o różnych układach i układa storyboard: bity co 2-3 s (hak, rozwinięcie, dowód, CTA) ze stylem, układem, przejściem, dźwiękiem i hasłami do assetów. (zmienia pliki) |
| `director_review` | `project`, `depth`?, `platform`?, `pace`? | Mierzy film oczami widza: rytm (nowa sytuacja co 2-3 s), hak, różnorodność looków, ruch (przyspieszenia, stagger), widoczność i fonty tekstu (polskie znaki), obrazy, migotanie. Zwraca werdykt, znaleziska, taśmę klatek i wykres rytmu. (zmienia pliki) (obrazy) |
| `director_signoff` | `project`, `approve`, `notes`, `checklist`?, `accept`? | Świadome zatwierdzenie (albo odrzucenie) aktualnej wersji sceny po obejrzeniu klatek: checklista, notatka, zaakceptowane ostrzeżenia z powodem. Zmiana sceny unieważnia decyzję. (zmienia pliki) |
| `director_latest` | `project` | Ostatni raport reżysera bez uruchamiania nowego, stan zatwierdzenia (czy aktualny), zapisany plan i historia rund. |

### Assety: ikony, grafiki, napisy, zdjęcia

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `assets_search` | `query`, `source`?, `limit`? | Ikony i obrazy: wbudowane ikony SVG (offline), Iconify (ikony, licencja sprawdzana w API) albo Openverse (zdjęcia CC0/PD/CC-BY). Zwraca ref do assets_add. |
| `assets_add` | `project`, `ref`, `name`?, `color`? | Zapisuje ikonę lub obraz w src/assets/ (SVG oczyszczany, obraz zmniejszany i kodowany ponownie) ze śladem licencji i zwraca gotowy kod do sceny. (zmienia pliki) |
| `assets_generate` | `project`, `kind`, `seed`?, `colors`?, `name`?, `width`?, `height`? | Deterministyczna grafika SVG z ziarna w kolorach marki: blob, mesh (zorza), dots, grid, rings, waves, rays, confetti, grain, starburst, squiggle, arrow. (zmienia pliki) |
| `assets_list` | `project` | Pliki w src/assets/ z pochodzeniem i licencją oraz lista generatorów i liczba wbudowanych ikon. |
| `assets_snippet` | `project`, `file`, `mode`? | HTML do wklejenia w scenę: SVG inline (przemalowywalny przez `color`) albo <img> z relatywną ścieżką. |
| `captions_build` | `project`, `text`?, `srt`?, `words`?, `start`?, `end`?, `wpm`?, `style`?, `max_words`?, `highlight`?, `numbers`? | Z tekstu lektora, SRT/VTT albo znaczników słów buduje dane napisów (czasy słów, linie, podświetlenia) i zapisuje je razem z silnikiem w src/assets/. Zwraca kod do wklejenia w scenę. (zmienia pliki) |
| `motion_kit_add` | `project` | Zapisuje src/assets/motion-kit.js: sprężyny jako ease dla GSAP, mocne krzywe Béziera, licznik, pisanie znak po znaku i silnik napisów. Wszystko deterministyczne. (zmienia pliki) |
| `assets_remove` | `project`, `file` | Usuwa plik z src/assets/ razem z wpisem w śladzie licencji. (zmienia pliki) |

### Render, dźwięk, wydanie

| Narzędzie | Parametry | Do czego |
| --- | --- | --- |
| `render_start` | `project`, `final`?, `audio`?, `overlay`?, `force`?, `skip_review`? | Uruchamia render jako job (draft w połowie rozdzielczości, final albo nakładka z przezroczystością). Zwraca job; postęp przez job_get/job_wait. (job) |
| `sound_start` | `project` | Buduje cue sheet z EV, miksuje do -14 LUFS i podkłada pod najnowszy render (job). (job) |
| `deliver_start` | `project`, `strict`?, `skip_review`? | QA pliku, plakat, paczka wydania i DELIVERY.md (job). (job) |
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

## Reżyser: film ma być ładny, dynamiczny i sprawdzony zanim trafi do użytkownika

Nadzorca (`check_run`) odpowiada za poprawność techniczną. **Reżyser** odpowiada za to, co widzi widz: plan stylu i storyboard
(`director_plan`), przegląd rytmu, haka, różnorodności, ruchu, widoczności tekstu i fontów (`director_review`) oraz zatwierdzenie
(`director_signoff`). Finalny render i wydanie **nie wystartują** bez zatwierdzenia aktualnej wersji sceny. Najlepiej oddaj przegląd
subagentowi `vstudio-director` (świeże oczy, bez narzędzi do edycji). Assety (ikony, grafiki, obrazy) bierz z `assets_search` / `assets_add` /
`assets_generate`. Zasady rzemiosła: `knowledge_get topic=direction`, style: `topic=styles`, assety: `topic=assets`.

# The director's craft (read before building; director_review measures it)

A film that is technically correct can still be boring. You are the director: decide what the viewer sees every 2-3 seconds.

1. Hook, 0-1.5 s. Frame 1 is the thumbnail. Something moves or a bold line is on screen by 1 s: the promise in at most 6 words. Never open on a logo or a fade from black.
2. Rhythm. A visibly NEW situation every 2-3 s on reels/tiktok/shorts (3.5 s on feed/linkedin, 5 s for calm explainers). "New" means layout, background, subject or camera
   changes, not a word swap. Let the CTA hold still for 1.5-2.5 s. WEAK_HOOK, SLOW_PACE and BEAT_MISSING measure this.
3. Variety inside a system. Constant: palette, font, tone, logo position. Variable per beat: layout, background treatment (dark / light / gradient / photo), motion
   language, transition, sound. `director_plan` picks a main style and two accents with different layouts. At least 2 looks in 7 s, 3 from 12 s, 4 from 20 s (MONOTONE_STYLE).
4. Motion with weight. Ease everything: expo.out or power3.out for entrances, power2.inOut for moves, back.out(1.4) for pops. Constant speed only for long drifts
   (LINEAR_MOTION). Stagger groups by 0.05-0.1 s (NO_STAGGER). Overlap the end of one move with the start of the next. Put a slow push-in or drift under static holds.
   One hero motion per beat.
5. Text. At most 6 words per beat and 2 sizes; the key word in the accent colour. Fully visible, never clipped (TEXT_CLIPPED), never hidden behind another layer (TEXT_HIDDEN),
   never colliding (TEXT_OVERLAP). Polish letters must come from the chosen font (GLYPH_MISSING): load latin-ext. Stay inside platform safe zones. Reading time is at least chars/15 + 1.5 s.
6. Assets. Pair every text-only beat with an icon, sticker or small image. One stroke weight and corner style across the film. Colour icons through CSS `color` so the
   brand palette applies. Prefer built-in icons and generated graphics (no licence questions); downloaded files get credits in DELIVERY.md automatically.
7. Sound. Every transition has a cue in EV: hit for cuts, whoosh for moves, pop for stickers, chime for success.
8. Restraint. If a beat has two ideas, split it. If an element does not help the message, remove it.

Review ritual: `director_review`, then LOOK at the filmstrip and the rhythm chart (green lines = new situations, red areas = gaps). Check each checklist item honestly.
A film you would scroll past is not approved.

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
- `TEXTS_FAILED`: Fix the error thrown by window.TEXTS(t) (usually a selector that no longer exists or a read of an element before it is created). Reading time, framing and contrast cannot be checked until it works for every t.
- `SEEK_FAILED`: Fix the error thrown by seek(t); the film cannot be sampled or rendered until it works for every t in [0, DURATION].
- `ENGINE_UNSUPPORTED`: Deep checks need the html engine (window.seek contract). Use still/render for this engine.

## Kody znalezisk reżysera

- `SLOW_PACE`: Nothing visibly new happens for too long. Add a beat inside the gap: swap the layout, change the background treatment, bring in a new element with a different transition (knowledge_get topic=styles lists them). Aim for a visible change every 2-3 s on social; a calm hold is fine only when the brief asks for it (then accept the warning with a reason).
- `MONOTONE_STYLE`: The whole film shares one look. Keep brand colours and font, but change the TREATMENT between beats: layout, background (dark / light / gradient), motion language, transition. Run director_plan to pick a main style plus two accents with different layouts.
- `WEAK_HOOK`: Nothing grabs attention in the first 1.5 s. Open with motion or a bold line in frame 1, put the key promise on screen by 1 s, and save the logo or product reveal for the end.
- `NO_HOOK_TEXT`: Most viewers watch muted: state the point in words (max 6) by 1 s, or open on a striking visual that carries it on its own.
- `FLASH_RISK`: The frame flashes light and dark more than 3 times per second, which can harm photosensitive viewers and reads as a glitch. Reduce to at most 2 flashes per second and lower the contrast of each flash.
- `LINEAR_MOTION`: Most moves run at constant speed, which looks mechanical. Use eases: expo.out or power3.out for entrances, power2.inOut for moves, back.out(1.4) for pops. Keep ease none for long drifts only.
- `NO_STAGGER`: Several elements enter on the same frame. Offset them by 0.05-0.1 s (stagger) so the eye can follow the order.
- `TEXT_CLIPPED`: The text is cut off by a container (overflow hidden) or by the frame. Enlarge the container, reduce the font size or shorten the copy. Check long Polish words.
- `TEXT_TRUNCATED`: text-overflow: ellipsis is cutting the copy. Remove it, shorten the text or widen the box.
- `TEXT_HIDDEN`: The DOM says the text is shown, but the pixels do not change when it is hidden: it is covered by another element, has the same colour as its background, or is clipped away. Raise its z-index, change its colour or remove the cover.
- `TEXT_OVERLAP`: Two different texts overlap. Move them apart, stagger their timing so one leaves before the other lands, or reduce their size.
- `TEXT_WALL`: More than about 28 words are on screen at once. Social video is read in under 2 s per beat: keep to 6 words per beat or split the beat in two.
- `TEXTS_INCOMPLETE`: Some visible texts are not reported by window.TEXTS(t), so reading time, framing and contrast are not checked for them. Make TEXTS read the DOM (every visible text node with its Range rect and opacity).
- `GLYPH_MISSING`: Some characters are not drawn by the chosen font (they fall back to another font or show as boxes). For Polish load the font with the latin-ext subset or pick a font that covers ąćęłńóśźż, then run director_review again.
- `FONT_FALLBACK`: The first font in the stack is not loaded, so the page falls back to another font and renders differently than designed (and differently on other machines). Bundle the font next to the scene with @font-face (src: url(assets/font.woff2)) or choose a system font stack.
- `ASSET_BROKEN`: An <img> failed to load (wrong path, 404 or unsupported file). Add images with assets_add and use the returned snippet; files live in src/assets/ and are referenced as assets/<file>.
- `NO_VISUAL_ASSETS`: The film has no icons, illustrations or images. Add 3-6 icons or stickers where text carries the message (assets_search, then assets_add) to make beats more visual.
- `BEAT_MISSING`: The storyboard (director_plan) puts a new beat here, but nothing visibly changes in the film. Build the beat or update the plan.
- `PLAN_STALE`: The saved plan has a different duration than the film. Run director_plan again.

## Zasady pracy

- Patrz na klatki (`frames_view`), nie zgaduj z kodu: początek, główny moment, najszybsze przejście, koniec.
- Nie twierdź, że film jest gotowy bez werdyktu `pass`, zatwierdzenia reżysera (`director_signoff`) i jawnej notatki o świadomie zostawionych ostrzeżeniach.
- Nie zostawiaj bitów samego tekstu: dodaj ikonę, naklejkę albo grafikę (`assets_search`, `assets_generate`). Zmieniaj wygląd co 2-3 s, marka zostaje stała.
- Nie wymyślaj kolorów ani fontów: bierz z `knowledge_get topic=brand`.
- Edytuj sceny przez `scene_write` / `scene_patch` (zachowują historię, `scene_restore` cofa). Nie nadpisuj `src/index.html` inaczej.
- Po 6 rundach bez postępu zatrzymaj się i zapytaj użytkownika. Nic nie publikuj bez jego wyraźnej zgody.
