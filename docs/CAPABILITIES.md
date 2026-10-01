# Mapa możliwości vstudio

> Plik generowany z rejestru możliwości (`vstudio/registry.py`, operacje w `vstudio/ops.py`). Nie edytuj ręcznie: `python vstudio.py tools --write-docs`.

Studio ma **57 operacji** w 12 kategoriach. Każda z nich jest dostępna tą samą drogą z trzech powierzchni, bo wszystkie czytają jeden rejestr:

| Powierzchnia | Jak | Dla kogo |
| --- | --- | --- |
| **Serwer MCP** | `python vstudio.py mcp` (stdio): narzędzia, zasoby, prompty | agent (Claude Code i inne klienty MCP) |
| **Dashboard** | `python vstudio.py dashboard`: API `POST /api/call/<operacja>` | człowiek (interfejs w przeglądarce) |
| **CLI** | `python vstudio.py check / tools / skill / vendor / onboard` (+ dotychczasowe komendy potoku) | skrypty, CI |

```
agent (MCP)  ─┐
dashboard    ─┼─►  registry.call(operacja, args) ─► ops ─► workspace / supervisor / jobs / vendor ─► projekt na dysku
CLI          ─┘            │
                           └─► activity.jsonl  (feed „co robi agent” w dashboardzie)
```

Legenda: **zmienia pliki** = modyfikuje stan na dysku; **job** = długa operacja w tle (postęp przez `job_get`/`job_wait`); **obrazy** = wynik zawiera klatki, które MCP oddaje agentowi jako obrazy.

## Start i połączenie agenta

### `studio_status`: Stan studia

Jedno wywołanie: środowisko, profil marki, agent, projekty, zadania i co zrobić dalej.

**Kiedy:** Call this FIRST in every session to learn what to do next.

**Zwraca:** ready, onboarded, doctor, agent, projects, open_tasks, vendor, next[]

_brak parametrów_

### `profile_get`: Profil marki

Nazwa, paleta, font, ton, odbiorcy i domyślny format użytkownika.

**Kiedy:** Before designing anything: use the brand values, do not invent colours or fonts.

**Zwraca:** profile

_brak parametrów_

### `profile_set`: Zapisz profil marki

Ustawia profil marki (częściowo). Uzupełnienie nazwy kończy onboarding.

**Kiedy:** During onboarding, after asking the user for their brand.

**Zwraca:** profile

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `name` | string | nie |  |
| `palette` | object | nie | bg, ink, accent, accent2 as #RRGGBB |
| `font` | string | nie |  |
| `tone` | string | nie |  |
| `audience` | string | nie |  |
| `default_format` | string (9:16 \| 4:5 \| 1:1 \| 16:9) | nie |  |
| `fps` | integer | nie |  |
| `auto_supervise` | boolean | nie | run a quick supervisor check in the background whenever a scene changes on disk (dashboard) |
| `require_director` | boolean | nie | final render and delivery need the director's sign-off for the current scene (default true) |

### `agent_connect_info`: Jak podłączyć agenta

Polecenie MCP, fragment .mcp.json, ścieżki skilla i stan połączenia agenta.

**Zwraca:** command, claude_code, mcp_json, skill, agent

_brak parametrów_

### `agent_selftest`: Test połączenia agenta

Uruchamia serwer MCP i robi handshake jak prawdziwy klient: dowód, że agent się połączy.

**Zwraca:** ok, server, protocol, tools, ms

_brak parametrów_

### `agent_install`: Zainstaluj skill, agenta-recenzenta i konfigurację MCP

Zapisuje skill (SKILL.md), subagenta `vstudio-director` (recenzent przed wysyłką) i wpis vstudio w .mcp.json.

**Zwraca:** installed{skill, director_agent, mcp_config}

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `skill` | boolean | nie | Domyślnie: `True`. |
| `director` | boolean | nie | install the vstudio-director reviewer subagent Domyślnie: `True`. |
| `mcp_config` | boolean | nie | Domyślnie: `True`. |
| `scope` | string (project \| user) | nie | Domyślnie: `project`. |

## Biblioteka szablonów

### `templates_list`: Szablony

Katalog szablonów: opis, technika, format, czas, tagi i czy wymagają sieci.

**Kiedy:** When starting a new film: pick the closest template instead of writing from scratch.

**Zwraca:** templates[]

_brak parametrów_

### `project_create`: Nowy projekt

