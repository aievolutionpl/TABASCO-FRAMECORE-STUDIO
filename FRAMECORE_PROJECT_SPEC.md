# Format projektu FrameCore — schemat 1

Projekt jest zapisany jako JSON UTF-8. Czas podajemy w sekundach, geometrię w pikselach obszaru filmu. Identyfikatory są stałe, `revision` rośnie przy każdej zmianie treści. Komendy wymagają `expected_revision`; konflikt nie zmienia treści ani historii.

| Pole | Znaczenie |
| --- | --- |
| `id`, `schemaVersion`, `revision` | Tożsamość, wersja schematu, rewizja |
| `metadata` | Nazwa, brief, kierunek filmu i daty |
| `canvas` | Szerokość, wysokość, FPS, tło i opcjonalne `fx` (look filmu) |
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

## Ruch 2.0: wejścia, wyjścia, wygląd i look filmu

`motion` to `{"id","duration","easing"}`; czas 0,1–4 s. Animacje rodzaju `kinetic` (np. `type-on`, `char-rise`, `word-highlight`) działają tylko dla tekstu i napisów i animują każde słowo lub literę. Opcjonalne `exit: {"id","duration","easing"}` (0,1–2 s) działa w ostatnich sekundach klipu; krzywa wyjścia jest odbiciem krzywej wejścia. Krzywe: `linear`, `quad-out`, `cubic-out`, `quint-out`, `expo-out`, `back-out`, `elastic-out`, `cubic-in-out`. Podział klipu zostawia wyjście tylko na drugiej części.

`style` może zawierać: `shadow` (`none`, `soft`, `lift`, `glow`, `neon`, `long`), `shadowColor`, `gradient` (`{"from":"#hex","to":"#hex","angle":0–360}` albo `null`), `letterSpacing` (−50–200 px), `strokeWidth` (0–40 px), `strokeColor`, `blend` (`normal`, `screen`, `multiply`, `overlay`, `soft-light`, `lighten`, `difference`) i `fit` (`contain`, `cover`) dla obrazów i wideo. `style.emphasis` (`{"word","color","marker","emojiElementId"}`) podkreśla jedno słowo tekstu w chwili jego pojawienia się; `emojiElementId` wskazuje powiązany klip emoji, który `emphasize_text` usuwa razem z podkreśleniem. To zamknięte słowniki — projekt nie przenosi dowolnego CSS.

`canvas.fx` opisuje look całego filmu: `grade` (`none`, `cinematic`, `warm`, `cool`, `mono`, `vivid`, `faded`, `noir`), `vignette` 0–1, `grain` 0–1, `letterbox` 0–0,25 wysokości kadru, `transition` (`none`, `dip`, `flash`, `wipe`, `light-leak`, `blur`) na cięciach między scenami, `transitionDuration` 0,1–2 s i `motionBlur` (rozmycie ruchu w finalnym eksporcie: 4 podklatki, migawka 180°). Scena może mieć własne `transition: {"id","duration"}` dla cięcia na swoim początku (pierwszeństwo przed `canvas.fx`). Przejścia ✦ `domain-warp`, `ridged-burn`, `whip-pan`, `sdf-iris`, `cinematic-zoom`, `glitch`, `chromatic-split`, `cross-warp` nakładają sceny: klipy zaczynające się na cięciu startują o `duration/2` wcześniej, a kończące się na cięciu trzymają ostatnią klatkę o `duration/2` dłużej (ich wyjście jest pomijane). Wszystkie efekty są funkcją czasu filmu, więc podgląd i eksport są identyczne. Szczegóły: [docs/MOTION_2.md](docs/MOTION_2.md).

## Dźwięk

Klip audio może mieć `audio: {"gain":0.8,"fadeIn":0.5,"fadeOut":1}`. Głośność to 0–1; czasy wyciszeń nie przekraczają długości klipu. Wyciszenie ścieżki pomija jej klipy w eksporcie. Wideo z dźwiękiem może być źródłem osobnego elementu audio.

## Walidacja i zapis

Odrzucamy NaN, nieskończoność, powtórzone identyfikatory, brakujące referencje, błędne ścieżki, nieznane animacje i właściwości. Historia zawiera aktora, opis, komendę oraz stan przed i po zmianie. Zapis jest atomowy, chroniony blokadą między procesami.

Zmiana formatu skaluje geometrię, rozmiar tekstu i klatki pozycji. Eksport zamraża rewizję. Bezpośrednia edycja pliku stanu omija walidację i historię, dlatego do edycji używaj komend. Nieznane wersje schematu są odrzucane; migracje wymagają osobnej implementacji.

## Tła i materiały biblioteki

`canvas.backgroundPreset` zawiera identyfikator z `list_backgrounds`; opcjonalne `backgroundAnimated` pozwala zamrozić ruch w czasie 0. `background` zachowuje jednolity kolor bazowy. Receptury są zamkniętym katalogiem kodu, bez dowolnego CSS w JSON.

Wbudowane ikony i ilustracje mają `provenance.source: framecore_builtin` oraz `library_id`, kolekcję, commit i SHA-256. Pliki trafiają do lokalnego `assets/`. Ikony mają rolę `icon` i kolorowanie maską; ilustracje zachowują kolory PNG. Eksport osadza użyte fonty z audytowanego katalogu. `metadata.templateId` opisuje użyty kierunek wizualny.
