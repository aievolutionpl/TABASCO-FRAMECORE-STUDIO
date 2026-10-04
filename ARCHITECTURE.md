# Architektura TABASCO CREATIVES + FRAMECORE — STUDIO

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
| `motion.py`, `templates.py`, `library.py` | 20 animacji, 4 szablony i biblioteka ikon |
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
