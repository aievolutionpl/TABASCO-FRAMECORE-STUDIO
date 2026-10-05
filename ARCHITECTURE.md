# Architektura TABASCO CREATIVES + FRAMECORE — STUDIO

## Wbudowana rozmowa 0.2

`framecore/agent.py` obsługuje iteracyjne tool calling przez OpenRouter lub OpenAI. Serwer utrzymuje jeden aktywny przebieg, limit 16 tur, możliwość zatrzymania i krótką historię rozmowy w RAM. Konfiguracja dostawcy pozostaje poza dokumentem projektu. Narzędzia wywołują wspólne `API.call` z aktorem `agent`, przypiętym identyfikatorem projektu i kontrolą rewizji. Narzędzia powłoki, dowolnego importu plików oraz globalnej biblioteki marek nie są udostępnione temu agentowi.

`framecore/static/agent-studio.js` dostarcza rozmowę, konfigurację oraz onboarding. Starszy `agent_control.py` zachowuje niezależny przepływ propozycji przez CLI i OpenRouter. Ich endpointy oraz identyfikatory interfejsu są rozdzielone; wspólną granicą edycji jest Store.

To projekt współpracy nad lokalnym studiem filmowym. Człowiek i agent korzystają z jednego zapisu projektu, zestawu walidowanych komend i historii cofania. Dotychczasowe narzędzia CLI vstudio pozostają dostępne.

## Decyzje po przeglądzie projektów

Wbudowujemy rzeczywisty `@hyperframes/player` 0.8.124 na licencji Apache-2.0, jako niezmieniony lokalny plik biblioteki. Nasz kompilator zamienia projekt JSON na deterministyczną kompozycję HTML zgodną z udokumentowanym adapterem osi czasu: `duration/time/seek/play/pause`. Podgląd i render używają tego samego kodu kompozycji.

Zachowujemy działającą infrastrukturę Python, Playwright i FFmpeg. Nie przenosimy całego monorepo HyperFrames Studio opartego na React 19, Zustand i Bun. Pakiety core/sdk/parsers/producer pozostają kandydatami do kolejnych integracji.

Z CartCut przyjmujemy zasadę wspólnej historii edytora i MCP; z FreeCut — oddzielenie modelu projektu od infrastruktury multimediów. Nie kopiujemy ich kodu. OpenCut jest obecnie przebudowywany wokół Rust i wtyczek. Null Motion służy wyłącznie jako odniesienie, ponieważ nie ma wybranej licencji całego projektu.

## Moduły

| Plik | Odpowiedzialność |
| --- | --- |
| `framecore.py` | Uruchomienie edytora, MCP i listy projektów |
| `model.py` | Format projektu i walidacja |
| `commands.py` | Wspólne operacje edytora i agenta |
| `store.py` | Blokady plików, zapis atomowy, rewizje, historia, propozycje |
| `api.py`, `mcp.py`, `server.py` | API wspólne dla HTTP i MCP; transporty i import |
| `composition.py`, `static/composition.js` | Kompilacja i odtwarzanie kompozycji |
| `render.py` | Eksport MP4 i miks dźwięku |
| `motion.py`, `templates.py`, `library.py`, `backgrounds.py` | 28 animacji, 12 szablonów, 24 tła i audytowany Creator Pack |
| `inspection.py` | Kontrola geometrii i rzeczywiste klatki dla agenta |
| `providers.py` | Interfejsy integracji z dostawcami materiałów |
| `static/` | Polski interfejs edycji |

Dane projektu znajdują się w `output/.framecore/`, poza śledzeniem Git. Każdy katalog projektu zawiera `state.json`, niezmienne materiały i eksporty. Osobny proces MCP korzysta z tego samego katalogu co edytor.

## Przepływ zmian

Interfejs lub MCP → komenda → kopia robocza projektu → walidacja → atomowy zapis projektu i historii → nowa rewizja → odświeżenie edytora. Zaznaczenie i wskaźnik czasu należą do współdzielonej sesji; nie zaśmiecają historii treści. Cofanie nie zmniejsza numeru rewizji.

Propozycja zapisuje sprawdzony stan wynikowy wraz ze stałymi identyfikatorami. Zastosowanie propozycji jest jednym krokiem historii. Zmiana projektu po jej utworzeniu uniemożliwia zastosowanie starej propozycji.