Tworzy projekt (opcjonalnie z szablonu) z briefem; format z szablonu lub profilu marki.

**Zwraca:** project summary (id, size, gates, next)

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `slug` | string | tak | short-kebab-name |
| `brand` | string | nie | defaults to the profile name |
| `template` | string | nie | template id from templates_list |
| `format` | string (9:16 \| 4:5 \| 1:1 \| 16:9) | nie |  |
| `size` | string | nie | WxH, overrides format |
| `fps` | integer | nie |  |
| `duration` | number | nie |  |
| `brief` | string | nie | what the film is for; written into BRIEF.md |

## Projekty i bramki jakości

### `projects_list`: Projekty

Wszystkie projekty z postępem bramek, następnym krokiem i wynikiem ostatniego nadzoru.

**Zwraca:** projects[]

_brak parametrów_

### `project_get`: Szczegóły projektu

Bramki, rendery, zadania, pokrycie vendorem i podsumowanie nadzoru jednego projektu.

**Zwraca:** project (status, gates, renders, vendor, tasks)

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `gate_set`: Bramka jakości

Zatwierdza/resetuje bramkę (brief, visual_rules, stills, draft, sound, critic, final) albo ustawia wynik krytyka.

**Kiedy:** Approve a gate only when the work is genuinely done; final render is blocked until brief, visual_rules and stills are approved.

**Zwraca:** message, next

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `action` | string (approve \| reset \| score) | tak |  |
| `gate` | string (brief \| reference_spec \| visual_rules \| stills \| draft \| sound \| critic \| final) | nie |  |
| `score` | number | nie |  |

## Scena (kod filmu)

### `scene_read`: Czytaj scenę

Kod sceny (src/index.html) z informacją o haczykach kontraktu i zasobach z sieci.

**Kiedy:** Before editing: read the current scene.

**Zwraca:** content, range, lines, hooks, vendor

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `start_line` | integer | nie |  |
| `end_line` | integer | nie |  |

### `scene_write`: Zapisz scenę

Zapisuje całą scenę (z kopią w historii). Z `check` od razu uruchamia nadzorcę i zwraca werdykt.

**Kiedy:** Write the whole scene. For small changes prefer scene_patch.

**Zwraca:** bytes, lines, backup, check?

**Cechy:** zmienia pliki, obrazy

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `content` | string | tak | full HTML of the scene |
| `note` | string | nie |  |
| `check` | string (quick \| standard \| deep) | nie | Run the supervisor after the change and attach its verdict. |

### `scene_patch`: Popraw fragment sceny

Zamienia dokładne fragmenty tekstu (każdy musi wystąpić raz, chyba że all=true). Atomowo, z historią.

**Kiedy:** Small fixes after a finding: cheaper and safer than rewriting the scene.

**Zwraca:** applied[], backup, check?

**Cechy:** zmienia pliki, obrazy

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `edits` | array | tak | [{find, replace, all?}]; find must match exactly once |
| `note` | string | nie |  |
| `check` | string (quick \| standard \| deep) | nie | Run the supervisor after the change and attach its verdict. |

### `scene_palette`: Paleta sceny

Kolory #RRGGBB użyte w scenie (liczność, jasność) i propozycja mapowania na kolory marki z profilu.

**Kiedy:** Before restyling a template: see which colours it uses, then apply the brand with scene_recolor instead of editing hex values by hand.

**Zwraca:** colors[], brand, suggestion[]

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `scene_recolor`: Zmień kolory sceny

Podmienia kolory #RRGGBB w całej scenie jednym przebiegiem (z historią). Z `check` od razu uruchamia nadzorcę.

**Kiedy:** Apply the brand palette (see `suggestion` in scene_palette) or change one colour everywhere. Contrast is re-checked by the supervisor.

**Zwraca:** replaced{hex: n}, not_found[], check?

**Cechy:** zmienia pliki, obrazy

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `mapping` | object | tak | {"#OLD": "#NEW", ...}, each #RRGGBB |
| `note` | string | nie |  |
| `check` | string (quick \| standard \| deep) | nie | Run the supervisor after the change and attach its verdict. |

### `scene_history`: Historia sceny

Ostatnie wersje sceny (do 30) z notatkami.

**Zwraca:** versions[]

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `scene_restore`: Przywróć wersję sceny

Cofa scenę do wersji z historii (obecna trafia do historii).

**Zwraca:** restored, backup

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `version` | string | tak | file name from scene_history |

