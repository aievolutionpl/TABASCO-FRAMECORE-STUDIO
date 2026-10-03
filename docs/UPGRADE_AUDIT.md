# Audyt wstępny i stan bazowy vstudio (Upgrade Audit)

Data: 2026-10-03
Gałąź bazowa: `main` (commit `1c9dc1b`)
Gałąź robocza: `feat/brand-profiles-and-creative-modes`

---

## 1. Weryfikacja środowiska i narzędzi (`vstudio doctor`)

- **Python**: 3.13.1 (spełnia wymóg `>= 3.11`).
- **FFmpeg & FFprobe**: zainstalowane i dostępne w `PATH` (`loudnorm` dwuprzebiegowy -14 LUFS gotowy).
- **Playwright & Chromium**: zsynchronizowano Playwright 1.62.0 z zainstalowanym `chromium-headless-shell-1234`.
- **Render próbny**: wykonano weryfikację potoku renderowania HTML -> Chromium -> klatki -> FFmpeg MP4 (`test-audit`, draft MP4 15fps wygenerowany pomyślnie i bez błędów).
- **Dashboard**: serwer oparty na bibliotece standardowej Pythona, tokenach sesyjnych i izolowanym sandbox iframe (`sandbox allow-scripts`).

---

## 2. Diagnoza i naprawione błędy regresyjne (Platforma Windows)

Podczas pierwszego uruchomienia pełnego zestawu testów `pytest` wykryto 3 błędy specyficzne dla środowiska Windows:

1. **`vstudio.py:resolve_project`**:
   - *Problem*: wyszukiwanie projektu `-p t/c` porównywało `value in str(q.parent)`. Na systemie Windows ścieżka systemowa używa separatorów `\`, co powodowało brak dopasowania dla ciągów z `/`.
   - *Naprawa*: dodano dopasowanie `value in q.parent.as_posix() or value in str(q.parent)`.
   - *Weryfikacja*: testy CLI w `tests/test_reel_formats.py` przeszły pomyślnie.

2. **`tests/test_studio_agent.py::TestSupportModules::test_jobs_are_visible_and_cancellable_across_processes`**:
   - *Problem*: test uruchamiał komendę systemową `sleep 60`, która nie występuje w systemie Windows (`WinError 2`).
   - *Naprawa*: zamieniono na wieloplatformowe wywołanie `[sys.executable, "-c", "import time; time.sleep(60)"]` z odpowiednią flagą `creationflags` na Windows.

3. **`tests/test_studio_agent.py::TestWatcher::test_watcher_only_reacts_to_real_changes`**:
   - *Problem*: wywołanie `src.write_text(...)` bez jawnego kodowania używało domyślnego `cp1252` na Windows, rzucając `UnicodeEncodeError` na polskich znakach starteru HTML.
   - *Naprawa*: dodano `encoding="utf-8"`.

Po wdrożeniu poprawek cały pakiet testów przechodzi w 100% (wszystkie testy zielone, testy wymagające zewnętrznego CDN pomijane zgodnie z definicją).

---

## 3. Ryzyka architektoniczne i założenia pod Etap 1

1. **Migracja dotychczasowego profilu**:
   - W `output/.studio/profile.json` dotychczas istniał pojedynczy obiekt profilu.
   - *Rozwiązanie*: bezstratna migracja do biblioteki marek `brands.json` (lub struktury z `brands: {id: ...}` oraz `active_brand_id`). Dostęp wsteczny przez `profile_get()` / `profile_set()` musi zachować dotychczasowy kontrakt dla istniejących narzędzi i testów.

2. **Niezależność marek i wersjonowanie w projektach**:
   - Istniejące projekty `project.json` nie posiadały przypisanego `brand_id` ani migawki/wersji ustawień marki (`brand_settings_version` / `brand_snapshot`).
   - Zmiana aktywnej marki w studio nie może mutować wygenerowanych projektów. Każdy projekt zapamiętuje swój `brand_id` oraz kopię/wersję parametrów brandu w chwili tworzenia.

3. **Profile kreatywne a ocena reżysera**:
   - Dotychczasowe reguły `director.py` miały twarde limity: `NO_VISUAL_ASSETS` (ostrzeżenie przy braku ikon), `MONOTONE_STYLE` (wymóg wielu looków/stylów), `SLOW_PACE` (wymóg częstych zmian kadru co 2.5s na reels), `NO_HOOK_TEXT` (wymóg tekstu w pierwszych sekundach).
   - W profilu `premium_minimal` lub przy trybie tekstu `none` / `headline_only` takie cechy są zamierzoną decyzją estetyczną.
   - Reżyser i nadzorca muszą respektować profil kreatywny projektu i nie zgłaszać fałszywych błędów/ostrzeżeń, zachowując jednocześnie pełną kontrolę błędów technicznych (brak błędów JS, brak przyciętych tekstów, brak migotania).
