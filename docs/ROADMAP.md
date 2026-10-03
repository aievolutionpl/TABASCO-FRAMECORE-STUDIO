# Roadmapa Rozbudowy VStudio — Lokalne Studio Produkcyjne

Niniejsza roadmapa określa plan ewolucyjnej rozbudowy repozytorium `vstudio` w pełnoprawne, lokalne studio produkcyjne w oparciu o architekturę:
**własne materiały + profil marki + brief → storyboard → edycja scen → kontrola jakości → eksport wariantów**.

Wszystkie etapy realizowane są przy zachowaniu nadrzędnych założeń:
1. Brak zewnętrznych zależności chmurowych i obowiązkowych abonamentów — 100% lokalne przetwarzanie.
2. Zachowanie istniejącego stacku (Python, Playwright, Chromium, FFmpeg, GSAP, HTML/CSS) oraz interfejsów (CLI, MCP, Dashboard).
3. Wspólny rejestr operacji (`vstudio/registry.py`) jako jedyne źródło prawdy dla CLI, agenta (MCP) i Dashboardu.
4. Nienaruszalność architektury bezpieczeństwa: izolacja scen w piaskownicy (iframe sandbox without same-origin) i determinizm renderowania klatek.

---

## Przegląd Etapów

| Etap | Zakres | Status |
|---|---|---|
| **Etap 0** | Audyt, naprawa regresji środowiskowych (Windows/Playwright/Subprocess), stabilizacja testów | **Zrealizowany (v0.2)** |
| **Etap 1** | Wiele niezależnych marek, profile kreatywne, tryby tekstu, migracja i spójny przepływ | **Zrealizowany (v0.2)** |
| **Etap 2** | Biblioteka materiałów i lokalny menedżer mediów (Asset & Media Manager) | Zaplanowany (v0.3) |
| **Etap 3** | Wizualny inspektor scen i interaktywny storyboarder | Zaplanowany (v0.4) |
| **Etap 4** | Automatyczny eksport wariantów wieloformatowych i paczek wydawniczych | Zaplanowany (v0.5) |
| **Etap 5** | Zaawansowana synchronizacja rytmiczna audio-motion i detekcja transjentów | Zaplanowany (v0.6) |

---

## Szczegółowy opis etapów

### Etap 0: Audyt, stabilizacja i testy regresji (Zrealizowany)
- [x] Audyt środowiska i narzędzi (`python vstudio.py doctor`, `pytest`).
- [x] Usunięcie problemów wieloplatformowych na Windowsie (obsługa ścieżek POSIX/Win32 w `resolve_project`, subprocess `creationflags` zamiast Uniksowego `sleep`, jawne kodowanie UTF-8 przy obsłudze polskich znaków).
- [x] Utworzenie dokumentu audytu `docs/UPGRADE_AUDIT.md`.
- [x] Zapewnienie 100% przechodzenia dotychczasowej bazy testowej.

### Etap 1: Niezależne marki i profile kreatywne (Zrealizowany)
- [x] **Biblioteka marek (`vstudio/brands.py`)**:
  - Obsługa wielu niezależnych marek z własnymi paletami, fontami, wytycznymi logo, tonem i ograniczeniami kreatywnymi.
  - Bezstratna migracja ze starszego `profile.json` do `output/.studio/brands.json` z zachowaniem wstecznej kompatybilności.
  - Wersjonowanie konfiguracji marki (`version`).
  - Niezmienne migawki marki w projektach (`brand_snapshot` w `project.json`) gwarantujące, że edycja marki w studiu nie modyfikuje renderów istniejących projektów.
- [x] **Profile kreatywne i tryby tekstu**:
  - Wprowadzenie 4 profili: `premium_minimal`, `cinematic`, `social_fast`, `educational`.
  - Wprowadzenie 3 trybów tekstu: `none`, `headline_only`, `full`.
  - Obsługa reguł minimalizmu dla `premium_minimal`: tłumienie automatycznych naklejek/ikon, preferencja spójnego świata wizualnego bez wymuszonego żonglowania stylami, dopuszczenie spokojnych zatrzymań (do 7.0 s) bez fałszywych ostrzeżeń `SLOW_PACE`.
  - Wsparcie dla filmów bez tekstu (`text_mode: "none"`) bez zgłaszania `NO_HOOK_TEXT`.
  - Weryfikacja minimalnego czasu czytania dla profilu `educational`.