## Wiedza dla agenta

### `knowledge_get`: Wiedza

Zasady: kontrakt strony, deterministyczny GSAP, pętla pracy, kody znalezisk, ruch, wizualia, marka.

**Kiedy:** Read `gsap` and `contract` before writing a scene, `brand` before choosing colours, `findings` when the supervisor reports a code.

**Zwraca:** text

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `topic` | string (contract \| direction \| styles \| formats \| assets \| gsap \| workflow \| findings \| feel \| motion \| visual \| brand) | tak |  |

## Podgląd klatek i osi czasu

### `frames_view`: Zobacz klatki

Klatki filmu w podanych chwilach (obraz dla agenta i dashboardu): tak oceniasz kompozycję.

**Kiedy:** After every meaningful change: look at the opening, the main beat, the fastest transition and the end.

**Zwraca:** images (frames or a labelled sheet)

**Cechy:** obrazy

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `times` | array | tak | seconds, up to 12 |
| `width` | integer | nie | Domyślnie: `720`. |

### `filmstrip`: Taśma filmowa

Równomierny przekrój całego filmu (do 12 klatek) jednym obrazem.

**Zwraca:** image

**Cechy:** obrazy

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `count` | integer | nie | Domyślnie: `8`. |

### `timeline_get`: Mapa czasu

Zdarzenia dźwiękowe (EV) i przedziały, w których widać poszczególne teksty (z boksami).

**Zwraca:** duration, events[], texts[]

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `step` | number | nie | Domyślnie: `0.1`. |

## Nadzór jakości

### `check_run`: Sprawdź film (nadzór)

Runda nadzoru: błędy, klatki, pętla, determinizm, czytelność, kontrast. Zwraca werdykt, znaleziska, delta i taśmę.

**Kiedy:** After every edit. Loop until verdict is `pass`; fix errors first, then warnings. Read `delta` to see progress.

**Zwraca:** verdict, score, findings[], delta, next_actions[], images

**Cechy:** zmienia pliki, obrazy

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `depth` | string (quick \| standard \| deep) | nie | Domyślnie: `standard`. |

### `check_latest`: Ostatni raport nadzoru

Zwraca ostatni raport bez uruchamiania nowej rundy.

**Zwraca:** report or null

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `check_history`: Historia rund nadzoru

Wynik i werdykt każdej rundy: widać, czy praca idzie do przodu.

**Zwraca:** rounds[]

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `check_explain`: Wyjaśnij kod znaleziska

Co znaczy kod (np. NONDETERMINISTIC) i jak to naprawić.

**Zwraca:** title, fix

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `code` | string | tak |  |

## Reżyser: styl, plan i przegląd przed wysyłką

### `styles_list`: Biblioteka stylów

14 stylów (kinetyczna typografia, szkło, neo-brutalizm, luksus, retro, naklejki, dane, 3D...) z tonem, energią, platformami, plus przejścia i układy bitów.

**Kiedy:** Before building a film: pick styles by goal and tone; mix a main style with two accents.

**Zwraca:** styles[], transitions[], layouts{}

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `platform` | string (reels \| tiktok \| shorts \| story \| feed \| linkedin \| web \| presentation) | nie |  |
| `energy_min` | integer | nie |  |
| `query` | string | nie | word from the name, tone or goal (English or Polish) |

### `style_get`: Opis stylu

Pełny opis jednego stylu: paleta, typografia, język ruchu, przejścia, zasady kompozycji i gotowa receptura CSS/GSAP.

**Kiedy:** After director_plan: read the recipe of every style used in the storyboard before writing the scene.

**Zwraca:** style, text

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `id` | string (kinetic-type \| glass-ui \| neo-brutal \| swiss-minimal \| dark-luxe \| retro-synth \| sticker-pop \| gradient-mesh \| isometric-3d \| data-story \| paper-cut \| cinematic-captions \| terminal-code \| pastel-soft \| creator-captions \| tool-showcase) | tak |  |

### `director_plan`: Plan reżyserski

Dobiera styl główny i dwa akcenty o różnych układach i układa storyboard: bity co 2-3 s (hak, rozwinięcie, dowód, CTA) ze stylem, układem, przejściem, dźwiękiem i hasłami do assetów.

**Kiedy:** BEFORE building the scene: the plan is what director_review later checks the film against.

