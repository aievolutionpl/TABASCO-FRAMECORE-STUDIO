# Co przenosimy z pomysłów Concat do MotionDuo

Przegląd [jub0t/Concat](https://github.com/jub0t/Concat) wykonano 6 października 2026 dla commitu [`7b5cc44bc5c58838967e5f9c511e9f0ae3c9929c`](https://github.com/jub0t/Concat/tree/7b5cc44bc5c58838967e5f9c511e9f0ae3c9929c). Sprawdzono README, architekturę, changelog, opisy komend montażowych, timeline i analizę amplitudy audio.

Concat to natywny edytor w Rust z własnym silnikiem odtwarzania i renderowania. Dla MotionDuo najcenniejsze są krótkie, przewidywalne operacje montażowe, które mogą wykonywać zarówno człowiek, jak i agent.

| Rozwiązanie w Concat | Implementacja w MotionDuo |
| --- | --- |
| Wielokrotne zaznaczanie i wspólne operacje | Ctrl / ⌘ / Shift + klik, przeciąganie grupy, duplikowanie, podział, usuwanie oraz wspólne fonty, kolor i look. Jedna operacja oznacza jeden krok cofania. |
| Przycinanie magnetyczne i usuwanie ze zsuwaniem | Przełącznik **Magnetyczny**, zakotwiczony początek klipu i zsuwanie kolejnych klipów na tej samej ścieżce. Sprawdzenie zakresu źródła, blokad i nakładania klipów. |
| Waveform i linia głośności na klipie | Rzeczywiste amplitudy obliczane lokalnie przez FFmpeg, uwzględniające zakres źródła, gain i fade. Przeciągana linia 0–100%, wspólna historia i odczyt amplitud przez MCP. |
| Monitor źródła i fragmenty nagrań | Podgląd oryginału, punkty IN/OUT, skróty I/O i odtwarzanie zakresu. Wstawianie obrazu i jego dźwięku na osobnych, wyrównanych ścieżkach w jednym kroku. |
| Model komend edycji | Rozszerzenie istniejących komend MotionDuo. Te same walidatory obsługują UI, HTTP, MCP i propozycje agenta. Zaznaczenie grupy jest zamrażane przed odpowiedzią modelu. |

Źródła orientacyjne: [CHANGELOG](https://github.com/jub0t/Concat/blob/7b5cc44bc5c58838967e5f9c511e9f0ae3c9929c/CHANGELOG.md), [architektura](https://github.com/jub0t/Concat/blob/7b5cc44bc5c58838967e5f9c511e9f0ae3c9929c/ARCHITECTURE.md) oraz opis warstw projektu i mediów w `src/README.md`. [Instrukcja nowych funkcji](ADVANCED_EDITING.md).

## Licencja i zakres

Concat jest na **AGPL-3.0-or-later**, z wyjątkiem dla niezależnych modułów korzystających z jego publicznych API. Wyjątek nie jest pozwoleniem na kopiowanie silnika do produktu na MIT.

Implementacje opisane powyżej są własnym kodem MotionDuo, napisanym dla jego istniejącego formatu projektu. Nie skopiowano ani nie dołączono kodu Rust, grafik, modeli, bibliotek lub silnika Concat. Repozytorium Concat nie jest zależnością aplikacji. Licencja kodu MotionDuo pozostaje MIT; wbudowane materiały i narzędzia zachowują swoje licencje.

Nie przeniesiono renderera GPU, sprzętowego dekodowania, pipeline HDR/AV1, katalogu 170+ efektów ani lokalnych modeli transkrypcji, lektora i segmentacji tła. Te elementy wymagałyby odrębnej integracji, budowania, pomiarów jakości i sprawdzenia dystrybucji modeli. Opisy możliwości w README Concat nie są dowodem, że MotionDuo je obsługuje.
