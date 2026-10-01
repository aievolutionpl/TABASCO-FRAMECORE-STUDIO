<div align="center">

# vstudio

**Deterministyczne studio filmowe: z CLI, przez agenta i z dashboardu.**
Brief → plan reżyserski → scena z assetami → nadzór → przegląd reżysera → render → dźwięk → wydanie.

[![Python](https://img.shields.io/badge/python-3.11%2B-22d3ee?style=flat-square)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/render-Playwright%20%2B%20Chromium-a855f7?style=flat-square)](https://playwright.dev/)
[![FFmpeg](https://img.shields.io/badge/audio-FFmpeg-f472b6?style=flat-square)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/license-MIT-10b981?style=flat-square)](LICENSE)
[![PL](https://img.shields.io/badge/docs-Polski-fbbf24?style=flat-square)](#)

**Film to strona HTML, w której obraz jest czystą funkcją czasu.**
Dźwięk powstaje proceduralnie, ikony i grafiki są własne albo mają ślad licencji, zero telemetrii.

</div>

---

## Spis treści

- [Co to jest](#co-to-jest)
- [Showreel](#showreel)
- [Możliwości](#możliwości)
- [Przykładowa scena](#przykładowa-scena)
- [Szybki start](#szybki-start)
- [Studio: agent, nadzór jakości i dashboard](#studio-agent-nadzór-jakości-i-dashboard)
- [Reżyser: plan, przegląd i zatwierdzenie przed wysyłką](#reżyser-plan-przegląd-i-zatwierdzenie-przed-wysyłką)
- [Rolki: formaty, napisy słowo po słowie i nakładka](#rolki-formaty-napisy-słowo-po-słowie-i-nakładka)
- [Assety: ikony, grafiki i obrazy](#assety-ikony-grafiki-i-obrazy)
- [Pipeline i bramki jakości](#pipeline-i-bramki-jakości)
- [Kontrakt strony filmowej](#kontrakt-strony-filmowej)
- [Zasady, które decydują o jakości](#zasady-które-decydują-o-jakości)
- [CLI — pełna lista komend](#cli--pełna-lista-komend)
- [Struktura projektu filmowego](#struktura-projektu-filmowego)
- [Wymagania](#wymagania)
- [Dźwięk: jak powstaje](#dźwięk-jak-powstaje)
- [Prywatność](#prywatność)
- [Licencja](#licencja)

---

## Co to jest

`vstudio` to mały, uczciwy warsztat do roboty z filmem. Nie jest generatorem „tekst na obrazek”, tylko
pełnym, powtarzalnym procesem: **piszesz scenę jak kod, system pilnuje rytmu, kadru i głośności**.

Cztery rzeczy odróżniają to od typowych narzędzi:

1. **Determinizm.** Klatka o czasie `t` jest zawsze tą samą klatką. Zero `Math.random`, zero timerów
   w rysowaniu. Dzięki temu można porównywać render ze studium referencji i wyłapywać regresje.
2. **Dźwięk bez praw autorskich.** Efekty (`whoosh`, `hit`, `click`, `chime`) są generowane
   proceduralnie, a miks jest liczony do **−14 LUFS** dwuprzebiegowym loudnorm — tak jak wymagają
   platformy streamingowe.
3. **Bramki zamiast subiektywności.** Projekt przechodzi przez osiem bramek jakości (`brief`,
   `stills`, `draft`, `sound`, `final`…). Dopóki bramka nie jest zatwierdzona, `status` przypomina,
   co jest następne. To robi film powtarzalnym, a nie „raz mi się udało”.
4. **Reżyser, który nie wypuszcza byle czego.** Zanim film trafi do użytkownika, przechodzi przegląd: czy co 2-3 s
   dzieje się coś nowego, czy tekst naprawdę się renderuje (też polskie znaki), czy ruch ma przyspieszenia, czy film nie wygląda
   tak samo od początku do końca. Finalny render i wydanie startują dopiero po zatwierdzeniu
   ([opis](#reżyser-plan-przegląd-i-zatwierdzenie-przed-wysyłką)).

## Showreel

25-sekundowy materiał demonstracyjny: pięć zupełnie różnych wizualizacji, zmiana co 5 sekund,
przejścia typu *slice glitch*, rozdzielenie kanałów RGB i rozbłysk na cięciu.

<video src="assets/showreel.mp4" width="100%" autoplay muted loop playsinline></video>

| Scena | Co pokazuje | Zegar |
| --- | --- | --- |
| **BOOT** | kinetyczna typografia litera po literze, deszcz kodu | `00:00 – 00:05` |
| **ANALIZA** | siatka klatek, detektor klatek kluczowych, wektory ruchu, panel metryk | `00:05 – 00:10` |
| **MONTAŻ** | oś czasu z klipami, *ripple edit*, przecięcie, taśma filmowa | `00:10 – 00:15` |
| **DŹWIĘK** | lustrzana fala, spektrum, znaczniki zdarzeń, miernik LUFS | `00:15 – 00:20` |
| **WYDANIE** | klatki zbiegające się do taśmy, pasek postępu, checklist, logo | `00:20 – 00:25` |

Plakat: [`assets/poster.jpg`](assets/poster.jpg) · Kontakt: [`assets/contact_sheet.png`](assets/contact_sheet.png)

## Możliwości

| Obszar | Co dostajesz |
| --- | --- |
| **Projekt** | `new`, `list`, `status` — projekt w `output/<brand>/<slug>/`, pełny stan bramek |
| **Środowisko** | `doctor` — Python, ffmpeg, ffprobe, Playwright + Chromium, renderery |
| **Studium referencji** | `analyze` → `SPEC.md`, `analysis.json`, klatki kluczowe |
| **Krytyka** | `compare` → `CRITIC_BRIEF.md` (render vs referencja, SSIM na klatkach) |
| **Montaż** | `edl` — montaż z listy decyzji w JSON |
| **Obraz** | `still` — klatki kontrolne + contact sheet; `readcheck` — czytelność i kadrowanie tekstów |
| **Render** | `render` (roboczy, half-res), `render --final` (1080p), `render --overlay` (przezroczysta nakładka ProRes 4444), `--audio`, `--subframes` |
| **Dźwięk** | `cues` → `mix` → `mux`, albo `sound` jednym poleceniem; `sfx` — efekty proceduralne |
| **Wydanie** | `qa` (audyt pliku) i `deliver` (QA + plakat + paczka) |
| **Studio** | `dashboard`, `mcp`, `check`, `tools`, `skill`, `vendor`, `onboard`: agent, nadzór jakości i interfejs ([opis](#studio-agent-nadzór-jakości-i-dashboard)) |
| **Reżyser** | `director plan / review / signoff / status`, `styles`: 16 stylów, storyboard co 2-3 s, przegląd rytmu, haka, tekstu i ruchu, zatwierdzenie przed wysyłką ([opis](#reżyser-plan-przegląd-i-zatwierdzenie-przed-wysyłką)) |
| **Rolki** | `director plan --format`, `assets captions / kit`, `render --overlay`: formaty z gotowym układem bitów, napisy słowo po słowie, sprężyny, nakładka z przezroczystością na własne nagranie ([opis](#rolki-formaty-napisy-słowo-po-słowie-i-nakładka)) |
| **Assety** | `assets search / add / generate / list`: 64 ikony offline, 12 generatorów grafik, Iconify i Openverse z kontrolą licencji ([opis](#assety-ikony-grafiki-i-obrazy)) |
| **Silniki** | `html` (domyślny, zero zależności poza przeglądarką), `remotion`, `hyperframes` |

## Przykładowa scena

W repo jest **kompletna, działająca scena** — 25-sekundowy showreel z pięcioma scenami i przejściami.
To ten sam materiał, który widzisz na górze strony.

```bash
# 1. podejrzyj w przeglądarce (pętla czasu startuje sama)
start examples/showreel/index.html

# 2. albo wyrenderuj go przez vstudio
py -3 -I vstudio.py new moje-demo --brand "Demo" --engine html --size 1920x1080 --fps 30 --duration 25
cp examples/showreel/index.html output/Demo/moje-demo/src/index.html
py -3 -I vstudio.py render --final -p moje-demo --audio output/Demo/moje-demo/audio/mix.m4a
```

Obok jest sześć krótkich pętli 1080×1350 na GSAP — [`examples/motion-graphics/`](examples/motion-graphics/README.md)
(ukryte cięcie, jedna ramka na wszystko, trzy kolory, cisza i uderzenie, części najpierw, jeden bohater). Każda to
jeden plik HTML zgodny z kontraktem strony, więc renderuje się tym samym `vstudio render`.

Warto zajrzeć do `examples/showreel/index.html` — plik ma ~440 linii i pokazuje wszystkie techniki,
które warto znać: kinetyczna typografia na sprężynie, *slice glitch*, rozdzielenie kanałów RGB,
rozbłysk na cięciu, deszcz kodu, siatka perspektywiczna, detektor klatek, oś czasu z klipami,
lustrzana fala, spektrum, miernik LUFS i plansza końcowa z cząsteczkami.

## Szybki start

Wymagania: **Python ≥ 3.11**, **ffmpeg** i **ffprobe** w `PATH`.

```bash
git clone https://github.com/aievolutionpl/vstudio.git
cd vstudio

# 1. zależności
py -3 -m pip install -r requirements.txt
py -3 -m playwright install chromium

# 2. czy środowisko gotowe?
py -3 -I vstudio.py doctor
```

Windows: `vstudio.cmd <komenda>` robi dokładnie to samo co `py -3 -I vstudio.py <komenda>`.

```bash
# 3. nowy projekt filmowy
py -3 -I vstudio.py new moj-film --brand "Moja Marka" \
    --engine html --size 1920x1080 --fps 30 --duration 25

# 4. napisz scenę: output/moja-marka/moj-film/src/index.html
#    wzorzec: templates/html-video-starter.html

# 5. klatki kontrolne → spójrz → render → dźwięk → final
py -3 -I vstudio.py readcheck -p moj-film
py -3 -I vstudio.py still    -p moj-film --times 1,6,11,16,21
py -3 -I vstudio.py render   -p moj-film
py -3 -I vstudio.py sound    -p moj-film
py -3 -I vstudio.py render   --final -p moj-film --audio output/moja-marka/moj-film/audio/mix.m4a
py -3 -I vstudio.py deliver  -p moj-film
```

## Studio: agent, nadzór jakości i dashboard

![Dashboard vstudio: podgląd sceny, oś czasu i panel nadzoru jakości](assets/dashboard.png)

Oprócz potoku CLI studio ma warstwę dla **agenta** (np. Claude Code) i dla **człowieka**. Obie siedzą na tym samym silniku,
więc niczego nie trzeba robić dwa razy:

```
agent (MCP)  ─┐
dashboard    ─┼─►  rejestr możliwości (57 operacji) ─► projekt na dysku
CLI          ─┘             │
                            ├─► nadzorca jakości: sprawdza każdą zmianę sceny i mówi, co poprawić
                            ├─► reżyser: plan, przegląd i zatwierdzenie przed wysyłką do użytkownika
                            └─► log aktywności: dashboard pokazuje na żywo, co robi agent
```

```bash
python vstudio.py dashboard            # interfejs w przeglądarce (onboarding przy pierwszym uruchomieniu)
python vstudio.py skill --install      # skill + agent-recenzent vstudio-director + wpis vstudio w .mcp.json
python vstudio.py check -p moj-film    # nadzór z terminala (werdykt, znaleziska, delta względem poprzedniej rundy)
```

**Zero nowych zależności:** serwer MCP i dashboard są napisane na bibliotece standardowej Pythona, interfejs nie ładuje nic z sieci.

### Nadzorca jakości: pilnuje generacji

Po każdej zmianie sceny nadzorca ładuje ją w Chromium w rozmiarze projektu, próbkuje klatki i zwraca **werdykt** (`pass`,
`needs_fixes`, `blocked`), wynik 0-100 i listę znalezisk z kodem, czasem, miejscem w kadrze i **wskazówką naprawy dla agenta**.
Kolejna runda pokazuje, co naprawiono, co jest nowe i co wciąż wisi. Agent działa w pętli: edytuj, sprawdź, popraw, aż `pass`.

| Kontrola | Łapie |
| --- | --- |
| Błędy strony i sieci | wyjątek JS, zablokowany CDN (`NET_FAILED`, z podpowiedzią: `vendor_add`) |
| Kontrakt | brak `seek`, `DURATION`, `TEXTS`, `EV`; czas różny od projektu |
| Determinizm | `NONDETERMINISTIC`: klatka zależy od kolejności `seek` (losowość, timery, nakładające się tweeny) |
| Czas i ruch | puste klatki, martwy czas > 1 s, twarde cięcia, pętla, która nie domyka się |
| Tekst | za krótko na ekranie, poza kadrem, niski kontrast, za mały, w strefie interfejsu platformy |

Automatyczny nadzór w tle (włączony domyślnie): gdy scena zmieni się na dysku, dashboard sam robi szybką rundę, więc werdykt jest
aktualny nawet wtedy, gdy agent o nim nie pamięta. Pełna lista kodów i napraw: [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md).

### Most dla agenta (MCP) i skill

`python vstudio.py mcp` uruchamia serwer MCP (stdio). Agent dostaje:

- **57 narzędzi** w 12 kategoriach: onboarding, szablony, projekty, edycja sceny (z historią i cofaniem), **podgląd klatek jako obrazy**
  (agent naprawdę *widzi* film), nadzór, **reżyser**, **assety**, render, zadania, diagnostyka,
- **zasoby**: skill, wiedza (kontrakt strony, deterministyczny GSAP, pętla pracy), brief i ostatni raport każdego projektu,
- **prompty**: `make-video`, `direct-video` (jak reżyser: plan, assety, przegląd, zatwierdzenie), `review-video`, `fix-findings`, `onboard`.

Połączenie: dashboard → Agent → *Zainstaluj* (zapisuje `SKILL.md`, subagenta `vstudio-director` i wpis w `.mcp.json`), albo ręcznie
`claude mcp add vstudio -- python vstudio.py mcp`. Przycisk *Testuj połączenie* robi prawdziwy handshake. Użytkownik zleca pracę
z dashboardu („Poproś agenta”), agent podejmuje ją przez `task_next`, a cała jego aktywność widać na żywo.

### Dashboard

| Widok | Do czego |
| --- | --- |
| **Start** | co dalej (środowisko, marka, zadania), projekty z podglądem, „poproś agenta” |
| **Biblioteka** | 10 szablonów z żywym podglądem (najedź, żeby odtworzyć), nowy projekt jednym kliknięciem |
| **Warsztat projektu** | podgląd sterowany `seek` (to, co widzisz, to się wyrenderuje), klatka po klatce, oś czasu z dźwiękiem, tekstami i znaleziskami; zakładki: Nadzór, **Reżyser** (plan stylu i bitów, wykres rytmu, znaleziska, zatwierdzenie, assety), Źródło (edytor z historią i **paleta sceny**: zmiana koloru w całej scenie albo zastosowanie kolorów marki jednym kliknięciem), Render (jobs z postępem i anulowaniem), Potok (bramki), Agent |
| **Agent** | instalacja i test połączenia, tablica zadań, aktywność na żywo |
| **Mapa możliwości** | wszystkie operacje z parametrami i przyciskiem „Wypróbuj” |
| **Onboarding** | środowisko, marka (paleta, font, ton, format), agent, pierwszy film |

Dashboard słucha tylko na `localhost` (zmienia pliki projektów), odrzuca obcy `Host`/`Origin`, wymaga tokenu sesji dla każdej zmiany
i nie wychodzi poza katalog projektu. Podglądy scen (a to kod, który może napisać agent) działają w piaskownicy
(`Content-Security-Policy: sandbox allow-scripts`, nieprzezroczysty origin), więc scena nie ma dostępu do tokenu ani do API;
panel steruje nią wyłącznie przez `postMessage` (`seek`, `info`). SVG i HTML otwierane wprost z `/files/` dostają ten sam
rygor (`sandbox`), więc plik z `src/assets/` nie przejmie origin dashboardu. Skróty: spacja odtwarza, ←/→ krok o klatkę (z Shift o sekundę), L pętla.

Joby (render, dźwięk, wydanie): w projekcie działa naraz jeden, bo dotykają tych samych plików. Stan jest w `output/.studio/jobs/`
i jest wspólny dla agenta (MCP) i dashboardu, więc dashboard może anulować job uruchomiony przez agenta. Anulowanie zabija całe drzewo
procesów (render → chromium → ffmpeg) i usuwa urwane pliki powstałe od startu joba; zamknięcie serwera też przerywa jego joby.

### Praca offline: vendor

Strony z GSAP ładowanym z CDN nie uruchomią się bez sieci. `python vstudio.py vendor add gsap` (albo `--file plik.js` bez sieci) zapisuje
lokalną kopię, a podgląd, nadzorca i render podmieniają żądanie do CDN na plik z dysku. HTML sceny zostaje bez zmian.

### Mapa możliwości

Każda operacja jest zarejestrowana **raz** w [`vstudio/registry.py`](vstudio/registry.py) (nazwa, schemat parametrów, „kiedy użyć”,
czy zmienia pliki, czy jest jobem). Z tego jednego opisu powstają narzędzia MCP, API dashboardu,
[`docs/CAPABILITIES.md`](docs/CAPABILITIES.md), tabela w skillu [`skills/vstudio/SKILL.md`](skills/vstudio/SKILL.md) i agent-recenzent
[`agents/vstudio-director.md`](agents/vstudio-director.md); test pilnuje, żeby pliki nie rozjechały się z kodem. Nowa operacja to jedna funkcja z dekoratorem `@capability` w `vstudio/ops.py`, potem
`python vstudio.py tools --write-docs` i `python vstudio.py skill --write` (zapisuje skill i agenta).

## Reżyser: plan, przegląd i zatwierdzenie przed wysyłką

Nadzorca odpowiada na pytanie „czy film jest poprawny technicznie?”. **Reżyser** na pytanie „czy ktoś zatrzyma się na nim w feedzie?”:
planuje styl i rytm przed budową, mierzy to, co widzi widz, i **nie wypuszcza filmu bez zatwierdzenia**. Działa tak samo dla
agenta (MCP), w dashboardzie (zakładka *Reżyser*) i z terminala.

```
director plan ─► scena + assety ─► check (nadzorca) ─► director review ─► director signoff ─► render finalny, wydanie
styl główny +     ikony, grafiki,   poprawność          rytm, hak, tekst,   decyzja po obejrzeniu  (bez zatwierdzenia
bity co 2-3 s     napisy            techniczna          ruch, fonty         klatek (checklista)     nie wystartują)
```

```bash
python vstudio.py director plan   -p moj-film --goal "Premiera aplikacji do treningów" --platform reels --tone "zabawny"
python vstudio.py director review -p moj-film              # kod wyjścia 3, gdy są błędy
python vstudio.py director signoff -p moj-film --notes "Obejrzałem taśmę: hak w 0.3 s, zmiany co 2 s" --all-checked
python vstudio.py styles                                   # biblioteka stylów (styles sticker-pop: opis i receptura)
```

### Plan: styl główny, dwa akcenty, bity co 2-3 s

Film nie może być cały w jednym „systemie”. **Stała jest marka** (paleta, font, ton, logo), a **zmienia się traktowanie**: układ, tło,
język ruchu, przejście, dźwięk. `director plan` dobiera styl główny i dwa akcenty o *różnych układach* (zawsze deterministycznie, z uzasadnieniem
wyboru), a potem układa storyboard: hak, rozwinięcie, dowód, CTA. Każdy bit ma czas, styl, układ, przejście (z dźwiękiem), regułę tekstu
(maks. 6 słów) i hasła do assetów. Dwa sąsiednie bity nigdy nie mają tego samego stylu ani układu. Plan trafia do `director/plan.json`
(opcjonalnie do `STORYBOARD.md`, poprzedni plik jest zachowany), a przegląd sprawdza potem, czy film się go trzyma (`BEAT_MISSING`).

| Styl | Do czego | Energia |
| --- | --- | --- |
| `kinetic-type` Kinetyczna typografia | ogłoszenia, promocje, premiery | 5 |
| `sticker-pop` Naklejki i emoji | sklep, jedzenie, UGC | 5 |
| `neo-brutal` Neo-brutalizm | młodzieżowe premiery, wydarzenia | 4 |
| `retro-synth` Retro synthwave | muzyka, gry, rozrywka | 4 |
| `glass-ui` Szkło i interfejs | aplikacje, SaaS, demo | 3 |
| `gradient-mesh` Płynny gradient | marka, produkt, spokojny nowoczesny ton | 3 |
| `isometric-3d` Obiekt 3D | sprzęt, gadżety, premiery produktu | 3 |
| `data-story` Opowieść z danych | raporty, B2B, dowody | 3 |
| `paper-cut` Papierowy collage | rzemiosło, jedzenie, rodzina | 3 |
| `terminal-code` Terminal i kod | narzędzia dla developerów, AI | 3 |
| `swiss-minimal` Szwajcarski minimalizm | edukacja, firma, raporty | 2 |
| `dark-luxe` Ciemny luksus | perfumy, biżuteria, premium | 2 |
| `creator-captions` Napisy twórcy | rolki z nagraniem twórcy: wielkie napisy słowo po słowie | 4 |
| `tool-showcase` Polecajka narzędzia | okno przeglądarki, karta zasobu z plakietką DARMOWY | 3 |
| `cinematic-captions` Kinowe napisy | historie, opinie, podróże | 2 |
| `pastel-soft` Miękki pastel | uroda, zdrowie, dzieci | 2 |

Każdy styl ma paletę, typografię (z uwagą o `latin-ext` dla polskich znaków), język ruchu, przejścia, zasady kompozycji i **gotową recepturę
CSS/GSAP** (`style_get`). Do tego 13 przejść (każde deterministyczne w GSAP) i 15 układów bitów (`styles_list`).

### Przegląd: co mierzy

| Obszar | Kody | Jak |
| --- | --- | --- |
| **Rytm** | `SLOW_PACE`, `BEAT_MISSING` | nowa sytuacja wizualna (zmiana ≥ 12% kadru w siatce 8×8 względem chwili sprzed 0,5 s) co najwyżej co 2,5 s (reels, tiktok, shorts, story), 3,5 s (feed, linkedin), 5 s (www, prezentacja); końcowy odcinek może trwać o 1 s dłużej (CTA) |
| **Hak** | `WEAK_HOOK`, `NO_HOOK_TEXT` | w pierwszych 1,5 s zmienia się ≥ 8% kadru; tekst albo obraz do 1,2 s |
| **Różnorodność** | `MONOTONE_STYLE` | film dzielony na plasterki po 1 s, grupowane w „looki” (układ kolorów 3×3): wymagane 2 looki od 4,5 s, 3 od 12 s, 4 od 20 s |
| **Ruch** | `LINEAR_MOTION`, `NO_STAGGER` | położenia elementów z DOM w pełnej liczbie klatek (bez zrzutów): ruchy o stałej prędkości, ≥ 6 elementów wchodzących w tej samej klatce; ruch dziecka liczony względem rodzica |
| **Tekst** | `TEXT_CLIPPED`, `TEXT_TRUNCATED`, `TEXT_HIDDEN`, `TEXT_OVERLAP`, `TEXT_WALL`, `TEXTS_INCOMPLETE` | geometria z DOM **oraz weryfikacja pikseli**: tekst robiony na chwilę przezroczystym, a jeśli obraz się nie zmienia, napisu nie widać (zasłonięty, w kolorze tła, przycięty) |
| **Fonty** | `GLYPH_MISSING`, `FONT_FALLBACK` | czy każdy znak (w tym ąćęłńóśźż) jest rysowany wybranym fontem, a nie zamiennikiem lub pustym kwadratem |
| **Obrazy** | `ASSET_BROKEN`, `NO_VISUAL_ASSETS` | obraz, który się nie załadował; film bez żadnej ikony i grafiki |
| **Bezpieczeństwo** | `FLASH_RISK` | ≥ 6 skoków jasności w 1 s (próg trzech błysków na sekundę, WCAG 2.3.1) |

Raport zawiera werdykt, wynik, delta względem poprzedniej rundy, **taśmę klatek** i **wykres rytmu** (krzywa zmiany kadru, nowe sytuacje, luki,
bity z planu, „looki”). Przegląd ma budżet czasu: ciężka scena dostaje rzadsze próbkowanie, a raport mówi o tym wprost (`thinned`,
`motion_skipped`), zamiast przekroczyć limit czasu klienta MCP.

### Zatwierdzenie: bramka przed wysyłką

Przegląd mierzy to, co mierzalne. **Czy jest ładnie, rozstrzyga recenzent** (agent albo człowiek), więc `director signoff` wymaga:
notatki, co zobaczył na klatkach, potwierdzenia sześciu pozycji checklisty (hak, tekst, rytm, styl, ruch, assety) i decyzji o każdym ostrzeżeniu
(naprawić albo świadomie zaakceptować **z powodem**; błędów nie da się zaakceptować). Zatwierdzenie jest powiązane z odciskiem całej
sceny, więc **każda zmiana je unieważnia**. Zapisuje też, kto zdecydował, na podstawie źródła wywołania (agent przez MCP, człowiek w dashboardzie, CLI), a nie
argumentu, którego nie da się podrobić. `render_start --final` i `deliver_start` odmawiają startu bez zatwierdzenia (wyłącznik: profil
`require_director`; pominięcie na wyraźną prośbę użytkownika: `skip_review`). CLI `deliver` dopisuje w tym przypadku ostrzeżenie do `DELIVERY.md`.

To bramka procesu, nie dowód, że recenzent patrzył: dlatego checklista, notatka z konkretami i ślad w logu aktywności.

### Agent-recenzent

`skill --install` zapisuje subagenta Claude Code [`vstudio-director`](agents/vstudio-director.md): surowy recenzent z własnym kontekstem i
**bez narzędzi do edycji sceny** (niezależność oceny). Procedura: plan, `check_run`, `director_review`, obejrzenie taśmy i klatek w kluczowych
chwilach, decyzja według checklisty, `director_signoff`, odpowiedź z werdyktem i listą poprawek. Agent budujący film wywołuje go przed
powiedzeniem użytkownikowi, że film jest gotowy.

## Rolki: formaty, napisy słowo po słowie i nakładka

Rolka twórcy ma powtarzalny układ: mówiąca głowa na dole, karty i okno nad nią, wielkie napisy słowo po słowie na styku i CTA „skomentuj słowo”.
Studio zna go jako **format**, a nie jako jeden szablon, więc te same klocki składają się w różne filmy:

| Format | Układ bitów | Czas |
| --- | --- | --- |
| `tool-drop` Polecajka narzędzia | hak → okno przeglądarki z produktem → karta zasobu (plakietka DARMOWY, komenda w terminalu) → korzyści → CTA | 14-24 s |
| `talking-head` Mówiąca głowa z napisami | hak → trzy punkty z kartą na każdy → CTA | 10-30 s |
| `listicle` Lista | hak → N pozycji (2-7) → CTA | 10-30 s |

`director plan --format tool-drop` (albo `director_plan` z `format`) układa bity z tego schematu zamiast z ogólnego szkieletu. Marka (paleta, font, ton) zostaje
Twoja; format ustala bity, style i układy. Za krótki film jest odrzucany z podaniem minimum, a bit dłuższy niż limit tempa platformy o ponad sekundę albo krótszy niż sekunda
dostaje ostrzeżenie w planie (`warnings`).

**Napisy słowo po słowie** (`assets captions`, narzędzie `captions_build`) powstają z tekstu lektora, pliku SRT/VTT albo znaczników słów z transkrypcji.
Trzy style: `single` (jedno wielkie słowo; słowa krótsze niż 0,2 s łączą się w parę, żeby nie migały), `pop` (słowa wskakują, linia zostaje) i `karaoke` (cała linia,
aktywne słowo podświetlone). Liczby i wskazane słowa dostają kolor akcentu. Dane i silnik trafiają do `src/assets/` (`captions.js`, `motion-kit.js`), a w scenie wystarczą
trzy linie (`VS.captions.mount`, `draw(t)` w `seek`, `texts(t)` w `TEXTS`). Uwaga: bez znaczników czasów słowa są rozłożone proporcjonalnie do długości i interpunkcji,
czyli **przybliżenie**; dokładne napisy daje SRT albo `words`. Wpisy napisów mają w `TEXTS` pole `caption: true`: sprawdzamy tylko, czy mieszczą się w kadrze,
a nie czas czytania, bo widz je słyszy.

**Zestaw ruchu** (`assets kit`, `templates/motion-kit.js`): sprężyny jako ease dla GSAP (`VS.spring(170, 16)` z czasem ustalenia `VS.springDuration`), mocne krzywe
Béziera (`VS.ease.out`), licznik, pisanie znak po znaku i miganie kursora liczone wprost z `t`. Wszystko deterministyczne, bez timerów i losowości. Zasady „ciężaru” ruchu
(ease-out na wejściu, jedna sprężyna na bit, skala od .8-.95, stagger .04-.09 s, ruch ustala się przed następnym) są w wiedzy agenta: `knowledge_get topic=feel`.

**Nakładka z przezroczystością.** Własnego nagrania nie renderujemy: `render --overlay` (`render_start` z `overlay: true`) zapisuje same animowane warstwy jako
**ProRes 4444 `.mov` z kanałem alfa**, pełna rozdzielczość projektu, bez dźwięku. Składasz je w montażu na swoim nagraniu. Renderer ustawia `window.__ALPHA__`,
zdejmuje tło strony i ukrywa elementy oznaczone `data-alpha="hide"`; szablony rolek chowają tło i placeholder nagrania same. Nakładka trafia do użytkownika, więc
wymaga tego samego zatwierdzenia reżysera co finalny render. Większość przeglądarek (Chrome, Firefox) nie odtwarza ProRes, więc dashboard pokazuje plik na liście do pobrania, bez odtwarzacza.

Dwa szablony do startu (Biblioteka): `resource-drop` (16 s, polecajka narzędzia) i `word-captions` (13,5 s, mówiąca głowa). Oba przechodzą nadzorcę i reżysera bez ostrzeżeń.
Szablon może zawierać znacznik `<!--@motion-kit-->`: przy tworzeniu projektu wchodzi w jego miejsce zestaw ruchu, więc kod sprężyn i napisów jest w jednym miejscu.

```bash
python vstudio.py director plan -p moj-film --goal "Darmowy skill do animacji" --format tool-drop --cta "Skomentuj ANIMACJA"
python vstudio.py assets captions -p moj-film --text "Ten skill zmienia 3 rzeczy w Twoich filmach" --style pop --highlight skill
python vstudio.py assets captions -p moj-film --srt napisy.srt --style karaoke        # dokładne czasy
python vstudio.py render -p moj-film --overlay                                         # renders/moj-film_overlay_*.mov
```

## Assety: ikony, grafiki i obrazy

Beat złożony z samego tekstu to najczęstszy powód, dla którego film wygląda jak slajd. Assety lądują w `src/assets/` projektu (strona widzi je jako
`assets/<plik>`), a ślad pochodzenia (źródło, licencja, autor, hash) w `src/assets/ASSETS.json`. `deliver` składa z niego sekcję *Credits*.

| Źródło | Co | Sieć | Licencja |
| --- | --- | --- | --- |
| `builtin:<id>` | 64 ikony liniowe SVG, wyszukiwanie po polsku i angielsku („koszyk”, „rakieta”) | nie | własne |
| `assets generate` | 12 generatorów z ziarna: `blob`, `mesh` (zorza), `dots`, `grid`, `rings`, `waves`, `rays`, `confetti`, `grain`, `starburst`, `squiggle`, `arrow`; kolory marki | nie | własne |
| `iconify:<zestaw>:<nazwa>` | ikony z Iconify | tak | sprawdzana w API (MIT, ISC, Apache, CC0, CC-BY, OFL...), CC-BY z autorem w creditsach |
| `openverse:<id>` | zdjęcia z Openverse | tak | tylko CC0, domena publiczna i CC-BY (bez NC/ND/SA) |
| adres `https://` | dowolny obraz | tak | nieznana: do sprawdzenia przez użytkownika |

SVG wstawiany inline dziedziczy `color`, więc jedna ikona maluje się paletą marki i animuje jak każdy element. Pobieranie jest bezpieczne z założenia:
tylko `https` na porcie 443, odrzucane adresy nieglobalne (localhost, sieci prywatne, `169.254.169.254`), każde przekierowanie sprawdzane od nowa, połączenie
z zweryfikowanym adresem IP (bez proxy), limity rozmiaru i czasu, typ pliku ustalany po zawartości, SVG przez czarną i białą listę (bez skryptów, stylów, `foreignObject`
i odwołań na zewnątrz), obraz rastrowy zmniejszany i kodowany ponownie bez metadanych.

```bash
python vstudio.py assets search koszyk                    # wbudowane
python vstudio.py assets add builtin:cart -p moj-film --color "#FF6B4A"
python vstudio.py assets generate mesh -p moj-film --seed 7
python vstudio.py assets search rocket --source iconify   # wymaga internetu
```

## Pipeline i bramki jakości

```
brief ──▶ reference_spec ──▶ visual_rules ──▶ stills ──▶ draft ──▶ sound ──▶ critic ──▶ final ──▶ deliver
  ▲            (opcjonalna)                                                                    │
  └────────────────────────────────── gate approve ─────────────────────────────────────────────┘
```

`reference_spec` powstaje automatycznie, gdy film powstaje **z** referencji (`analyze`).
Przy filmie od zera jest zbędna — `status` sam oznacza ją jako „nie potrzebna”.

```bash
py -3 -I vstudio.py status -p moj-film        # co zrobione, co dalej
py -3 -I vstudio.py gate approve stills -p moj-film
py -3 -I vstudio.py gate score critic --score 8 -p moj-film
```

Osiem bramek to potok z CLI. W studio (agent i dashboard) dochodzi do tego **zatwierdzenie reżysera** dla aktualnej wersji sceny: bez niego
finalny render i wydanie nie wystartują ([opis](#zatwierdzenie-bramka-przed-wysyłką)).

Co sprawdza warstwa `qa` na pliku końcowym:

| Kontrola | Kryterium |
| --- | --- |
| Rozdzielczość | zgodna z projektem (np. 1920×1080) |
| Płynność | zgodna z projektem (np. 30 fps) |
| Długość | w tolerancji ±10 % |
| Format pikseli | `yuv420p` — odtwarza się wszędzie |
| Martwy czas | wykrywanie klatek bez zmian |
| Czarne klatki | brak |
| Domknięcie pętli | SSIM pierwszej i ostatniej klatki |
| Poziom audio | średnia w normie |
| Szczyt audio | true peak poniżej −1 dBTP |

## Kontrakt strony filmowej

Silnik `html` renderuje Twoją stronę przez Playwright/Chromium. Strona musi wystawić sześć rzeczy:

| Symbol | Typ | Znaczenie |
| --- | --- | --- |
| `window.DURATION` | `number` | długość filmu w sekundach |
| `window.seek(t)` | `fn` | narysuj klatkę dla czasu `t` — deterministycznie |
| `window.EV` | `[{t, type}]` | zdarzenia dźwiękowe → z nich powstaje cue sheet |
| `window.TEXTS(t)` | `fn` | widoczne teksty z pikselowymi boksami → dla `readcheck` |
| `window.__ready` | `Promise` | fonty i obrazy gotowe do zrzutu klatki |
| `window.__CAPTURE__` | `boolean` | flaga renderera — gdy `true`, nie odpalaj pętli `requestAnimationFrame` |

Opcjonalnie: wpis `TEXTS` z `caption: true` oznacza napis słowo po słowie (sprawdzany tylko pod kątem kadru), a `window.__ALPHA__` (ustawiane w trybie nakładki)
mówi scenie, żeby schowała tło i placeholder nagrania.

Minimalny szkielet (pełny wzorzec: `templates/html-video-starter.html`):

```html
<canvas id="c"></canvas>
<script>
  window.DURATION = 25;
  const EV = [{ t: 1.2, type: 'hit' }, { t: 5.0, type: 'whoosh' }];
  window.EV = EV.sort((a, b) => a.t - b.t);
  const TEXTS = [{ id: 'title', text: 'MÓJ FILM', x: 0.5, y: 0.5, size: 9, align: 'center', tIn: 0.5, tOut: 6 }];

  function draw(t) {
    const c = document.getElementById('c').getContext('2d');
    c.clearRect(0, 0, innerWidth, innerHeight);
    c.fillStyle = '#0a1230'; c.fillRect(0, 0, innerWidth, innerHeight);
    // ...rysuj klatkę dla t — wyłącznie z t, bez timerów i Math.random...
    c.font = '800 96px Manrope, "Segoe UI", system-ui, sans-serif';
    c.fillStyle = '#22d3ee'; c.textAlign = 'center';
    c.fillText('MÓJ FILM', innerWidth / 2, innerHeight / 2);
  }
  window.seek = draw;
  window.TEXTS = (t) => TEXTS.filter((s) => t >= s.tIn && t <= s.tOut).map((s) => ({ ...s }));

  if (!window.__CAPTURE__) {                       // podgląd w przeglądarce
    const t0 = performance.now();
    (function loop() { draw((performance.now() - t0) / 1000); requestAnimationFrame(loop); })();
  }
</script>
```

## Zasady, które decydują o jakości

Te reguły są wbudowane w `templates/MOTION_RULES.md` i `templates/VISUAL_RULES.md` — i pilnowane
przez `readcheck` oraz `qa`:

1. **Obraz jest czystą funkcją czasu.** Żadnych `setTimeout`, żadnego `Math.random` w rysowaniu.
   Inaczej klatki przestają być powtarzalne, a porównanie z referencją kłamie.
2. **Nic nie zamarza.** Każdy element wchodzi albo dryfuje. Klatka bez ruchu to najczęstszy zarzut
   do filmu — i najłatwiejszy do naprawienia.
3. **Wejście sprężyną, nie liniowo.** `spring(τ, ζ≈0.8, ω≈15..18)`: wchodzi szybko, ląduje miękko.
4. **Tekst stoi i jest duży.** Nie animuj treści, którą ktoś ma przeczytać. `readcheck` pilnuje
   czasu czytania — minimum zależne od rozmiaru fontu.
5. **Kadr gęsty.** HUD w narożnikach, belki akcentowe, wskaźniki. Puste narożniki wyglądają jak slop.
6. **Jedno źródło prawdy dla tekstów.** Rysowanie i `window.TEXTS` czytają tę samą tablicę — inaczej
   kontrola czytelności kłamie i przepuszcza tekst, którego nie ma na ekranie.

> **Pułapka, o której warto wiedzieć:** `readcheck` analizuje *boksy* deklarowane w `window.TEXTS`,
> a nie piksele. Jeśli zapomnisz narysować tekstu, kontrola powie „OK”. Dlatego po każdej zmianie
> kompozycji obejrzyj `stills/sheet.jpg`.

## CLI — pełna lista komend

```
vstudio new       nowy projekt w output/<brand>/<slug>/
vstudio list      projekty i ich następny krok
vstudio doctor    sprawdzenie środowiska (uruchom pierwszy)
vstudio status    stan bramek i następny krok
vstudio still     klatki kontrolne + contact sheet
vstudio render    render roboczy (--final = 1080p, --overlay = przezroczysta nakładka .mov, --audio, --subframes)
vstudio gate      approve | reset | score  (brief…final)
vstudio cues      cue sheet z window.EV
vstudio mix       miks do -14 LUFS
vstudio mux       wideo + audio -> mp4
vstudio sound     cues + mix + mux jednym poleceniem
vstudio readcheck czytelność i kadrowanie tekstów
vstudio sfx       proceduralne efekty dźwiękowe
vstudio analyze   studium referencji -> SPEC.md + analysis.json
vstudio compare   render vs referencja -> CRITIC_BRIEF.md
vstudio edl       montaż z listy decyzji (JSON)
vstudio qa        audyt pliku
vstudio deliver   QA + plakat + paczka wydania
vstudio dashboard dashboard w przeglądarce (onboarding, podgląd, nadzór, rendery, aktywność agenta)
vstudio mcp       serwer MCP dla agenta (narzędzia, wiedza, prompty)
vstudio check     nadzór jakości: błędy, klatki, pętla, determinizm, czytelność
vstudio tools     mapa wszystkich możliwości (--write-docs generuje docs/CAPABILITIES.md)
vstudio skill     skill dla agenta (--write, --install)
vstudio vendor    lokalne kopie bibliotek z CDN: add | list | remove
vstudio onboard   stan studia i co zrobić dalej
vstudio director  reżyser: plan (--format) | review | signoff | status (zatwierdzenie przed wysyłką)
vstudio styles    biblioteka stylów reżysera (z id: pełny opis i receptura)
vstudio assets    ikony, grafiki i obrazy: search | add | generate | list | captions | kit
```

Każda komenda przyjmuje `--json`, więc da się je zagnieżdzić w skryptach i CI.

## Struktura projektu filmowego

```
output/<brand>/<slug>/
├── src/index.html        # film (kontrakt strony); src/.history/ = wersje sceny (cofanie)
├── src/assets/           # ikony, grafiki, obrazy + ASSETS.json (źródło, licencja, autor, hash)
├── project.json          # parametry + stan bramek
├── BRIEF.md              # cel, grupa docelowa, przekaz
├── VISUAL_RULES.md       # paleta, typografia, kompozycja
├── STORYBOARD.md         # bity z planu reżyserskiego (jeśli zapisany)
├── stills/               # klatki kontrolne + sheet.jpg
├── supervisor/           # rundy nadzoru: round-NNN.json, taśma filmowa, klatki-dowody
├── director/             # plan.json, rundy przeglądu (review-NNN.json, taśma, rhythm.png), signoff.json
├── audio/                # cues.json, mix.m4a
├── renders/              # draft / final (.mp4 + .qa.json), nakładki (.mov, ProRes 4444 z alfą)
└── final/                # plakat, contact sheet, qa.json, DELIVERY.md (z creditsami assetów)
```

## Wymagania

| Składnik | Wersja | Do czego |
| --- | --- | --- |
| Python | ≥ 3.11 | CLI |
| `numpy`, `Pillow` | ≥ 2.0 / ≥ 10 | analiza klatek, contact sheet |
| `playwright` | ≥ 1.40 | render strony do klatek |
| Chromium | — | silnik renderujący |
| FFmpeg / FFprobe | dowolny | kodowanie, miks, audyt |

Sam silnik `html` nie wymaga Node.js. `remotion` i `hyperframes` są opcjonalne i potrzebują `npx`.

## Dźwięk: jak powstaje

1. Scena deklaruje zdarzenia: `window.EV = [{ t: 5.0, type: 'whoosh' }, …]`.
2. `cues` zamienia je na cue sheet (`audio/cues.json`) — to jedno źródło prawdy dla obrazu i dźwięku.
3. `sfx` generuje brzmienia proceduralne (szum, obwiednie, transpozycja) — bez plików stockowych.
4. `mix` składa ścieżki i liczy głośność dwuprzebiegowym `loudnorm` do **−14 LUFS**.
5. `mux` spina wideo z dźwiękiem.

W praktyce `sound` wykonuje kroki 2–5 jednym poleceniem.

## Prywatność

- Zero telemetrii. Nic nie wychodzi poza Twoją maszynę poza instalacją zależności.
- Dashboard i serwer MCP same z siebie nie łączą się z siecią; dashboard słucha wyłącznie na `localhost`. Sieć jest używana tylko na
  wyraźne polecenie: `vendor add` (kopia biblioteki z CDN) oraz `assets search/add` ze źródeł `iconify`, `openverse` i adresu `https` (z zabezpieczeniami opisanymi
  wyżej). Stan użytkownika (profil marki, zadania, joby, lokalne kopie bibliotek) leży w `output/.studio/`, poza repozytorium.
- Dźwięk jest generowany, a ikony i grafiki są własne albo mają zapisany ślad licencji (`ASSETS.json` i *Credits* w `DELIVERY.md`). Za prawa do materiałów
  z adresu `https` odpowiada użytkownik.
- Render działa lokalnie w headless Chromium; strona filmowa nigdy nie łączy się z siecią
  (jedyny wyjątek: pętle w `examples/motion-graphics/` ładują GSAP z `cdnjs.cloudflare.com`, tak jak w promptach —
  do pracy offline podmień `src` na lokalną kopię).

## Licencja

MIT — pełny tekst w [LICENSE](LICENSE).

Renderery dołączone w `vstudio/renderers/` używają wyłącznie biblioteki standardowej Pythona,
Playwright i FFmpeg. Kod dla silników `remotion` i `hyperframes` jest generowany, ale te silniki
nie są dołączane — podlegają własnym licencjom.

---

<div align="center">

**vstudio** — zrobione w Polsce 🇵🇱
Przez **AI Evolution Polska** · deterministyczne narzędzia do roboty z obrazem i dźwiękiem

</div>