**Zwraca:** styles{main, accents, why}, beats[], contract, brand, format, warnings[]

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `goal` | string | tak | what the film is about and what the viewer should do |
| `tone` | string | nie | e.g. premium, playful, techy (adds to the brand tone) |
| `platform` | string (reels \| tiktok \| shorts \| story \| feed \| linkedin \| web \| presentation) | nie | reels, tiktok, shorts, story (fast), feed, linkedin (standard), web, presentation (calm). Default: from the project format. |
| `pace` | string (fast \| standard \| calm) | nie |  |
| `prefer` | array | nie | style ids to favour |
| `avoid` | array | nie | style ids to exclude |
| `cta` | string | nie | the call to action line |
| `loop` | boolean | nie | Domyślnie: `False`. |
| `write_storyboard` | boolean | nie | also write STORYBOARD.md (the previous one is kept as STORYBOARD.previous.md) Domyślnie: `False`. |
| `format` | string (tool-drop \| talking-head \| listicle) | nie | reel format with a proven beat sheet: tool-drop (recommend a free tool), talking-head (captions over footage), listicle (N things) |
| `items` | integer | nie | number of items for the listicle format Domyślnie: `3`. |

### `director_review`: Przegląd reżysera

Mierzy film oczami widza: rytm (nowa sytuacja co 2-3 s), hak, różnorodność looków, ruch (przyspieszenia, stagger), widoczność i fonty tekstu (polskie znaki), obrazy, migotanie. Zwraca werdykt, znaleziska, taśmę klatek i wykres rytmu.

**Kiedy:** Before telling the user a film is ready, and before the final render: LOOK at the returned images, fix findings, re-run, then director_signoff.

**Zwraca:** verdict, score, findings[], metrics, state, checklist, images (filmstrip, rhythm chart, evidence)

**Cechy:** zmienia pliki, obrazy

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `depth` | string (quick \| standard \| deep) | nie | Domyślnie: `standard`. |
| `platform` | string (reels \| tiktok \| shorts \| story \| feed \| linkedin \| web \| presentation) | nie | reels, tiktok, shorts, story (fast), feed, linkedin (standard), web, presentation (calm). Default: from the project format. |
| `pace` | string (fast \| standard \| calm) | nie |  |

### `director_signoff`: Zatwierdzenie reżysera

Świadome zatwierdzenie (albo odrzucenie) aktualnej wersji sceny po obejrzeniu klatek: checklista, notatka, zaakceptowane ostrzeżenia z powodem. Zmiana sceny unieważnia decyzję.

**Kiedy:** After director_review, once you have looked at the frames. Final render and delivery refuse to start without an approved sign-off for the current scene.

**Zwraca:** state, record

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `approve` | boolean | tak |  |
| `notes` | string | tak | 1-2 sentences: what you saw in the frames (min 12 characters) |
| `checklist` | object | nie | {"hook": true, "text": true, "rhythm": true, "style": true, "motion": true, "assets": true}; all must be true to approve |
| `accept` | object | nie | {CODE: reason} for warnings kept on purpose (errors cannot be accepted) |

### `director_latest`: Ostatni przegląd reżysera

Ostatni raport reżysera bez uruchamiania nowego, stan zatwierdzenia (czy aktualny), zapisany plan i historia rund.

**Zwraca:** review|null, state, plan|null, history[]

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

## Assety: ikony, grafiki, napisy, zdjęcia

### `assets_search`: Szukaj assetów

Ikony i obrazy: wbudowane ikony SVG (offline), Iconify (ikony, licencja sprawdzana w API) albo Openverse (zdjęcia CC0/PD/CC-BY). Zwraca ref do assets_add.

**Kiedy:** Where a beat is only text: find an icon or sticker for it. Start with builtin (offline); use iconify/openverse when you need more (needs internet).

**Zwraca:** results[] {id (ref), name, license, attribution, preview}

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `query` | string | tak | English or Polish word, e.g. cart, koszyk, rocket |
| `source` | string (builtin \| iconify \| openverse) | nie | Domyślnie: `builtin`. |
| `limit` | integer | nie | Domyślnie: `12`. |

### `assets_add`: Dodaj asset do projektu

Zapisuje ikonę lub obraz w src/assets/ (SVG oczyszczany, obraz zmniejszany i kodowany ponownie) ze śladem licencji i zwraca gotowy kod do sceny.

**Kiedy:** After assets_search. Paste snippet.html into the scene; images load from assets/<file>. Downloads are checked (https only, public hosts, size and type limits).

