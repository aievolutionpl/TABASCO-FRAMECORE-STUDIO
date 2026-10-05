# Media Engine — etap P0

## Obsługa

W zakładce **Materiały** lub **Dźwięk** wybierz **Analiza materiałów**, wskaż plik i naciśnij **Analizuj materiał**. Analiza działa w tle. Panel pokazuje stan, metadane, miniaturę, sześć klatek wideo, link do proxy oraz waveform z liczbą odcinków ciszy. Ponowne uruchomienie wykorzystuje poprawny cache. Błąd można ponowić.

Analiza jest uruchamiana jawnie: import nadal szybko waliduje plik, ale nie rozpoczyna automatycznie kosztownego transkodowania całej biblioteki. Stare projekty nie wymagają migracji.

## Kontrakt API i MCP

Te same narzędzia są dostępne przez `API.call`, HTTP `POST /api/command` oraz MCP `tools/call`:

```json
{"name":"analyze_media","args":{"project_id":"fc_…","asset_id":"asset_…"}}
```

Następnie odpytuj `get_media_analysis` z tymi samymi argumentami. Stany: `not_started`, `queued`, `running`, `ready`, `failed`. Raport zwraca SHA-256 źródła, metadata, listę plików z hashami i lokalne URL. Wbudowany agent może zlecić analizę i odczytać raport; analiza nie wysyła materiałów do zewnętrznego API.

Narzędzia nie zmieniają projektu, nie wymagają `expected_revision` i nie tworzą wpisów undo. Zastosowanie wyników do montażu nadal wymaga FrameCore Commands, rewizji i — zależnie od przepływu — proposal. HTTP zachowuje istniejące zabezpieczenia Host/Origin/token. Pliki pochodne obsługuje `/media/<project>/<asset>/<filename>`; tylko gotowe wyniki z jawnej listy nazw.

## Pliki i kompatybilność

Cache: `output/.framecore/<project>/.media-cache/<hash>/`. Klucz zawiera SHA-256 oryginału, typ materiału i wersję algorytmu. Manifest `analysis.json` jest zapisywany atomowo. Brak lub zmiana pliku wynikowego unieważnia cache. Oryginały, schema projektu i eksport finalny nie zmieniają się. Hashowanie jest memoizowane po ścieżce, rozmiarze oraz czasach modyfikacji/zmiany pliku; nie wczytujemy ponownie całego źródła przy każdym odpytywaniu.

- Zdjęcia: rozmiar po uwzględnieniu orientacji EXIF, format, liczba bajtów i JPEG do 640 px.
- Wideo: informacje o strumieniach, sześć równomiernie rozłożonych klatek, contact sheet 960×360, proxy H.264/AAC do 640×640.
- Audio i ścieżka audio wideo: mono 8 kHz do analizy, do 1200 wartości szczytowych, odcinki RMS poniżej −40 dB przez co najmniej 0,3 s.

Limity: dwa równoległe zadania, maksymalnie 16 zadań w kolejce/wykonaniu w procesie, materiał do 60 minut, limit czasu podprocesów. Stan zadania starszy niż 15 minut uznawany jest za przerwany; można go ponowić. Cache nie jest automatycznie usuwany. Brak FFmpeg/FFprobe daje jawny błąd. Dane o ciszy są heurystyką, a nie rozpoznaniem mowy.

## Granice etapu

Proxy można obejrzeć, ale podgląd timeline nadal korzysta z oryginałów. Nie dodano jeszcze beat detection, duckingu, rozpoznawania voice/music, transkrypcji ani renderowania przyrostowego. Te funkcje mają osobne etapy w [audycie](AI_STUDIO_AUDIT.md).

`framecore.persistence` jest właścicielem blokad i atomowego zapisu; `vstudio.locking` pozostaje zgodnym re-eksportem tych samych funkcji. `framecore.media_import` jest właścicielem importu; dotychczasowy `framecore.server.import_asset` pozostaje dostępny. Transport HTTP/MCP i renderer legacy są zachowane.

Regresje: `tests/test_framecore_media.py` obejmuje prawdziwy FFmpeg, cache, niezmienność projektu, błędy, ścieżki i panel przeglądarkowy. CI uruchamia cały dotychczasowy zestaw na Ubuntu i Windows z UTF-8; każdy system publikuje raport JUnit.

## Walidacja lokalna

Pełny przebieg na Windows: 305 przypadków, 282 zaliczone, 23 pominięte przez warunki środowiska (m.in. lokalny GSAP), 0 błędów i 0 niepowodzeń. Nowy zestaw sześciu regresji Media Engine przeszedł także osobno. Wyniki macierzy CI należy sprawdzać dla konkretnego SHA, a nie wnioskować z samej konfiguracji workflow.

Pierwszy przebieg macierzy ujawnił natywny błąd zamykania Pythona na ruchomym obrazie Ubuntu (305/305 testów zaliczonych przed błędem procesu) oraz problemy z marginesami/kolizjami fontów w dwóch szablonach legacy na Windows. CI przypięto do Ubuntu 24.04 i Windows 2022, włączono faulthandler i pomiar czasu testów. Szablony zachowują sceny i animacje, ale mają większy zapas wokół dużych cyfr i długich napisów. Regresje nadzorcy i reżysera pozostają obowiązkowe.

Dalsza regresja Windows wykazała przycinanie słów w masce kinetycznej i kolizję zawijanych napisów. Zwiększono odstęp wierszy w motion-kit i zmniejszono tekst wewnątrz maski; wszystkie 49 lokalnych testów formatów rolek z GSAP przeszło po tej zmianie.
