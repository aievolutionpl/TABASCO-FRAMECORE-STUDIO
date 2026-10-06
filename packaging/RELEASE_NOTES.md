# MotionDuo Studio · desktop preview

Samodzielna aplikacja: własne okno, Python, FFmpeg/FFprobe i Chromium do eksportu. Nie trzeba instalować środowiska programistycznego. Windows x64 oraz osobne paczki macOS dla Apple Silicon i Intel.

- Windows: pobierz `windows-x64-setup.exe`, uruchom instalator, a później ikonę MotionDuo Studio w menu Start. Pierwsza instalacja WebView2 może wymagać internetu.
- macOS: wybierz właściwy DMG, otwórz i przeciągnij MotionDuo Studio do Applications.
- Projekty i profile marek pozostają poza katalogiem instalacji: `%LOCALAPPDATA%\FrameCore Studio` lub `~/Library/Application Support/FrameCore Studio`.
- Studio działa lokalnie. Generowanie oraz agent przez API wymagają własnego połączenia i klucza dostawcy.

To wydanie testowe bez komercyjnego certyfikatu wydawcy i bez notaryzacji Apple. macOS może wymagać otwarcia aplikacji przez **Ustawienia systemowe → Prywatność i ochrona → Otwórz mimo to**, a Windows może pokazać informację o nierozpoznanym wydawcy. Nie wyłączaj zabezpieczeń całego systemu.

Automatyczny test każdej paczki uruchamia zamrożony serwer, wczytuje H.264/AAC, eksportuje MP4 z audio, sprawdza zapis projektu i połączenie MCP. Nie zastępuje ręcznego testu całego natywnego okna. Narzędzia mają własne licencje, dołączone do aplikacji; informacje są w TOOL_NOTICES.md. Pliki SHA-256 towarzyszą instalatorom.

Rebranding 0.3.1: nowy znak M, nazwa MotionDuo Studio — by TABASCO CREATIVES + FRAMECORE, polski banner oraz dopracowane panele, timeline i przycisk dodania logo do filmu. Katalog danych i konfiguracja MCP pozostają kompatybilne z 0.3.0.