Pliki importowane mają identyfikatory lokalnych materiałów. Edytor sprawdza Host, Origin i token sesji. Agent importuje z jawnego katalogu `imports`; nie podaje dowolnych ścieżek systemowych. Importowane dokumenty HTML/JS i SVG nie są wykonywane. Ikony SVG pochodzą wyłącznie z zamkniętej, sprawdzonej biblioteki Phosphor.

## Animacja i eksport

Stan obrazu jest funkcją projektu i czasu klatki. Animacje semantyczne można łączyć z liniowymi klatkami kluczowymi pozycji, skali, obrotu i widoczności. Podział klipu zachowuje fazę wejścia i ciągłość klatek kluczowych; zmiana formatu skaluje geometrię oraz klatki pozycji.

Eksport zamraża projekt i materiały. Przeglądarka zapisuje obraz, a FFmpeg składa MP4 H.264 i miksuje klipy audio, uwzględniając przycięcia, czas, głośność oraz narastanie i wyciszenie. Postęp eksportu jest orientacyjny, na granicach etapów. Edycja podczas renderu nie zmienia rozpoczętego eksportu.

## Kolejne etapy

Import i ponowna edycja dowolnych źródeł HyperFrames, proxy wideo, przebiegi falowe, marketplace, ripple/slip, krzywe animacji, prawdziwe integracje dostawców i dopasowanie transkrypcji pozostają do wykonania. Obecne szablony są lokalnymi planami startowymi, a nie generowaniem przez model językowy.

## Kontrakt produkcyjny FrameCore

Opcjonalne `project.production` zawiera brief i wymagane materiały; `scene.beat` opisuje cel, stany i fokus. Zmiany używają dotychczasowych transakcji i undo. `framecore/production.py` waliduje kontrakt, reguły ruchu i układ wariantu; `review.py` generuje dowody z Chromium i przypisuje ocenę do pełnego odcisku projektu oraz SHA-256 plików. Raporty i checklisty są artefaktami poza historią montażu. `RenderJobs.start` sprawdza bramkę, a eksport kopiuje pliki do zamrożonego katalogu. `delivery.py` pakuje ten eksport. HTTP i MCP korzystają z tej samej implementacji; MCP przekazuje również obraz planszy klatek. [Pełny przepływ i ograniczenia](docs/PRODUCTION_PIPELINE.md).

## Agent dashboardu i dowody ruchu

`AgentControl` posiada połączenie w pamięci, jeden wątek zadania i sygnał anulowania. Adapter OpenRouter wysyła opis projektu do stałego endpointu; Codex/Claude są lokalnymi podprocesami zwracającymi JSON. Wynik jest ograniczony do komend edytora i przechodzi `propose_changes` oraz opcjonalnie `apply_proposal`, z rewizją i zaznaczeniem zamrożonym przy starcie. Klucz API nie jest zapisywany. Endpointy konfiguracji nie są narzędziami modelu MCP.

`motion_evidence` adresuje czasy scen, składa ważoną nakładkę z rzeczywistych PNG i porównuje dwa zapisane harmonogramy klatek. Korzysta z obecnego renderera; nie uruchamia Rust/Skia. Pomiar `quality` dotyczy SHA-256 ukończonego MP4 i nie stanowi oceny kreatywnej.

## Company brain w FrameCore

`framecore.brands.BrandLibrary` przechowuje formularze i obrazy w `_brands` przy projektach, z blokadą biblioteki, zapisem atomowym i własną wersją. `apply_brand_profile` kopiuje obrazy, sprawdza SHA-256 i wykonuje jeden zapis `attach_brand_snapshot`: `brandProfile`, konfigurację `brand` oraz materiały w jednej historii projektu. Stare kopie i formaty są niezależne od późniejszych zmian lub usunięcia biblioteki. Dashboard i MCP mają ten sam interfejs biblioteki. Szkic agenta jest osobnym zadaniem procesu, ze stanem `draft`, bez automatycznego zapisu ani dostępu do sieci; montaż dostaje zamrożony `companyBrain`.

## Fundamenty Media Engine (P0)

`framecore.persistence` przejmuje własność zapisu i blokad; `vstudio.locking` zachowuje zgodne re-eksporty. `media_import` oddziela import od HTTP, a `media.MediaEngine` generuje pochodne w cache adresowanym zawartością bez zmiany dokumentu projektu. API/MCP i `static/media-ui.js` korzystają z tego samego kontraktu. [Media Engine](docs/MEDIA_ENGINE.md) · [Audyt](docs/AI_STUDIO_AUDIT.md).
