# Mapa możliwości vstudio

> Plik generowany z rejestru możliwości (`vstudio/registry.py`, operacje w `vstudio/ops.py`). Nie edytuj ręcznie: `python vstudio.py tools --write-docs`.

Studio ma **41 operacji** w 10 kategoriach. Każda z nich jest dostępna tą samą drogą z trzech powierzchni, bo wszystkie czytają jeden rejestr:

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

### `agent_connect_info`: Jak podłączyć agenta

Polecenie MCP, fragment .mcp.json, ścieżki skilla i stan połączenia agenta.

**Zwraca:** command, claude_code, mcp_json, skill, agent

_brak parametrów_

### `agent_selftest`: Test połączenia agenta

Uruchamia serwer MCP i robi handshake jak prawdziwy klient: dowód, że agent się połączy.

**Zwraca:** ok, server, protocol, tools, ms

_brak parametrów_

### `agent_install`: Zainstaluj skill i konfigurację MCP

Zapisuje skill (SKILL.md) i wpis vstudio w .mcp.json.

**Zwraca:** installed{skill, mcp_config}

**Cechy:** zmienia pliki

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `skill` | boolean | nie | Domyślnie: `True`. |
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
| `topic` | string (contract \| gsap \| workflow \| findings \| motion \| visual \| brand) | tak |  |

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

## Render, dźwięk, wydanie

### `render_start`: Render

Uruchamia render jako job (draft w połowie rozdzielczości albo final). Zwraca job; postęp przez job_get/job_wait.

**Kiedy:** Render a draft after the supervisor says pass; final only after brief, visual_rules and stills are approved.

**Zwraca:** job, warnings[]

**Cechy:** job

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `final` | boolean | nie | Domyślnie: `False`. |
| `audio` | string | nie | path to a mixed audio file |
| `force` | boolean | nie | skip the gate check for a final render Domyślnie: `False`. |

### `sound_start`: Dźwięk

Buduje cue sheet z EV, miksuje do -14 LUFS i podkłada pod najnowszy render (job).

**Zwraca:** job

**Cechy:** job

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |

### `deliver_start`: Wydanie

QA pliku, plakat, paczka wydania i DELIVERY.md (job).

**Zwraca:** job

**Cechy:** job

| Parametr | Typ | Wymagany | Opis |
| --- | --- | --- | --- |
| `project` | string | tak | Project id 'brand/slug' (or a unique slug). Get ids from projects_list. |
| `strict` | boolean | nie | Domyślnie: `False`. |

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
| `SEEK_FAILED` | window.seek rzuca wyjątek | Fix the error thrown by seek(t); the film cannot be sampled or rendered until it works for every t in [0, DURATION]. |
| `ENGINE_UNSUPPORTED` | Silnik bez głębokich kontroli | Deep checks need the html engine (window.seek contract). Use still/render for this engine. |
