# Przejścia, efekty i precyzyjny montaż MotionDuo

## Efekty i przejścia

W lewym menu otwórz **Efekty**. Zaznacz klip, wybierz look i ustaw siłę od 0 do 100%. Naturalny, Złota godzina, Chłodny błękit, Noir, Vintage, Żywy kontrast i Miękki sen działają lokalnie. Look łączy się z wejściem, wyjściem i kolorem całego filmu; efekt klipu nie zmienia materiału źródłowego. Na klipie pojawia się oznaczenie **FX**.

Przejścia obejmują cięcie, przejście przez czerń, błysk, kurtynę marki, smugę światła, rozmycie, przysłonę, kurtynę ukośną, zoom z rozmyciem, kurtynę pionową i mozaikę. Wybierz scenę i czas 0,1–2 s. **Podgląd przejścia** odtwarza fragment wokół początku sceny. **Użyj ustawień filmu** usuwa lokalną zmianę. Wybranie **Cięcie** wyłącza przejście dla tej sceny nawet wtedy, gdy cały film ma inny domyślny efekt.

Przejścia zasłaniają lub stylizują cięcie między scenami; nie są crossfade dwóch nakładających się nagrań. Nie wymagają dodatkowych klatek przed lub po wyciętym zakresie. Krótkie sceny mogą mieć nakładające się okna przejść — silnik wybiera najbliższe cięcie. Pierwsza scena nie ma przejścia wejściowego. Zmiany działają w podglądzie i w MP4, a przewijanie jest deterministyczne.

## Timeline

Pasek scen nad ścieżkami pokazuje granice i pozwala przejść do sceny kliknięciem. Wybierz klip i otwórz **Narzędzia** na pasku timeline lub **Szybki montaż** we Właściwościach:

- **Przytnij początek/koniec do wskaźnika**: wskaźnik musi znajdować się wewnątrz klipu. Przycinanie zachowuje poprawny zakres źródła i przelicza klatki kluczowe.
- **Usuń i zsuń kolejne**: usuwa zaznaczony klip i przesuwa późniejsze klipy na tej samej ścieżce o jego długość. Istniejące luki pozostają. Skrót: **Shift + Delete**.
- **Usuń luki na ścieżce**: układa klipy kolejno od 0 s, zachowując ich długości, animacje i zakres źródła.
- **Zmień zakres źródła**: wybiera inny fragment tego samego wideo lub dźwięku, zachowując miejsce i długość klipu w filmie.

Zsuwanie działa na jednej ścieżce. Nie przesuwa pozostałych ścieżek ani planu scen i nie skraca projektu. Jeśli potrzebujesz synchronizacji obrazu z osobną narracją, przesuń obie ścieżki świadomie. Nakładanie klipów blokuje zsuwanie; zablokowane ścieżki blokują edycję. Każda operacja jest jednym krokiem historii **Cofnij / Ponów**.

Na mniejszych ekranach pasek narzędzi można przewijać poziomo, a panel Efekty otwiera się jako osobne okno.

## Te same narzędzia dla agenta

Agent powinien odczytać projekt, zaznaczenie i `list_editing_presets`. Dostępne komendy:

| Komenda | Argumenty |
| --- | --- |
| `set_clip_fx` | `element_id`, `fx: {look: "noir", strength: 0.5}` |
| `set_scene_transition` | `scene_id`, `transition: {id: "iris", duration: 0.8}` lub `null` |
| `ripple_delete` | `element_id` |
| `close_track_gaps` | `track_id` |
| `slip_clip` | `element_id`, `source_start` |

Zmiany wymagają `project_id` i aktualnej `expected_revision`. Większy montaż można przedstawić przez `propose_changes`; zastosowanie propozycji jest atomowe i trafia do wspólnej historii. Niepoprawny efekt, zakres źródła lub zablokowana ścieżka odrzuca zmianę bez zapisywania częściowego montażu.

## Weryfikacja

Testy obejmują historię cofania i propozycje agenta, granice źródła, blokady ścieżek, odrzucanie nakładania klipów, piksele każdego przejścia oraz powtarzalność przewijania. Interfejs sprawdzono na komputerze i telefonie. [Film demonstracyjny 8 s](../assets/motionduo-effects-demo.mp4) został wyeksportowany przez rzeczywisty silnik do H.264, 640 × 360, 24 FPS; używa wbudowanego banneru MotionDuo, własnych przejść scen i czterech looków klipów. Demo jest bez ścieżki audio. [Klatki z MP4](../assets/motionduo-effects-demo-frames.jpg).