**Zwraca:** file, rel, license, snippet{html, note}

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `ref` | string | tak | builtin:<id> | iconify:<set>:<name> | openverse:<id> (from assets_search) | https URL |
| `name` | string | nie | file name without extension |
| `color` | string | nie | #RRGGBB or currentColor (default; recolour by CSS `color`) |

### `assets_generate`: Wygeneruj grafikę

Deterministyczna grafika SVG z ziarna w kolorach marki: blob, mesh (zorza), dots, grid, rings, waves, rays, confetti, grain, starburst, squiggle, arrow.

**Kiedy:** For backgrounds, textures, stickers and doodles that match the brand: no licence questions, no network.

**Zwraca:** file, rel, snippet

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `kind` | string (blob \| mesh \| dots \| grid \| rings \| waves \| rays \| confetti \| grain \| starburst \| squiggle \| arrow) | tak |  |
| `seed` | integer | nie | Domyślnie: `1`. |
| `colors` | array | nie | #RRGGBB list; default: brand accent, accent2, ink, bg (mesh uses the last as background) |
| `name` | string | nie |  |
| `width` | integer | nie |  |
| `height` | integer | nie |  |

### `assets_list`: Assety projektu

Pliki w src/assets/ z pochodzeniem i licencją oraz lista generatorów i liczba wbudowanych ikon.

**Zwraca:** assets[], generators[], builtin_icons

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `assets_snippet`: Kod assetu do sceny

HTML do wklejenia w scenę: SVG inline (przemalowywalny przez `color`) albo <img> z relatywną ścieżką.

**Zwraca:** mode, html, note

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `file` | string | tak |  |
| `mode` | string (auto \| inline \| img) | nie | Domyślnie: `auto`. |

### `captions_build`: Napisy słowo po słowie

Z tekstu lektora, SRT/VTT albo znaczników słów buduje dane napisów (czasy słów, linie, podświetlenia) i zapisuje je razem z silnikiem w src/assets/. Zwraca kod do wklejenia w scenę.

**Kiedy:** For talking-head and tool-drop reels: captions that appear with the voice. Give exact timings (srt/words) when you have them.

**Zwraca:** file, lines, words, start, end, preview[], snippet

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `text` | string | nie | the spoken script; word times are estimated (use srt or words for exact timing) |
| `srt` | string | nie | SRT or VTT text with cue timings; words are spread inside each cue |
| `words` | array | nie | [{t0, t1, w}] word timestamps (e.g. from a transcription tool) |
| `start` | number | nie | seconds: where the script starts in the film (text and srt) Domyślnie: `0`. |
| `end` | number | nie | seconds: where the script ends (text); default from wpm |
| `wpm` | number | nie | speaking pace used when end is not given Domyślnie: `150`. |
| `style` | string (single \| pop \| karaoke) | nie | single: one big word at a time | pop: words pop in, line stays | karaoke: whole line, active word highlighted Domyślnie: `single`. |
| `max_words` | integer | nie | words per line (default 1 for single, 3 otherwise) |
| `highlight` | array | nie | key words shown in the highlight colour |
| `numbers` | boolean | nie | highlight words with digits Domyślnie: `True`. |

### `motion_kit_add`: Zestaw ruchu (sprężyny, krzywe)

Zapisuje src/assets/motion-kit.js: sprężyny jako ease dla GSAP, mocne krzywe Béziera, licznik, pisanie znak po znaku i silnik napisów. Wszystko deterministyczne.

**Kiedy:** Before writing motion that should feel physical: springs and strong ease-out curves instead of linear or default eases.

**Zwraca:** file, usage

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `assets_remove`: Usuń asset

Usuwa plik z src/assets/ razem z wpisem w śladzie licencji.

**Zwraca:** removed

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `file` | string | tak |  |

## Render, dźwięk, wydanie

### `render_start`: Render

Uruchamia render jako job (draft w połowie rozdzielczości, final albo nakładka z przezroczystością). Zwraca job; postęp przez job_get/job_wait.

**Kiedy:** Render a draft after the supervisor says pass; final only after brief, visual_rules and stills are approved AND the director signed off this version of the scene.

**Zwraca:** job, warnings[]

