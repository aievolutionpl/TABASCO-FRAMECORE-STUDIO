# Walidacja strony i paczki desktopowej

Walidacja w środowisku Linux, Python 3.12, przed publikacją:

- Rozszerzony zestaw FrameCore: 76 testów zaliczonych, jeden test Ruch 2.0 zatrzymany przez politykę Chromium dla `file://`. Test został zmieniony na serwowanie tego samego dokumentu przez HTTP; ponowne sprawdzenie całego modułu animacji oraz nowych testów desktopowych i strony zakończyło się powodzeniem.
- Rzeczywista zamrożona paczka PyInstaller: uruchomienie serwera z pliku wykonywalnego, trwały katalog projektów, import H.264/AAC, render MP4 z własnym FFmpeg i Chromium oraz połączenie MCP z konsolowym silnikiem — zaliczone. Projekt i jego rewizja pozostały zachowane.
- Linux użył jawnie oznaczonej kopii systemowego Chromium do tego sprawdzenia. Pobieranie oficjalnej przeglądarki Playwright w chmurze jest blokowane przez politykę sieci; ta kopia nie trafia do wydań Windows/macOS.
- Test strony: pięć szerokości 320–1440 px, brak poziomego przepełnienia, FAQ, `prefers-reduced-motion`, odtwarzanie rzeczywistego filmu i podstawianie linków instalatorów dla trzech systemów — zaliczone. Linki wydań były kontrolowaną odpowiedzią API, a nie dowodem istnienia instalatorów.
- Składnia obu plików GitHub Actions i JavaScript oraz `git diff --check` — poprawne.

Natywne testy gotowej paczki dla commitu `71320b9` przeszły na **Windows x64, macOS arm64 oraz macOS x64** w [GitHub Actions](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/actions/runs/37451256924). Każdy system sprawdził uruchomienie zamrożonego serwera, import H.264/AAC, eksport MP4 z dźwiękiem, trwałość projektu oraz MCP z polskimi znakami w nazwie. Oba DMG i instalator EXE zostały zbudowane, a job publikacji zakończył się powodzeniem. Rzeczywiste pliki, sumy SHA-256 i informacje licencyjne są dostępne w [wydaniu desktop preview](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases/tag/v0.3.0-desktop.2).

Workflow **Desktop installers** publikuje instalatory dopiero po powodzeniu wszystkich trzech platform. Test w trybie `--headless` nie zastępuje ręcznej oceny okna WebView ani instalacji na osobistym komputerze. Wydanie preview nie ma komercyjnego podpisu Windows ani notaryzacji Apple.

Publikacja GitHub Pages wymaga włączenia Source: GitHub Actions przez administratora repozytorium. Próba utworzenia strony przez dostępną integrację zwróciła `403 Resource not accessible by integration`; adres strony można traktować jako działający dopiero po poprawnym wdrożeniu i sprawdzeniu publicznego HTTP.

## MotionDuo 0.3.1

Rebranding z commitu `61467c2` przeszedł budowanie i testy rzeczywistych zamrożonych paczek na Windows x64, macOS arm64 i macOS x64 w [GitHub Actions](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/actions/runs/37474357286). Publikacja zakończyła się powodzeniem; [wydanie 0.3.1](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases/tag/v0.3.1-desktop.1) zawiera trzy instalatory. Sprawdzono import, eksport MP4 z dźwiękiem, trwałość danych i połączenie MCP. Zakres pozostaje automatyczny i headless; nie obejmuje ręcznej instalacji na komputerze użytkownika.

Lokalna weryfikacja rebrandingu: 10 testów UI, Ruch 2.0, strony i zgodności danych oraz 9 testów biblioteki, kampanii i strony zaliczonych. Zestaw rdzenia i przeglądarki zaliczył 14 testów; dwa kolejne wymagały aktualizacji oczekiwanej liczby materiałów po dodaniu trzech assetów MotionDuo. Ponowne wykonanie tych dwóch testów zakończyło się powodzeniem (2/2). Edytor sprawdzono także wizualnie przy 1512 × 982 i 390 × 844 px.

## Efekty i montaż 0.3.2

Dla commitu `1a45eed` wszystkie trzy natywne paczki przeszły budowanie i testy zamrożonego serwera, eksportu H.264/AAC oraz MCP w [GitHub Actions](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/actions/runs/37478389473). Publikacja zakończyła się powodzeniem; sprawdzenie API wydania zwróciło HTTP 200 i trzy rzeczywiste instalatory z sumami SHA-256: [MotionDuo 0.3.2](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases/tag/v0.3.2-desktop.1).

Lokalnie zaliczono 54 testy w modułach rdzenia, biblioteki, agenta, nowych efektów i timeline, Ruch 2.0, interfejsu, strony, desktopu oraz współpracy człowieka z agentem. Testy obejmują piksele dziesięciu aktywnych przejść, siłę korekcji koloru, powtarzalne przewijanie, cofanie zsuwania klipów, blokady ścieżek i granice źródła. Rzeczywisty [film demonstracyjny](../assets/motionduo-effects-demo.mp4) wyeksportowano do H.264, 8 s, 640 × 360, 24 FPS. Ręcznie obejrzano klatki filmu i zrzuty panelu efektów przy 1512 × 982 i 390 × 844 px. Walidacja natywna nadal jest headless; nie zastępuje ręcznej instalacji na komputerze użytkownika.
