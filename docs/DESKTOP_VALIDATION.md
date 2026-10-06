# Walidacja strony i paczki desktopowej

Walidacja w środowisku Linux, Python 3.12, przed publikacją:

- Rozszerzony zestaw FrameCore: 76 testów zaliczonych, jeden test Ruch 2.0 zatrzymany przez politykę Chromium dla `file://`. Test został zmieniony na serwowanie tego samego dokumentu przez HTTP; ponowne sprawdzenie całego modułu animacji oraz nowych testów desktopowych i strony zakończyło się powodzeniem.
- Rzeczywista zamrożona paczka PyInstaller: uruchomienie serwera z pliku wykonywalnego, trwały katalog projektów, import H.264/AAC, render MP4 z własnym FFmpeg i Chromium oraz połączenie MCP z konsolowym silnikiem — zaliczone. Projekt i jego rewizja pozostały zachowane.
- Linux użył jawnie oznaczonej kopii systemowego Chromium do tego sprawdzenia. Pobieranie oficjalnej przeglądarki Playwright w chmurze jest blokowane przez politykę sieci; ta kopia nie trafia do wydań Windows/macOS.
- Test strony: pięć szerokości 320–1440 px, brak poziomego przepełnienia, FAQ, `prefers-reduced-motion`, odtwarzanie rzeczywistego filmu i podstawianie linków instalatorów dla trzech systemów — zaliczone. Linki wydań były kontrolowaną odpowiedzią API, a nie dowodem istnienia instalatorów.
- Składnia obu plików GitHub Actions i JavaScript oraz `git diff --check` — poprawne.

Natywne testy gotowej paczki dla commitu `71320b9` przeszły na **Windows x64, macOS arm64 oraz macOS x64** w [GitHub Actions](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/actions/runs/37451256924). Każdy system sprawdził uruchomienie zamrożonego serwera, import H.264/AAC, eksport MP4 z dźwiękiem, trwałość projektu oraz MCP z polskimi znakami w nazwie. Oba DMG zostały zbudowane; publikacja wspólnego preview jest uzależniona także od ukończenia instalatora EXE.

Workflow **Desktop installers** publikuje instalatory dopiero po powodzeniu wszystkich trzech platform. Test w trybie `--headless` nie zastępuje ręcznej oceny okna WebView ani instalacji na osobistym komputerze. Wydanie preview nie ma komercyjnego podpisu Windows ani notaryzacji Apple.

Publikacja GitHub Pages wymaga włączenia Source: GitHub Actions przez administratora repozytorium. Próba utworzenia strony przez dostępną integrację zwróciła `403 Resource not accessible by integration`; adres strony można traktować jako działający dopiero po poprawnym wdrożeniu i sprawdzeniu publicznego HTTP.