**Cechy:** job

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `final` | boolean | nie | Domyślnie: `False`. |
| `audio` | string | nie | path to a mixed audio file |
| `overlay` | boolean | nie | transparent ProRes 4444 .mov of the animated layers only (no backdrop, no audio, full size) to lay over the user's own footage; mark full-bleed backdrops with data-alpha="hide" or branch on window.__ALPHA__ Domyślnie: `False`. |
| `force` | boolean | nie | skip the gate check for a final render Domyślnie: `False`. |
| `skip_review` | boolean | nie | skip the director sign-off requirement (only when the user explicitly asks) Domyślnie: `False`. |

### `sound_start`: Dźwięk

Buduje cue sheet z EV, miksuje do -14 LUFS i podkłada pod najnowszy render (job).

**Zwraca:** job

**Cechy:** job

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `deliver_start`: Wydanie

QA pliku, plakat, paczka wydania i DELIVERY.md (job).

**Kiedy:** Only after director_signoff approved the current scene: delivery refuses to start otherwise.

**Zwraca:** job, warnings[]

**Cechy:** job

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `strict` | boolean | nie | Domyślnie: `False`. |
| `skip_review` | boolean | nie | skip the director sign-off requirement (only when the user explicitly asks) Domyślnie: `False`. |

### `jobs_list`: Joby

Ostatnie joby (render, dźwięk, wydanie) z postępem.

**Zwraca:** jobs[]

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | nie | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `job_get`: Stan joba

Status, postęp, wynik i ogon logu.

**Zwraca:** job, log

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `job` | string | tak |  |

### `job_wait`: Czekaj na job

Blokuje do zakończenia joba albo do `timeout` s (maks. 600) i zwraca jego stan.

**Kiedy:** After render_start: call repeatedly until status is done/failed.

**Zwraca:** job, log

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `job` | string | tak |  |
| `timeout` | number | nie | Domyślnie: `60`. |

### `job_cancel`: Anuluj job

Przerywa działający job.

**Zwraca:** job

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `job` | string | tak |  |

## Zadania dla agenta

### `task_create`: Zadanie dla agenta

Zapisuje prośbę użytkownika dla agenta (dashboard: „poproś agenta”).

**Zwraca:** task

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `prompt` | string | tak |  |
| `project` | string | nie | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `task_list`: Lista zadań

Zadania dla agenta (open, in_progress, done, blocked).

**Zwraca:** tasks[]

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `status` | string (open \| in_progress \| done \| blocked) | nie |  |

### `task_next`: Następne zadanie

Najstarsze otwarte zadanie użytkownika z kontekstem projektu i instrukcją, co dalej.

**Kiedy:** After studio_status: pick up what the user asked for in the dashboard.

**Zwraca:** task or null, guide

_brak parametrów_

### `task_update`: Aktualizuj zadanie

Zmienia status (open, in_progress, done, blocked) i/lub dopisuje notatkę (np. świadomie zostawione ostrzeżenie).

**Zwraca:** task

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `task` | string | tak |  |
| `status` | string (open \| in_progress \| done \| blocked) | nie |  |
| `note` | string | nie |  |

## Środowisko i aktywność

### `doctor`: Diagnostyka środowiska

Python, FFmpeg, Playwright, Chromium, renderery, szablony: co działa, a czego brakuje.

**Zwraca:** ok, checks[]

_brak parametrów_

### `activity_tail`: Aktywność

Ostatnie wywołania operacji przez agenta, dashboard i joby.

**Zwraca:** events[], agent

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `limit` | integer | nie | Domyślnie: `40`. |
| `since` | integer | nie | event id, only newer |
| `source` | string (mcp \| dashboard \| api \| cli) | nie |  |

### `vendor_list`: Lokalne kopie bibliotek

Które zewnętrzne zasoby (np. GSAP z CDN) mają lokalną kopię do pracy offline.

**Zwraca:** items[]

_brak parametrów_

### `vendor_add`: Dodaj kopię biblioteki

Zapisuje lokalną kopię URL-a (skrót: gsap); `file` = lokalny plik zamiast pobierania.

**Kiedy:** When a check reports NET_FAILED for a CDN script, or before working offline.

**Zwraca:** url, file, bytes

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `url` | string | tak | https URL or alias (gsap) |
| `file` | string | nie | local file to copy instead of downloading |

### `vendor_remove`: Usuń kopię biblioteki

Usuwa lokalną kopię.

**Zwraca:** removed

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `url` | string | tak |  |

### `capabilities_list`: Mapa możliwości

Pełna lista operacji studia: kategoria, parametry, czy zmienia pliki, czy to job.

