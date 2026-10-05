# Audyt i plan rozwoju AI Studio — etap 1

## Stan zweryfikowany

- **Core:** `model`, `commands`, `store` i `api` tworzą wspólną granicę zmian. Atomowy zapis, blokady między procesami, expected_revision, propozycje i undo są już dostępne. Zachowujemy format istniejących projektów.
- **Legacy:** FrameCore importuje locking, transport MCP i handler HTTP z vstudio; renderer HTML także mieszka w legacy. Nie należy przenosić całego renderera i transportów jednocześnie. Pierwszy bezpieczny krok to własna infrastruktura zapisu i niezależny import mediów.
- **UI:** vanilla JS + Hyperframes; agent, marki i produkcja mają osobne moduły. `studio.js` nadal łączy bibliotekę, canvas, timeline i inspector. Rozdzielamy je stopniowo przez jawnie przekazywane zależności.
- **Timeline/motion:** są zaznaczenie wielu elementów, podstawowe przesuwanie, trim/split, ścieżki, liniowe keyframes i 28 animacji. Brakuje pełnej semantyki ripple/roll/slip/slide, linków A/V, markerów i edytora krzywych. Wszystkie nowe operacje muszą być komendami transakcyjnymi.
- **Media/audio:** import sprawdza typ i czas; brak trwałych pochodnych: thumbnails, contact sheets, proxy, waveform i stanu analizy. Oryginały muszą pozostać niezmienne. Podstawowy gain/fades istnieje; brak analizy ciszy, beatów i duckingu.
- **Transkrypcja/providers:** registry providerów jest szkieletem; brak gotowego edytora transkryptu i kontraktu word timestamps/speakers. Nie przedstawiamy deklaracji capability jako działającej integracji.
- **Agenci:** rozmowa tool-calling i dashboard zadań są odrębnymi usługami. Dashboard obsługuje proposals; rozmowa może wykonywać komendy. Brak wspólnego orkiestratora ról. API i rewizje pozostają jedyną drogą zapisu projektu.
- **Visual feedback:** capture_frame, review i motion evidence istnieją, lecz obecna rozmowa nie przekazuje modelowi obrazów. Potrzebny jawny kontrakt multimodalny oraz limity i zgoda na wysłanie mediów.
- **Company Brain:** wersjonowane profile, logo/referencje, snapshot projektu i SHA-256 istnieją. Brak pełnego egzekwowania reguł Brand Guardian i oceny podobieństwa wizualnego.
- **Rendering:** deterministyczne HTML/Chromium → FFmpeg, zamrożona rewizja i raporty jakości. Brakuje cache klatek/renderów oraz bezpiecznego rozróżnienia proxy preview i final export.
- **CI/testy:** istnieją testy jednostkowe, HTTP, MCP, Playwright i rzeczywistych eksportów. CI uruchamiał tylko Ubuntu; Windows wymaga UTF-8, FFmpeg i przeglądarki z kodekami.

## P0 — ten etap

1. Przenieść locking/atomic write do FrameCore, zachować kompatybilny import w vstudio. Oddzielić import mediów od transportu HTTP.
2. Media Engine: jawnie uruchamiana analiza materiału, metadata, thumbnail, contact sheet, proxy video, waveform i cisza; SHA-256/version cache; queued/running/ready/failed; bez mutacji dokumentu projektu. Ograniczyć zasoby i walidować ścieżki.
3. Udostępnić analizę przez wspólne API/MCP oraz osobny moduł UI. Stare projekty analizują się na żądanie, bez migracji. Pokazywać prawdziwy stan i błędy, nie udawać gotowości.
4. Macierz CI Linux + Windows, regresje mediów i kompatybilności; zachować wszystkie istniejące testy.

## P1 — kolejne etapy, jeszcze nie zaimplementowane

- Transakcyjne ripple/roll/slip/slide, linked A/V, markers; snapping do krawędzi, playhead i beatów. Testy granic źródła, kolizji ścieżek, proposal/revision/undo.
- Transcript Editor: neutralny format słów/speakerów, provider transkrypcji, klik → playhead, skreślenie → propozycja cięć. Tekst nie może sam zmieniać timeline.
- Provider Engine: capability/schema, jobs/cancel/errors, provenance i koszty; image/edit/video/image-to-video/voice/transcription/music/SFX. Generowanie z zaznaczenia przez proposal, po imporcie wyniku jako asset.
- Director koordynuje zadania Editor/Media/Sound/Brand/QA, każdy z ograniczonym zestawem narzędzi; konflikt rewizji wymaga ponownego planu. Model nigdy nie otrzymuje prawa zapisu state.json.
- Visual feedback: rzeczywiste capture/review jako obrazy, jawne wysłanie, wnioski powiązane z czasem i rewizją.
- Brand Guardian: deterministyczne reguły fontów/kolorów/logo/ilości tekstu/zakazów oraz osobna ocena referencji przez model.
- Easing i krzywe: linear/in/out/in-out/bezier/spring, wspólna ewaluacja preview/export oraz fundament Graph Editor.

## P2 — wydajność i konsolidacja

- Włączenie proxy playback z jawną etykietą jakości; eksport zawsze z oryginałów.
- Beat detection i automatic ducking jako propozycje zmian audio.
- Cache klatek/renderów po hashu projektu, assetów, fontów i wersji renderera. Incremental render dopiero po testach równoważności na granicach efektów/audio.
- Dalsze wydzielanie timeline/canvas/inspector/audio/captions z studio.js, bez zmiany frameworka.
- Dopiero po pokryciu kontraktów: własne transporty HTTP/MCP i stopniowe przeniesienie renderera z vstudio.

Każdy etap: kod, regresje, dokumentacja i otwieranie starych projektów. To plan etapowy, a nie deklaracja ukończenia wszystkich 14 obszarów.
