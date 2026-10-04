# Sprawdzenie FrameCore — 2026-10-04

Środowisko chmurowe: Python 3.12.14, Playwright 1.63.0, systemowy Chromium 151.0.7922.173 i dostępne FFmpeg/FFprobe. Nie skonfigurowano dostawcy generowania materiałów.

## Wyniki wykonanych testów

Nowy zestaw FrameCore: **14 testów przeszło, bez pominięć**. Polecenie:

```bash
python -m pytest tests/test_framecore.py tests/test_framecore_browser.py -o addopts='' -q
```

Sprawdzono wspólną edycję przez HTTP i osobny proces MCP, zaznaczenie, propozycje, cofanie, ponowną edycję człowieka, trwałość historii, konflikty rewizji i atomowość błędnych operacji. Import przez interfejs obejmował obraz produktu, logo oraz MP4 z dźwiękiem.

Test przeglądarkowy wyeksportował i pobrał film **15 s, 1080 × 1920, H.264 z audio**. FFprobe niezależnie sprawdził czas, rozdzielczość i kodeki. Oddzielnie wyrenderowano polski przykład współpracy **15 s, 1920 × 1080, H.264 + AAC**, dostępny w `assets/framecore-collaboration.mp4`. Klatki kontrolne obejrzano po renderze.

Dodatkowe sprawdzenia nowych funkcji:

- Ciągłość klatek kluczowych po podziale, skalowanie punktów przy zmianie formatu i odrzucanie błędnych wartości bez zmiany historii.
- Duplikowanie klipu oraz blokada zmiany na zablokowanej ścieżce.
- Ikony MIT jako materiały projektu, również dodawane przez propozycję z zachowaniem identyfikatorów.
- Cztery różne szablony i 20 animacji. Każdą animację sprawdzono po przewinięciu w różnej kolejności; stan tego samego czasu był zgodny.
- Głośność, narastanie i wyciszenie, walidacja czasów oraz ich zachowanie po podziale audio.
- Polski interfejs, edycja klatek przez panel, kontrola struktury i rzeczywisty obraz klatki przekazywany agentowi. Bez błędów JavaScript w testowanych ścieżkach.
- Ochrona tokenem, odpowiedź HTTP 409, odrzucanie błędnych ścieżek/SVG oraz bezpieczne traktowanie tekstu zawierającego znaczniki skryptów.
- Stan eksportu dostępny z osobnego procesu; brak dostawcy nie tworzy fikcyjnych materiałów.

Ponownie uruchomiono serwer studia. Otwiera polski interfejs i lokalny Player osiąga gotowość. Układy 1512, 900 i 390 px sprawdzono pod kątem poziomego przepełnienia. Zrzut: `assets/framecore-editor.png`.

Skrypt `scripts/install-local.sh` wykonano w obecnym środowisku i potwierdzono sprawdzenie instalacji. Skrypt PowerShell przygotowano, ale nie uruchomiono na Windows. Brak narzędzia dostępu do systemu użytkownika oznacza, że nie wykonano instalacji na jego komputerze.

## Granice potwierdzenia

To działający etap rozbudowy, a nie wszystkie fazy z briefu. Test osobnego procesu MCP potwierdza protokół; nie oznacza skonfigurowania klienta Codex/Claude na komputerze użytkownika.

Dostawcy AI i automatyczna transkrypcja wymagają integracji. Plan scen jest szablonem lokalnym. Nie obsługujemy jeszcze dowolnego importu źródeł HyperFrames, marketplace, ripple/slip, krzywych animacji ani automatycznego dopasowania transkrypcji.

Kontrola struktury nie zastępuje oceny wizualnej i odsłuchu. Pełny zestaw repozytorium wykonano ponownie: **233 testy przeszły, 24 nie przeszły** (257 łącznie). Wszystkie 24 błędy dotyczą testów animacji otwierających `file://`, blokowanych przez politykę zarządzanego Chromium. Dwie nieaktualne asercje dokumentacji i nazwy profilu zostały poprawione. Wynik 14/14 dotyczy zestawu FrameCore; cały historyczny zestaw pozostaje zablokowany w opisanej części.