**Zwraca:** categories[], capabilities[]

_brak parametrów_

## Kody znalezisk nadzorcy

| Kod | Znaczenie | Jak naprawić (wskazówka dla agenta) |
| --- | --- | --- |
| `PAGE_ERROR` | Błąd JavaScript na stronie | Read the error text, fix the script error in src/index.html (undefined variable, typo, missing library), then re-run check. Nothing else is trustworthy until the page loads clean. |
| `NET_FAILED` | Nie załadował się zasób z sieci | An external resource (usually a CDN script such as GSAP) did not load. Call vendor_add for that URL (or pass a local file) so preview, checks and render work offline; the HTML itself stays unchanged. |
| `NET_HTTP` | Zasób zwrócił błąd HTTP | Fix the URL or vendor the resource with vendor_add. |
| `CONSOLE_WARN` | Ostrzeżenie w konsoli strony | Read the warning; in GSAP it often means an unsupported property or a missing plugin. Remove or replace it. |
| `NO_SEEK` | Strona nie wystawia window.seek(t) | Add window.seek = function (t) {...} that draws the frame for time t deterministically (for GSAP: tl.pause(); tl.totalTime(t % DUR)). See knowledge_get topic=contract. |
| `NO_DURATION` | Brak window.DURATION | Set window.DURATION to the film length in seconds. |
| `DURATION_MISMATCH` | DURATION różni się od projektu | Make window.DURATION equal to the project duration (or update the project) so the render is not cut or padded. |
| `NO_TEXTS` | Brak window.TEXTS(t) | Expose window.TEXTS(t) returning every visible text with its pixel box so readability can be checked (see knowledge_get topic=contract). |
| `NO_EV` | Brak window.EV | Expose window.EV = [{t, type}] (whoosh, hit, pop, click, chime) so sound can be generated from the scene. |
| `BLANK_FRAMES` | Puste klatki | A stretch of the film shows a flat, empty frame. Start something moving earlier, or shorten the gap. Short gaps at the very start or end of a loop are fine. |
| `DEAD_TIME` | Martwy czas: obraz stoi | Nothing changes for too long. Add a slow push-in (about 0.25% per frame), a drift, or bring the next beat forward. Static holds over 1 s read as a frozen video. |
| `NOT_LOOPING` | Pętla nie jest szczelna | The last frame differs from the first, so a looping player will jump. Ease the end state back to the start state, or fade everything out at the end. Ignore if a hard reset is intended. |
| `NONDETERMINISTIC` | Klatka zależy od historii | The same time renders differently depending on what was drawn before. Remove Math.random, timers, CSS transitions, yoyo/repeat in tweens and overlapping tweens of one property; build state only from t. |
| `HARD_CUT` | Twarde cięcie | The picture changes abruptly between two samples. If this is meant to be a cut, fine; if the brief says one continuous motion, morph the object instead (size, radius, colour). |
| `TEXT_READ` | Tekst za krótko na ekranie | Keep the text on screen at least characters/15 + 1.5 s, or shorten it. Do not animate text while it is being read. |
| `OFF_FRAME` | Tekst wychodzi poza kadr | Move or scale the element so its box stays inside the frame. |
| `TEXT_MOVES` | Tekst rusza się zbyt szybko po wylądowaniu | Let the text stand still for at least 8 frames after it lands before it moves again. |
| `LOW_CONTRAST` | Niski kontrast tekstu | Raise contrast to at least 3:1 for large text (4.5:1 for small): darken the background behind the text or change the text colour. |
| `TEXT_TINY` | Tekst zbyt mały | Increase the font size; on a phone, text under about 2.5% of the frame height is hard to read. |
| `SAFE_ZONE` | Tekst w strefie interfejsu platformy | Keep text out of the top 10% and bottom 20% of vertical video (Reels/Shorts/TikTok UI covers them) and 5% from the edges. |
| `TEXTS_FAILED` | window.TEXTS rzuca wyjątek | Fix the error thrown by window.TEXTS(t) (usually a selector that no longer exists or a read of an element before it is created). Reading time, framing and contrast cannot be checked until it works for every t. |
| `SEEK_FAILED` | window.seek rzuca wyjątek | Fix the error thrown by seek(t); the film cannot be sampled or rendered until it works for every t in [0, DURATION]. |
| `ENGINE_UNSUPPORTED` | Silnik bez głębokich kontroli | Deep checks need the html engine (window.seek contract). Use still/render for this engine. |

