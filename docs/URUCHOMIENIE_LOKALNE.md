# Uruchomienie na komputerze

Wymagane: Python 3.11+, Git, FFmpeg i FFprobe. Studio uruchamia lokalny serwer na 127.0.0.1; projekt, materiały i eksport pozostają na tym komputerze.

## Linux i macOS

Zainstaluj FFmpeg (Ubuntu: `sudo apt install ffmpeg`, macOS: `brew install ffmpeg`). Po pobraniu repozytorium:

```bash
bash scripts/install-local.sh
.venv/bin/python framecore.py editor
```

Skrypt tworzy środowisko `.venv`, instaluje zależności i pobiera Chromium, jeśli nie ma dostępnej przeglądarki. Nie instaluje FFmpeg automatycznie. Polecenie `FRAMECORE_PYTHON=python3.12 bash scripts/install-local.sh` pozwala wskazać interpreter.

## Windows — PowerShell

Zainstaluj Python 3.11+ i FFmpeg. Przykład instalacji FFmpeg: `winget install --id Gyan.FFmpeg --exact`. Otwórz ponownie terminal, aby nowe programy znalazły się w PATH.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-local.ps1
.venv\Scripts\python.exe framecore.py editor
```

`Bypass` dotyczy wyłącznie tego procesu uruchamiającego lokalny skrypt, bez trwałej zmiany polityki systemowej. Skrypt Windows został przygotowany, ale nie wykonany w środowisku Linux. Instalacja na konkretnym komputerze wymaga uruchomienia go na tym komputerze.

## Dane i agent

Dane studia: `output/.framecore/`. Nie usuwaj tego katalogu, jeśli chcesz zachować projekty, historię i pliki. `--root` wskazuje inny katalog projektów; edytor i MCP muszą korzystać z tej samej wartości.

Pliki dla agenta umieść w `output/imports/` (przy domyślnym katalogu projektów). Narzędzie `add_asset` akceptuje tylko pliki w tym katalogu. Konfiguracja klienta: [MCP_SPEC.md](../MCP_SPEC.md).

## Sprawdzenie instalacji

```bash
.venv/bin/python -m pytest tests/test_framecore.py tests/test_framecore_creator_pack.py tests/test_framecore_browser.py tests/test_framecore_interface.py -q
```

Na Windows zamień interpreter na `.venv\Scripts\python.exe`. Test przeglądarkowy otwiera lokalny serwer, uruchamia Chromium i eksportuje rzeczywisty film. W izolowanym środowisku chmurowym wymaga prawa do uruchamiania serwera i procesów przeglądarki.
