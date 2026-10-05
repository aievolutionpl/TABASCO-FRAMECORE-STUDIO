# Agent wbudowany i zewnętrzny — pierwszy montaż

## Użytkownik: uruchomienie w trzy minuty

1. Uruchom studio. Na Windows możesz użyć `START-STUDIO.cmd`.
2. Przejdź przez samouczek **Jak zacząć**. Możesz otworzyć go ponownie w dowolnej chwili.
3. Utwórz projekt i dodaj materiały albo wybierz szablon.
4. Otwórz **Integracje**, wybierz OpenRouter lub OpenAI, wpisz model i klucz API.
5. Zapisz ustawienia. **Pobierz modele** pobiera katalog; dla OpenRouter filtruje modele deklarujące obsługę narzędzi. **Test połączenia** wysyła krótkie, potencjalnie płatne zapytanie.
6. Otwórz **Twój agent**. Zacznij od: „Przeczytaj projekt i zaproponuj trzy ulepszenia, bez zmian”.
7. Zleć zmianę. W rozmowie zobaczysz wykonane narzędzia. Sprawdź podgląd; Ctrl/Cmd+Z cofa także operacje agenta.

Klucz pozostaje po stronie lokalnego serwera w `output/.framecore-agent.json`, poza projektem i Git. Jest zapisany lokalnie, bez szyfrowania aplikacyjnego; chronią go uprawnienia systemu i konto użytkownika. Pole klucza w interfejsie nigdy nie odczytuje zapisanego sekretu. Alternatywnie ustaw `OPENROUTER_API_KEY` lub `OPENAI_API_KEY`. Usunięcie lokalnego klucza nie usuwa zmiennej środowiskowej. Zmiana dostawcy nie przenosi klucza między usługami.

Wybrany dostawca otrzymuje polecenia, kontekst montażu oraz wyniki narzędzi. Pliki wideo i obrazy nie są automatycznie wysyłane. Wbudowany agent wykonuje maksymalnie 16 tur narzędziowych i 24 operacje w jednej odpowiedzi. Jednocześnie działa jedno zadanie. Zatrzymanie kończy pracę po trwającym wywołaniu; nie cofa już zapisanych zmian. Rozmowy są przechowywane w pamięci procesu, historia edycji pozostaje na dysku.

## Agent: procedura startowa

1. `get_editing_guide`, `get_project`, `get_selection`.
2. `list_assets`, `list_templates`, `list_motion`, `list_fonts`, `list_library`, `list_backgrounds`.
3. Ustal odbiorcę, format, długość i cel. Dla krótkiej reklamy wybierz jeden komunikat na scenę, 3–6 sekund na scenę, najwyżej dwie rodziny fontów i wyraźną końcową zachętę.
4. Użyj `plan_storyboard`. Przy `assemble_storyboard` przekaż `template_id`. Duży montaż przygotuj przez `propose_changes`, potem `apply_proposal` zgodnie ze zleceniem.
5. Każda zmiana wymaga aktualnej `expected_revision`. Po konflikcie odczytaj projekt ponownie i uwzględnij zmiany człowieka.
6. `inspect_project` sprawdza strukturę. Zewnętrzny agent może dodatkowo obejrzeć `capture_frame`. Wbudowany agent tekstowy nie ogląda klatek — użytkownik sprawdza podgląd.
7. `export` uruchamiaj po zleceniu użytkownika. Wynik istnieje dopiero po `get_job.status == complete`.

MCP: `.venv/Scripts/python.exe framecore.py mcp` na Windows, `.venv/bin/python framecore.py mcp` na Linux/macOS. Katalog pracy to repozytorium. MCP i edytor muszą wskazywać ten sam `--root`. Schematy pobieraj przez `tools/list`; nigdy nie zgaduj identyfikatorów.

## HTTP dla własnego klienta

`GET /api/tools` opisuje komendy, `GET /api/runtime` sprawdza lokalne zależności, `GET /api/projects` zwraca projekty. Zmiany przechodzą przez `POST /api/command` i wymagają `X-Studio-Token` oraz zgodnego Origin. Agent korzysta z tego samego `API.call`, bez dostępu do powłoki i dowolnych plików. Wbudowany agent jest ograniczony do jednego projektu i nie ma narzędzia importu dowolnej ścieżki.

Agent HTTP: `GET /api/assistant/status`, `POST /api/assistant/settings`, `POST /api/assistant/models`, `POST /api/assistant/test`, `POST /api/assistant/run` (`project_id`, `prompt`), `GET /api/assistant/job/<id>`, `POST /api/assistant/cancel` (`job_id`). Żaden endpoint nie zwraca klucza API. Odczyt statusu zadania ujawnia tylko wynik i nazwy wykonanych operacji.

## Co jest faktycznie zintegrowane

OpenRouter i OpenAI: rozmowa tekstowa oraz wywołania narzędzi edytora. Generowanie obrazów, wideo, głosu i transkrypcja nadal wymagają osobnych adapterów dostawców. Nowe materiały kampanii zostały wygenerowane podczas przygotowania wydania, a następnie dołączone lokalnie do biblioteki — nie są wynikiem działającego generatora wewnątrz aplikacji.