- [x] **Pełna integracja przepływu**:
  - Rejestracja możliwości w `vstudio/ops.py` (`brands_list`, `brand_get`, `brand_set`, `brand_activate`, `brand_delete`, `creative_profiles_list`).
  - Rozszerzenie `project_create` i `director_plan` o profile kreatywne i tryby tekstu.
  - Udostępnienie widoku `Marki i profile` oraz formularzy tworzenia i planowania w Dashboardzie.
  - Aktualizacja bazy wiedzy agenta (`vstudio/knowledge.py`), dokumentacji możliwości (`docs/CAPABILITIES.md`) oraz definicji skilla (`skills/vstudio/SKILL.md`).

---

### Etap 2: Biblioteka materiałów i lokalny menedżer mediów (Kolejna iteracja)
**Cel:** Umożliwienie klientom i agentom łatwego importu, katalogowania oraz bezpiecznego używania lokalnych materiałów (wideo b-roll, zdjęcia produktowe, SVG, audio) w obrębie marki i projektów.

- **Kluczowe moduły do wdrożenia**:
  1. `vstudio/media.py`: indeksowanie plików w `brands/<brand_id>/media/` oraz `output/<project>/assets/`.
  2. Automatyczna ekstrakcja metadanych: rozdzielczość, proporcje (aspect ratio), czas trwania, kodek, obecność kanału alpha, profil kolorów.
  3. Generowanie lekkich miniatur i podglądów wideo w tle dla dashboardu (webp / mp4 proxy).
  4. Analiza palety kolorów z importowanych obrazów (wyciąganie dominanty kolorystycznej zgodnej z marką).
  5. Narzędzie `media_import` w rejestrze operacji z weryfikacją poprawności formatów bez konieczności wychodzenia do zewnętrznych bibliotek.

---

### Etap 3: Wizualny inspektor scen i interaktywny storyboarder
**Cel:** Przejście z deklaratywnego tekstu do pełnej interaktywnej kontroli nad ujęciami i parametrami animacji.

- **Kluczowe moduły do wdrożenia**:
  1. Wizualny edytor bloków storyboardu w dashboardzie — możliwość przesuwania granic beatów (zmiana czasów startu/końca ujęć metodą drag & drop).
  2. Dynamiczny inspektor parametrów sceny (Inspektor właściwości CSS/GSAP zmienianych w czasie rzeczywistym).
  3. Przełącznik nakładek Safe-Zone dla platform (Instagram Reels, TikTok, YouTube Shorts z oznaczeniem stref zasłoniętych przez interfejsy aplikacji mobilnych).
  4. Narzędzie porównawcze A/B klatek kluczowych: porównanie dwóch wariantów stylu na tej samej klatce czasowej w trybie kurtyny (split slider).

---

### Etap 4: Automatyczny eksport wariantów wieloformatowych i delivery
**Cel:** Masowe generowanie gotowych plików emisyjnych z jednego zatwierdzonego projektu źródłowego.

- **Kluczowe moduły do wdrożenia**:
  1. Uniwersalny silnik responsywnego kadrowania sceny (`responsive stage adapter`) — adaptacja sceny do 9:16, 1:1, 16:9, 4:5 z zachowaniem marginesów bezpieczeństwa.
  2. Wieloformatowy runner zadań renderowania w tle: równoległe lub kolejkowe generowanie wariantów docelowych.
  3. Moduł lokalizacji i wariantów językowych: podmiana plików napisów (SRT/VTT) oraz ścieżek lektora z zachowaniem zsynchronizowanych zdarzeń animacji.
  4. Paczka wydawnicza (`delivery_bundle`): zip zawierający wersje Master (wysoki bitrate), Social (zoptymalizowany pod limity platform), miniatury plakatów (posters) oraz automatycznie generowany raport licencyjny `CREDITS.md`.

---

### Etap 5: Zaawansowana synchronizacja rytmiczna audio-motion
**Cel:** Profesjonalny feeling montażu teledyskowego / dynamicznego dzięki sprzężeniu ruchu z podkładem muzycznym.

- **Kluczowe moduły do wdrożenia**:
  1. Analizator audio offline oparty o FFmpeg / numpy: wykrywanie uderzeń (onsets, beat tracking, tempo BPM).
  2. Automatyczne przyciąganie cięć storyboardu (`beat snapping`) do siatki muzycznej.
  3. Rozszerzenie silnika zdarzeń dźwiękowych (`vstudio/audio.py`): parametryczna synteza i miksowanie dźwięków SFX z regulacją tonu (pitch), tłumienia (decay) i pogłosu.
  4. Wizualizacja fali dźwiękowej (waveform) bezpośrednio pod osią czasu dashboardu.
