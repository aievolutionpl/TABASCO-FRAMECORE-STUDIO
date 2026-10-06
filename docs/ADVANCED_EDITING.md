# Szybszy montaż: grupy, źródło i dźwięk

Nowe narzędzia MotionDuo rozwijają wspólny montaż człowieka i agenta. [Źródło inspiracji i zakres przeglądu Concat](CONCAT_REVIEW.md).

## Wybierz fragment przed wstawieniem

W panelu **Media** kliknij **Zakres / podgląd** pod materiałem. Otwiera się monitor oryginału. Wideo i dźwięk mają pola IN/OUT w sekundach, przyciski ustawiania punktów w aktualnym miejscu odtwarzania oraz **Odtwórz zakres**. Skróty **I** i **O** działają poza polami formularza.

**Wstaw wybrany fragment** dodaje materiał przy wskaźniku timeline. Dla wideo z dźwiękiem możesz zostawić zaznaczone **Dodaj też dźwięk na osobnej ścieżce**. Oba klipy otrzymują ten sam początek, długość i zakres źródła. Całą operację cofniesz jednym kliknięciem. Obraz i dźwięk pozostają osobno edytowalne; nie tworzymy trwałego połączenia między nimi. Wstawianie nie wydłuża filmu automatycznie.

## Zaznacz i edytuj kilka klipów

**Ctrl / ⌘ / Shift + klik** dodaje lub usuwa klip z zaznaczenia. Przeciągnięcie zaznaczonego klipu przesuwa całą grupę o ten sam czas, zachowując odstępy i ścieżki. Ruch jest ograniczony początkiem i końcem filmu.

W panelu **Właściwości** znajdziesz przesunięcie o podaną liczbę sekund, duplikowanie, podział przy wskaźniku i usunięcie grupy. Kopie domyślnie zaczynają się za zakresem całej grupy; jeśli nie mieszczą się w filmie, operacja zostaje odrzucona. **S** dzieli tylko zaznaczone klipy przecinające wskaźnik. **Delete** usuwa zaznaczenie, **Shift + Delete** dodatkowo zsuwa późniejsze klipy na każdej objętej operacją ścieżce.

Grupa tekstów i napisów ma wspólne ustawienia fontu, rozmiaru i koloru. Grupa elementów wizualnych ma wspólny look klipu. Pola początkowo pokazują wartość pierwszego klipu; zmiana nadaje ją wszystkim zaznaczonym. Zablokowana ścieżka lub niepoprawna wartość odrzuca całą operację. Każda operacja grupowa tworzy jeden krok cofania.

## Montaż magnetyczny

Na pasku timeline włącz **Magnetyczny**. Przeciąganie krawędzi zmienia długość klipu i zsuwa późniejsze klipy na tej samej ścieżce. Przy lewej krawędzi początek na osi pozostaje zakotwiczony, a zakres nagrania przesuwa się w źródle. Klatki kluczowe i czasy fade są przeliczane. Pozostawione wcześniej luki zachowują długość.

Przełącznik włącza także zsuwanie przy **Delete**. Nie przesuwa pozostałych ścieżek, scen ani końca filmu. Jeśli przycinasz obraz z osobnym audio, zadbaj o ich synchronizację. Klipy nachodzące na siebie blokują zsuwanie. **Przyciąganie** to osobny przełącznik: pomaga trafiać w granice klipów i wskaźnik. Gesty bez przyciągania zaokrąglają czas do klatki projektu.

## Rzeczywisty waveform

Klipy audio pokazują amplitudy oryginału, przycięte do `sourceStart` i długości klipu. Wykres uwzględnia głośność i fade. Przeciągaj poziomą linię w górę lub w dół, aby zmieniać głośność 0–100%; wartość i fade można też wpisać we Właściwościach.

Pierwsza analiza odbywa się lokalnie w tle. Miniatury, proxy i waveform są buforowane według SHA-256 poza dokumentem projektu, więc nie zmieniają rewizji ani oryginału. Wykres jest uproszczonym zestawem maksymalnie 1200 szczytów amplitudy; nie zastępuje odsłuchu. Przy nieudanej analizie klip nadal pozostaje edytowalny. [Silnik analizy mediów](MEDIA_ENGINE.md).

## Komendy dla agenta

Każda zmiana wymaga `project_id` i bieżącej `expected_revision`. Po konflikcie odczytaj projekt ponownie. Podawaj jawne `element_ids`, aby operacja miała określony zakres.

| Komenda | Główne argumenty |
| --- | --- |
| `move_clips` | `element_ids`, `delta` w sekundach |
| `duplicate_clips` | `element_ids`, opcjonalny `delta` |
| `split_clips` | `element_ids`, `time` w sekundach filmu |
| `delete_clips` | `element_ids`, `ripple` (domyślnie false) |
| `set_clip_properties` | `element_ids`, `properties`, np. `{"style.fontFamily":"Manrope","style.color":"#00aabb"}` |
| `magnetic_trim` | `element_id`, `edge: "start"` lub `"end"`, `delta` w sekundach |
| `insert_media_range` | `asset_id`, `source_start`, `source_end`, `start`, `include_audio` |
| `get_audio_waveform` | Odczyt: `asset_id`, `source_start`, `duration`, `points` 1–1200. Najpierw `analyze_media` i status ready. |

Propozycja może łączyć te operacje przez `propose_changes`. Dashboard zamraża zaznaczenie przed wysłaniem zadania do modelu; późniejszy klik człowieka nie zmienia celu rozpoczętej edycji.

## Sprawdzenie

Testy nowych funkcji obejmują rzeczywisty H.264/AAC z różnym obrazem i dźwiękiem przed i po punkcie IN, amplitudy wybranego zakresu, eksport MP4, gesty grupy, przycinanie magnetyczne, linię głośności, cofanie, blokady, odrzucenie niepoprawnych zakresów oraz zamrożenie zaznaczenia agenta. Interfejs sprawdzono także przy szerokościach 320, 390 i 900 px.