## Kody znalezisk reżysera

| Kod | Znaczenie | Jak naprawić (wskazówka dla agenta) |
| --- | --- | --- |
| `SLOW_PACE` | Za długo bez zmiany wizualnej | Nothing visibly new happens for too long. Add a beat inside the gap: swap the layout, change the background treatment, bring in a new element with a different transition (knowledge_get topic=styles lists them). Aim for a visible change every 2-3 s on social; a calm hold is fine only when the brief asks for it (then accept the warning with a reason). |
| `MONOTONE_STYLE` | Film wygląda tak samo od początku do końca | The whole film shares one look. Keep brand colours and font, but change the TREATMENT between beats: layout, background (dark / light / gradient), motion language, transition. Run director_plan to pick a main style plus two accents with different layouts. |
| `WEAK_HOOK` | Słaby początek (hak) | Nothing grabs attention in the first 1.5 s. Open with motion or a bold line in frame 1, put the key promise on screen by 1 s, and save the logo or product reveal for the end. |
| `NO_HOOK_TEXT` | Brak tekstu w pierwszej sekundzie | Most viewers watch muted: state the point in words (max 6) by 1 s, or open on a striking visual that carries it on its own. |
| `FLASH_RISK` | Migotanie kadru | The frame flashes light and dark more than 3 times per second, which can harm photosensitive viewers and reads as a glitch. Reduce to at most 2 flashes per second and lower the contrast of each flash. |
| `LINEAR_MOTION` | Ruch bez przyspieszeń | Most moves run at constant speed, which looks mechanical. Use eases: expo.out or power3.out for entrances, power2.inOut for moves, back.out(1.4) for pops. Keep ease none for long drifts only. |
| `NO_STAGGER` | Elementy pojawiają się naraz | Several elements enter on the same frame. Offset them by 0.05-0.1 s (stagger) so the eye can follow the order. |
| `TEXT_CLIPPED` | Tekst przycięty | The text is cut off by a container (overflow hidden) or by the frame. Enlarge the container, reduce the font size or shorten the copy. Check long Polish words. |
| `TEXT_TRUNCATED` | Tekst skrócony wielokropkiem | text-overflow: ellipsis is cutting the copy. Remove it, shorten the text or widen the box. |
| `TEXT_HIDDEN` | Tekst nie jest widoczny na ekranie | The DOM says the text is shown, but the pixels do not change when it is hidden: it is covered by another element, has the same colour as its background, or is clipped away. Raise its z-index, change its colour or remove the cover. |
| `TEXT_OVERLAP` | Teksty nakładają się | Two different texts overlap. Move them apart, stagger their timing so one leaves before the other lands, or reduce their size. |
| `TEXT_WALL` | Za dużo tekstu naraz | More than about 28 words are on screen at once. Social video is read in under 2 s per beat: keep to 6 words per beat or split the beat in two. |
| `TEXTS_INCOMPLETE` | TEXTS(t) pomija widoczne napisy | Some visible texts are not reported by window.TEXTS(t), so reading time, framing and contrast are not checked for them. Make TEXTS read the DOM (every visible text node with its Range rect and opacity). |
| `GLYPH_MISSING` | Brak glifów w foncie | Some characters are not drawn by the chosen font (they fall back to another font or show as boxes). For Polish load the font with the latin-ext subset or pick a font that covers ąćęłńóśźż, then run director_review again. |
| `FONT_FALLBACK` | Font nie jest dostępny | The first font in the stack is not loaded, so the page falls back to another font and renders differently than designed (and differently on other machines). Bundle the font next to the scene with @font-face (src: url(assets/font.woff2)) or choose a system font stack. |
| `ASSET_BROKEN` | Obraz się nie załadował | An <img> failed to load (wrong path, 404 or unsupported file). Add images with assets_add and use the returned snippet; files live in src/assets/ and are referenced as assets/<file>. |
| `NO_VISUAL_ASSETS` | Brak ikon i obrazków | The film has no icons, illustrations or images. Add 3-6 icons or stickers where text carries the message (assets_search, then assets_add) to make beats more visual. |
| `BEAT_MISSING` | Plan zakłada zmianę, której nie widać | The storyboard (director_plan) puts a new beat here, but nothing visibly changes in the film. Build the beat or update the plan. |
| `PLAN_STALE` | Plan nie pasuje do filmu | The saved plan has a different duration than the film. Run director_plan again. |
