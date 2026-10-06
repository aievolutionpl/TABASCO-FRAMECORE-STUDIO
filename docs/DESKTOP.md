# MotionDuo Studio jako aplikacja

Instalatory **0.3.2 desktop preview** są dostępne w [GitHub Releases](https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO/releases/tag/v0.3.2-desktop.1). Pierwsza seria ma status **desktop preview**: Windows x64, macOS Apple Silicon i macOS Intel. Linki na stronie produktu aktualizują się dopiero po publikacji rzeczywistych plików.

## Instalacja

Windows: pobierz `windows-x64-setup.exe` i uruchom instalator. Powstaje skrót w menu Start; ikona pulpitu jest opcjonalna. Instalator przygotowuje WebView2 z oficjalnego podpisanego bootstrappera Microsoft — ten krok może wymagać internetu. Program instaluje się dla bieżącego użytkownika.

macOS: pobierz DMG dla Apple Silicon (`arm64`) lub Intel (`x64`), otwórz i przeciągnij **MotionDuo Studio** do **Applications**. Okno korzysta z systemowego WKWebView.

Nie trzeba instalować Pythona, Git ani FFmpeg. Paczka zawiera własny Python, FFmpeg/FFprobe, Chromium i lokalne materiały studia. Agent lub generowanie przez dostawcę nadal wymagają własnego połączenia. Narzędzia Codex/Claude CLI instalujesz osobno, jeśli wybierasz ten sposób połączenia.

To wydanie bez komercyjnego podpisu Windows i notaryzacji Apple. System może wymagać potwierdzenia konkretnej aplikacji. Na macOS użyj **Prywatność i ochrona → Otwórz mimo to** zgodnie z komunikatem systemu; nie wyłączaj ochrony globalnie. Instrukcje konkretnego wydania i sumy SHA-256 znajdują się przy plikach.

Nowe wydanie zawiera logo MotionDuo, banner, panel efektów, przejścia dla poszczególnych scen i narzędzia timeline. [Instrukcja montażu](EDITING_EFFECTS.md). Nazwa producentów: **TABASCO CREATIVES + FRAMECORE**.

## Dane i aktualizacja

- Windows: `%LOCALAPPDATA%\FrameCore Studio\projects`.
- macOS: `~/Library/Application Support/FrameCore Studio/projects`.
- Profile marek są w bibliotece projektów; ustawienia agenta obok niej.
- Log uruchomienia: `desktop.log` w katalogu FrameCore Studio.

Katalogi nadal noszą nazwę FrameCore Studio, aby aktualizacja zachowała dotychczasowe dane.

Instalator i deinstalator nie usuwają osobistych projektów. Aktualizację wykonaj po zamknięciu studia i ukończeniu eksportu. Istniejąca instalacja z kodu zachowuje swój katalog `output/.framecore`; nic nie jest przenoszone lub nadpisywane automatycznie. Aby zachować tamte projekty w aplikacji, zamknij obie wersje i skopiuj zawartość starego katalogu projektów do nowego. Zachowaj kopię oryginału.

## Budowanie

Buduj na docelowym systemie. Nie nazywaj kompilacji Linux instalatorem Windows lub macOS.

```bash
python -m pip install -r packaging/requirements-desktop.txt
# Ustaw PLAYWRIGHT_BROWSERS_PATH na katalog roboczy przeglądarek.
python -m playwright install --only-shell chromium
python scripts/build-desktop.py
```

Maszyna budująca musi mieć FFmpeg i FFprobe. `FRAMECORE_FFMPEG` oraz `FRAMECORE_FFPROBE` pozwalają wskazać pliki binarne. Na Windows skrypt rozpoznaje rzeczywisty plik pakietu Chocolatey zamiast kopiować jego shim. macOS bundluje zależności dylib narzędzi przez PyInstaller. Certyfikaty CA są dołączane do wywołań HTTPS; własne `SSL_CERT_FILE` pozostaje respektowane.

Workflow **Desktop installers** buduje na Windows i dwóch architekturach macOS, sprawdza każdą zamrożoną paczkę, a następnie publikuje prerelease. Uruchamia się dla taga `v*-desktop.*` lub ręcznie. W tej serii wersja i tag są określone w `packaging/version.json`; zmiana serii wymaga także aktualizacji nazwy instalatora i workflow.

Paczka ma dwa pliki wykonywalne: okno **FrameCoreStudio** i konsolowy **FrameCoreEngine** do renderowania oraz MCP. Konfiguracja `/api/mcp-config` wskazuje rzeczywisty silnik z właściwym katalogiem danych. Argumenty `--headless --ready-file` są przeznaczone tylko do automatycznego sprawdzenia paczki.

### Przenośny render mediów

Dołączone Chromium może mieć inny zestaw kodeków niż przeglądarka użytkownika. Aplikacja tworzy pośrednie kopie VP9/Opus lub PCM do przechwytywania klatek oraz przeglądu. Oryginalne pliki, identyfikatory klipów, montaż, rewizja i końcowy miks audio pozostają zachowane. Kopie przeglądu są buforowane według SHA-256. Pośrednia kompresja obrazu może wpływać na jakość; przed oddaniem filmu sprawdź rzeczywisty eksport.

Informacje i teksty licencji narzędzi są dołączone w `desktop-licenses` oraz katalogach bibliotek. [Szczegóły](../packaging/TOOL_NOTICES.md).
