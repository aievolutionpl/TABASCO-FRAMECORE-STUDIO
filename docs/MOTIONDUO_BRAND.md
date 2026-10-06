# MotionDuo Studio

Nazwa produktu: **MotionDuo Studio**. Podpis: **by TABASCO CREATIVES + FRAMECORE**.

Znak tworzą dwie splecione wstęgi układające się w M. Ciepła strona symbolizuje człowieka, chłodna agenta AI; wspólne przecięcie wiąże je z montażem. Kierunek opracowano na podstawie referencji użytkownika po eksploracji dziewięciu prostych znaków.

- `assets/motionduo-banner.png`: polska adaptacja bannera przesłanego przez użytkownika, z aktualnym podpisem produktu.
- `assets/motionduo-logo.png`: pełny lockup na czarnym tle.
- `assets/motionduo-mark.png`: sam znak PNG z przezroczystością.
- `assets/motionduo-logo-concepts-3x3.png`: wcześniejsza plansza koncepcyjna, nie zestaw zatwierdzonych znaków.

Pliki wygenerowano narzędziem Image Gen. Są rastrowe; nie przedstawiamy ich jako wektorów. W małych ikonach używamy samego M, bez drobnego podpisu. Dodatkowy glow nie jest potrzebny. Wersja monochromatyczna wymaga oddzielnego dopracowania.

Rebranding dotyczy nazwy produktu, UI, strony, README oraz konfiguracji kolejnych paczek. Silnik `framecore`, identyfikator MCP, nazwy plików wykonywalnych i katalog danych `FrameCore Studio` pozostają stałe, aby utrzymać kompatybilność projektów i aktualizacji. Dotychczasowe wydanie 0.3.0 nadal zawiera poprzedni branding; nowe logo nie jest automatycznie dopisywane do opublikowanych instalatorów.

Repozytorium nadal znajduje się pod dotychczasowym adresem: próba zmiany nazwy na `MotionDuo-Studio` i opisu przez dostępne GitHub API zwróciła `403 Resource not accessible by integration`. Nazwę repozytorium można zmienić w jego Settings; po udanej zmianie należy zaktualizować adresy repozytorium i GitHub Pages.

## Użycie w montażu

Materiały są dołączone lokalnie do kolekcji **MotionDuo Studio** w Bibliotece. Oryginalne pliki i kopie biblioteki mają sumy SHA-256 w katalogu. Agent odczyta je przez `list_library` i doda przez `add_library_asset`; użytkownik może wybrać kolekcję lub przycisk **Marka → Dodaj logo MotionDuo**. Import i wstawienie znaku korzystają ze wspólnej historii cofania.
