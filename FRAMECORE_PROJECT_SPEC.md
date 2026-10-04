# Format projektu FrameCore — schemat 1

Projekt jest zapisany jako JSON UTF-8. Czas podajemy w sekundach, geometrię w pikselach obszaru filmu. Identyfikatory są stałe, `revision` rośnie przy każdej zmianie treści. Komendy wymagają `expected_revision`; konflikt nie zmienia treści ani historii.

| Pole | Znaczenie |
| --- | --- |
| `id`, `schemaVersion`, `revision` | Tożsamość, wersja schematu, rewizja |
| `metadata` | Nazwa, brief, kierunek filmu i daty |
| `canvas` | Szerokość, wysokość, FPS, tło |
| `duration` | Długość projektu, do 600 sekund |
| `assets` | Lokalne materiały z pochodzeniem i licencją |
| `scenes` | Plan scen z tekstem, intencją ruchu i dźwięku |
| `tracks` | Ścieżki wideo, obrazów, kształtów, tekstów, napisów i audio |
| `elements` | Klipy i obiekty kompozycji |
| `brand` | Nazwa, kolory, font, logo i ustawienia marki |
| `exportProfiles` | Dostępne proporcje obrazu |

Sesja (`selection`, `playhead`), historia i propozycje znajdują się obok projektu w `state.json`. Zmiany sesji nie są krokami cofania treści.

Materiał zawiera `id`, `name`, `kind`, lokalny `file` w `assets/`, `mime`, `duration`, `provenance`, `license`. Źródła wideo z dźwiękiem mają `hasAudio`. Materiały nie wskazują dowolnych plików systemowych ani adresów zdalnych. Ikony z biblioteki mają pochodzenie `phosphor_builtin` i identyfikator z zamkniętego katalogu.

Scena ma `id`, `name`, `start`, `duration`, `message`, `visualPurpose`, `motionIntent`, `audioIntent`. Ścieżka ma `id`, `name`, `kind`, `muted`, `hidden`, `locked`; kolejność ścieżek określa nakładanie obrazu.

Element zawiera `id`, `sceneId`, `trackId`, `type`, `assetId`, `text`, `start`, `duration`, `sourceStart`, `x/y/width/height`, `scale`, `rotation`, `opacity`, `style`, `motion`, `effects`, `keyframes` i opcjonalne `audio`. Zakres klipu to `[start, start+duration)`. Podział przesuwa początek źródła, zachowuje fazę animacji i interpoluje klatki na granicy cięcia.

## Klatki kluczowe

Lista `keyframes` zawiera obiekty `{"property":"x","time":0,"value":100}`. Obsługiwane właściwości: `x`, `y`, `rotation`, `scale`, `opacity`. Czas jest lokalny względem początku klipu, w zakresie 0–duration. Przed pierwszym i po ostatnim punkcie wartość pozostaje stała; między punktami stosujemy interpolację liniową. Nie może być dwóch punktów tej samej właściwości w tym samym czasie. Limit to 200 punktów na element.

Animacja semantyczna `motion` działa ponad tymi wartościami. Niestandardowe `effects` nie są jeszcze obsługiwane i powodują błąd, zamiast znikać po cichu.

## Dźwięk

Klip audio może mieć `audio: {"gain":0.8,"fadeIn":0.5,"fadeOut":1}`. Głośność to 0–1; czasy wyciszeń nie przekraczają długości klipu. Wyciszenie ścieżki pomija jej klipy w eksporcie. Wideo z dźwiękiem może być źródłem osobnego elementu audio.

## Walidacja i zapis

Odrzucamy NaN, nieskończoność, powtórzone identyfikatory, brakujące referencje, błędne ścieżki, nieznane animacje i właściwości. Historia zawiera aktora, opis, komendę oraz stan przed i po zmianie. Zapis jest atomowy, chroniony blokadą między procesami.

Zmiana formatu skaluje geometrię, rozmiar tekstu i klatki pozycji. Eksport zamraża rewizję. Bezpośrednia edycja pliku stanu omija walidację i historię, dlatego do edycji używaj komend. Nieznane wersje schematu są odrzucane; migracje wymagają osobnej implementacji.
