# Narzędzia w aplikacji desktopowej

Kod FrameCore: MIT. Znak oraz materiały wygenerowane dla projektu: patrz informacje w repozytorium. Ikony, fonty i biblioteki wizualne: `THIRD_PARTY_NOTICES.md` i dołączony katalog `licenses`.

Własny Python jest pakowany przez PyInstaller (GPL z wyjątkiem dla aplikacji utworzonych bootloaderem). Okno aplikacji korzysta z pywebview (BSD-3-Clause) oraz systemowego WKWebView na macOS lub Microsoft WebView2 na Windows. WebView2 ma licencję Microsoft; instalator zawiera oficjalny podpisany bootstrapper.

Playwright: Apache-2.0. Chromium: licencje projektu Chromium i komponentów, dostarczane razem z przeglądarką w katalogu `browsers`. Chromium nie wymaga instalowania osobnej przeglądarki przez użytkownika.

FFmpeg i FFprobe są osobnymi procesami, na licencjach wskazanych przez konkretny build (LGPL/GPL). Dokładna wersja, konfiguracja, sumy plików oraz pochodzenie są zapisane w `tool-manifest.json`. Pełny tekst licencji narzędzi i zależności Pythona jest dołączany przy budowaniu. Źródła FFmpeg: https://ffmpeg.org/download.html oraz https://ffmpeg.org/releases/ . Build Windows pochodzi z pakietu Gyan.FFmpeg w Chocolatey (https://www.gyan.dev/ffmpeg/builds/), a macOS z formuły Homebrew (https://formulae.brew.sh/formula/ffmpeg). Źródła i receptury tych dystrybucji są publiczne.

Kopie VP9/Opus oraz PCM służą tylko przechwytywaniu w dołączonym Chromium. Oryginały mediów są zachowywane; końcowy miks audio korzysta z oryginalnych plików. Pośrednia kompresja obrazu może wpływać na jakość, dlatego gotowy film wymaga przeglądu.
