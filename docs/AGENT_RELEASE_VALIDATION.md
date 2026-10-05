# Walidacja wydania — 5 października 2026

## Wdrożone

- Iteracyjna rozmowa OpenRouter/OpenAI z wywołaniami narzędzi, ograniczona do otwartego projektu.
- Lokalna konfiguracja bez zwracania kluczy do przeglądarki; wsparcie zmiennych środowiskowych.
- Test rzeczywistej obsługi tool calling, lista modeli, postęp zadania i zatrzymanie.
- Pięcioetapowy onboarding, diagnostyka FFmpeg/Chromium, konfiguracja MCP z rzeczywistymi ścieżkami.
- Trzy materiały FrameCore Cinema z hashami SHA-256, promptami i jawnym pochodzeniem AI.
- Edytowalna reklama 30 s, sześć scen po 5 s, różne animacje, H.264 + AAC.
- Zachowane aktualne funkcje z main: zadania Codex/Claude/OpenRouter, profile marek, Company brain, produkcja i przegląd ruchu.

## Sprawdzenia

Testy jednostkowe sprawdzają prywatność konfiguracji, ograniczenie projektu, niedozwolone narzędzia, konflikt rewizji, błędy dostawcy, limit tur i anulowanie. Test Chromium przechodzi przez onboarding, zapis klucza testowego, polecenie do kontrolowanego modelu i aktualizację wspólnego projektu. Wykorzystuje atrapę odpowiedzi modelu, ale rzeczywisty serwer HTTP, API, zapis projektu i interfejs.

Osobny test na rzeczywistym OpenRouter potwierdził tool calling dla `openai/gpt-4.1-mini`. Po wyraźnej zgodzie użytkownika model wykonał `get_project` i `get_selection` na pokazowej reklamie oraz poprawnie zwrócił: 30 sekund, 6 scen, rewizja 50. Montaż nie został zmieniony. Żadne pliki mediów ani klucze nie trafiły do logu testowego.

Pełny lokalny zestaw: 298 przypadków, 274 zaliczone w pierwszym końcowym przebiegu, 23 pominięte zgodnie z warunkami środowiska oraz jeden timeout testu przeglądarkowego montażu/eksportu. Ten sam test ponowiony osobno przeszedł z rzeczywistym eksportem MP4 (78,73 s). Łącznie zweryfikowano 275 przypadków; timeout był przejściowy i pozostaje odnotowany, zamiast przedstawiać pierwszy przebieg jako bezbłędny. Testy pominięte obejmują między innymi opcjonalne scenariusze wymagające lokalnej kopii GSAP.

GitHub Actions odtworzył timeout oczekiwania na link eksportu, obecny także na poprzednim `main`. Test akceptacyjny został uzupełniony o odczyt rzeczywistego zadania: błąd renderera kończy test natychmiast z diagnostyką; trwający render ma limit 600 sekund dla wolniejszych runnerów, a po ukończeniu sprawdzany jest także link pobierania w interfejsie.

MP4 sprawdzono przez FFprobe (1920 × 1080, 30 fps, 30.000 s, H.264 i AAC) oraz ogląd sześciu rzeczywistych klatek. Renderowanie dużych lokalnych obrazów na Windows korzysta z obsługi plików przez Playwright, eliminując zależność eksportu od połączeń loopback.

## Granice

Rzeczywiste połączenie sprawdzono dla OpenRouter, nie dla płatnego konta OpenAI. Test połączenia nie dowodzi jakości każdej przyszłej decyzji modelu. Wbudowana rozmowa jest tekstowa; kontrola struktury nie zastępuje oceny obrazu i dźwięku. Generowanie mediów i transkrypcja wymagają osobnych adapterów. Klucz zapisany w pliku lokalnym nie jest szyfrowany przez aplikację. Panel zadań CLI ma osobne połączenie, przechowywane w pamięci procesu.

Kampania i kod są publikowane w repozytorium na zlecenie użytkownika. Nie wykonano publikacji reklamy w mediach społecznościowych ani wdrożenia publicznej usługi internetowej.
