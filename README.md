<div align="center">

# vstudio

**Deterministyczne studio filmowe sterowane z CLI.**
Brief → zasady obrazu → klatki kontrolne → render roboczy → dźwięk → render finalny → wydanie.

[![Python](https://img.shields.io/badge/python-3.11%2B-22d3ee?style=flat-square)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/render-Playwright%20%2B%20Chromium-a855f7?style=flat-square)](https://playwright.dev/)
[![FFmpeg](https://img.shields.io/badge/audio-FFmpeg-f472b6?style=flat-square)](https://ffmpeg.org/)
[![License](https://img.shields.io/badge/license-MIT-10b981?style=flat-square)](LICENSE)
[![PL](https://img.shields.io/badge/docs-Polski-fbbf24?style=flat-square)](#)

**Film to strona HTML, w której obraz jest czystą funkcją czasu.**
Dźwięk powstaje proceduralnie — zero licencji, zero materiałów stockowych, zero telemetrii.

</div>

---

## Spis treści

- [Co to jest](#co-to-jest)
- [Showreel](#showreel)
- [Możliwości](#możliwości)
- [Przykładowa scena](#przykładowa-scena)
- [Szybki start](#szybki-start)
- [Studio: agent, nadzór jakości i dashboard](#studio-agent-nadzór-jakości-i-dashboard)
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

Trzy rzeczy odróżniają to od typowych narzędzi:

1. **Determinizm.** Klatka o czasie `t` jest zawsze tą samą klatką. Zero `Math.random`, zero timerów
   w rysowaniu. Dzięki temu można porównywać render ze studium referencji i wyłapywać regresje.
2. **Dźwięk bez praw autorskich.** Efekty (`whoosh`, `hit`, `click`, `chime`) są generowane
   proceduralnie, a miks jest liczony do **−14 LUFS** dwuprzebiegowym loudnorm — tak jak wymagają
   platformy streamingowe.
3. **Bramki zamiast subiektywności.** Projekt przechodzi przez osiem bramek jakości (`brief`,
   `stills`, `draft`, `sound`, `final`…). Dopóki bramka nie jest zatwierdzona, `status` przypomina,
   co jest następne. To robi film powtarzalnym, a nie „raz mi się udało”.

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
| **Render** | `render` (roboczy, half-res) i `render --final` (1080p), `--audio`, `--subframes` |
| **Dźwięk** | `cues` → `mix` → `mux`, albo `sound` jednym poleceniem; `sfx` — efekty proceduralne |
| **Wydanie** | `qa` (audyt pliku) i `deliver` (QA + plakat + paczka) |
| **Studio** | `dashboard`, `mcp`, `check`, `tools`, `skill`, `vendor`, `onboard`: agent, nadzór jakości i interfejs ([opis](#studio-agent-nadzór-jakości-i-dashboard)) |
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
dashboard    ─┼─►  rejestr możliwości (41 operacji) ─► projekt na dysku
CLI          ─┘             │
                            ├─► nadzorca jakości: sprawdza każdą zmianę sceny i mówi, co poprawić
                            └─► log aktywności: dashboard pokazuje na żywo, co robi agent
```

```bash
python vstudio.py dashboard            # interfejs w przeglądarce (onboarding przy pierwszym uruchomieniu)
python vstudio.py skill --install      # skill dla agenta + wpis vstudio w .mcp.json
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

- **41 narzędzi** w 10 kategoriach: onboarding, szablony, projekty, edycja sceny (z historią i cofaniem), **podgląd klatek jako obrazy**
  (agent naprawdę *widzi* film), nadzór, render, zadania, diagnostyka,
- **zasoby**: skill, wiedza (kontrakt strony, deterministyczny GSAP, pętla pracy), brief i ostatni raport każdego projektu,
- **prompty**: `make-video`, `fix-findings`, `onboard`.

Połączenie: dashboard → Agent → *Zainstaluj* (zapisuje `SKILL.md` i wpis w `.mcp.json`), albo ręcznie
`claude mcp add vstudio -- python vstudio.py mcp`. Przycisk *Testuj połączenie* robi prawdziwy handshake. Użytkownik zleca pracę
z dashboardu („Poproś agenta”), agent podejmuje ją przez `task_next`, a cała jego aktywność widać na żywo.

### Dashboard

| Widok | Do czego |
| --- | --- |
| **Start** | co dalej (środowisko, marka, zadania), projekty z podglądem, „poproś agenta” |
| **Biblioteka** | 8 szablonów z żywym podglądem (najedź, żeby odtworzyć), nowy projekt jednym kliknięciem |
| **Warsztat projektu** | podgląd sterowany `seek` (to, co widzisz, to się wyrenderuje), klatka po klatce, oś czasu z dźwiękiem, tekstami i znaleziskami; zakładki: Nadzór, Źródło (edytor z historią), Render (jobs z postępem), Potok (bramki), Agent |
| **Agent** | instalacja i test połączenia, tablica zadań, aktywność na żywo |
| **Mapa możliwości** | wszystkie operacje z parametrami i przyciskiem „Wypróbuj” |
| **Onboarding** | środowisko, marka (paleta, font, ton, format), agent, pierwszy film |

Dashboard słucha tylko na `localhost` (zmienia pliki projektów), odrzuca obcy `Host`/`Origin`, wymaga tokenu sesji dla każdej zmiany
i nie wychodzi poza katalog projektu. Skróty: spacja odtwarza, ←/→ krok o klatkę (z Shift o sekundę), L pętla.

### Praca offline: vendor

Strony z GSAP ładowanym z CDN nie uruchomią się bez sieci. `python vstudio.py vendor add gsap` (albo `--file plik.js` bez sieci) zapisuje
lokalną kopię, a podgląd, nadzorca i render podmieniają żądanie do CDN na plik z dysku. HTML sceny zostaje bez zmian.

### Mapa możliwości

Każda operacja jest zarejestrowana **raz** w [`vstudio/registry.py`](vstudio/registry.py) (nazwa, schemat parametrów, „kiedy użyć”,
czy zmienia pliki, czy jest jobem). Z tego jednego opisu powstają narzędzia MCP, API dashboardu,
[`docs/CAPABILITIES.md`](docs/CAPABILITIES.md) i tabela w skillu [`skills/vstudio/SKILL.md`](skills/vstudio/SKILL.md); test pilnuje,
żeby pliki nie rozjechały się z kodem. Nowa operacja to jedna funkcja z dekoratorem `@capability` w `vstudio/ops.py`, potem
`python vstudio.py tools --write-docs` i `python vstudio.py skill --write`.

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
vstudio render    render roboczy (--final = 1080p, --audio, --subframes)
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
```

Każda komenda przyjmuje `--json`, więc da się je zagnieżdzić w skryptach i CI.

## Struktura projektu filmowego

```
output/<brand>/<slug>/
├── src/index.html        # film (kontrakt strony); src/.history/ = wersje sceny (cofanie)
├── project.json          # parametry + stan bramek
├── brief.md              # cel, grupa docelowa, przekaz
├── visual_rules.md       # paleta, typografia, kompozycja
├── stills/               # klatki kontrolne + sheet.jpg
├── supervisor/           # rundy nadzoru: round-NNN.json, taśma filmowa, klatki-dowody
├── audio/                # cues.json, mix.m4a
├── renders/              # draft / final (.mp4 + .qa.json)
└── final/                # plakat, contact sheet, qa.json, DELIVERY.md
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
- Dashboard i serwer MCP nie łączą się z siecią; dashboard słucha wyłącznie na `localhost`. Stan użytkownika (profil marki, zadania, joby,
  lokalne kopie bibliotek) leży w `output/.studio/`, poza repozytorium.
- Zero materiałów stockowych i zero licencji do rozliczania — dźwięk jest generowany.
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