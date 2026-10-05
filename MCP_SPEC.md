# Agent i API MCP FrameCore

MCP używa JSON-RPC 2.0 przez standardowe wejście i wyjście, po jednym komunikacie w wierszu. Uruchom `.venv/bin/python framecore.py mcp` w katalogu repozytorium. Na Windows użyj `.venv\Scripts\python.exe`. Interfejs HTTP i MCP wywołują ten sam zapis oraz komendy; agent nie musi klikać w przeglądarce.

## Konfiguracja klienta

Wpisz pełne ścieżki odpowiednie dla swojego komputera:

```json
{
  "mcpServers": {
    "framecore": {
      "command": "/sciezka/do/vstudio/.venv/bin/python",
      "args": ["/sciezka/do/vstudio/framecore.py", "mcp"],
      "cwd": "/sciezka/do/vstudio"
    }
  }
}
```

Jeśli edytor używa `--root`, dodaj tę samą opcję i ścieżkę do `args`. Instalacja i uwierzytelnienie klienta agenta należą do jego konfiguracji. MCP do edycji projektu nie wymaga klucza dostawcy generowania materiałów.

## Narzędzia

| Cel | Narzędzia |
| --- | --- |
| Kontekst | `get_project`, `get_selection`, `get_timeline`, `get_frame_context`, `get_history`, `list_projects`, `list_assets` |
| Instrukcje i biblioteki | `get_editing_guide`, `list_motion`, `list_templates`, `list_icons`, `list_library`, `list_fonts`, `list_backgrounds` |
| Kontrola | `inspect_project`, `capture_frame`, `preview` |
| Projekt | `create_project`, `rename_project`, `set_duration`, `set_format`, `set_brand`, `set_background`, `set_track` |
| Materiały i elementy | `add_asset`, `add_library_asset`, `add_icon`, `add_text`, `add_shape`, `add_video`, `add_image`, `add_audio`, `add_caption` |
| Montaż | `move_clip`, `trim_clip`, `split_clip`, `duplicate_clip`, `delete_clip`, `move_element`, `resize_element`, `set_property` |
| Ruch i dźwięk | `apply_motion`, `set_keyframes`, `set_audio`, `style_captions` |
| Plan scen | `plan_storyboard`, `apply_template`, `assemble_storyboard`, `add_scene`, `duplicate_scene` |
| Współpraca | `propose_changes`, `apply_proposal`, `cancel_proposal`, `undo`, `redo`, `set_selection`, `set_playhead` |
| Eksport | `render`, `export`, `get_job` |
| Dostawcy | `get_providers`, `generate_image`, `generate_video`, `generate_audio`, `generate_voice`, `transcribe` |

Dostawcy są obecnie interfejsami integracji. Bez adaptera generowanie kończy się błędem `provider_unavailable`; nie powstaje fikcyjny materiał.

## Kontrakt zmian

Komendy projektu wymagają `project_id`. Zmiany treści i eksport wymagają także `expected_revision`. Narzędzia elementów przyjmują `element_id`; jego brak oznacza użycie jednego wspólnego zaznaczenia. Po konflikcie odczytaj rewizję ponownie. `tools/list` publikuje schematy wejścia; [instrukcja agenta](skills/framecore/SKILL.md) opisuje kolejność pracy.

`propose_changes` przyjmuje listę `{"name":"move_clip","args":{"element_id":"…","start":1.6}}` i opis. Wynik zawiera sprawdzony stan po zmianach, listę zmienionych i usuniętych elementów. `apply_proposal` działa tylko przy rewizji, z której utworzono propozycję. Cała propozycja jest jednym krokiem cofania.

`set_keyframes` zastępuje listę punktów elementu. Punkt zawiera `property`, `time`, `value`; czas jest lokalny względem początku klipu. `set_audio` przyjmuje obiekt `audio` z wybranymi polami `gain`, `fadeIn`, `fadeOut`. `apply_template` przyjmuje `template_id`; zastąpienie montażu wymaga `replace: true`. Przed nim można obejrzeć `plan_storyboard` z tym samym identyfikatorem.

`add_asset` odczytuje `source_file` wyłącznie z katalogu `imports` przy katalogu projektów. Przy domyślnym zapisie to `output/imports/`. Używaj importu w interfejsie lub tego katalogu, zamiast ścieżek spoza przestrzeni projektu.

## Obraz i kontrola

`capture_frame` przyjmuje opcjonalny czas `time`; bez niego używa wspólnego wskaźnika. Renderuje zamrożony stan w Chromium, zwraca metadane i blok obrazu MCP `image/png`. Nie zmienia montażu ani wskaźnika czasu. `inspect_project` wykrywa wyjście poza kadr, mały tekst i wejście dłuższe od klipu; nie mierzy łamania tekstu, obrotów, kolizji ani kontrastu.

`export` zwraca identyfikator zadania; `get_job` pokazuje postęp, błąd lub adres MP4. Zadania są współdzielone między procesami. Wynik jest dostępny dopiero po stanie `complete`.

## HTTP

Odczyt: `/api/projects`, `/api/project/<id>`, `/api/context/<id>`, `/api/motion`, `/api/tools`, `/api/job/<id>`. Zmiany: POST `/api/create`, `/api/command`, `/api/upload/<id>`, `/api/export`. Komendy POST wymagają tokena sesji, poprawnego Host i tego samego Origin. Konflikt rewizji zwraca HTTP 409. Podgląd: `/composition/<id>`; pliki materiałów i eksportu mają ograniczone ścieżki.

## Wbudowane materiały

`list_library` zwraca 84 materiały wraz z identyfikatorem, kolekcją, licencją i lokalnym podglądem. `add_library_asset` kopiuje wybraną ilustrację lub ikonę do projektu i dodaje edytowalny klip. `list_fonts` opisuje osiem lokalnych rodzin, w tym dostępne grubości. `list_backgrounds` opisuje 24 receptury; `set_background` przyjmuje `background_id` i opcjonalne `animated`.

`plan_storyboard` zwraca `template_id`. Przekaż go do `assemble_storyboard` wraz ze scenami, aby zachować font, tło, układ i animacje. `apply_template` wykonuje tę operację bez osobnej redakcji scen. [Przykłady](docs/CREATOR_PACK.md).

## Pipeline produkcyjny

FrameCore udostępnia również kontrakt produkcyjny, beaty, reguły ruchu, przegląd klatek, ocenę konkretnej rewizji i niezależne warianty formatów. [Pola i przykłady narzędzi](docs/PRODUCTION_PIPELINE.md). `create_review` oraz `get_review` zwracają planszę JPEG jako blok obrazu MCP obok raportu JSON. Używaj aktualnego `expected_revision`; przy braku wymaganych materiałów lub nieaktualnej ocenie serwer zatrzyma odpowiedni etap. `package_delivery` przyjmuje `job_id` ukończonego eksportu tego projektu.

## Pomiary filmu i playbook

`get_motion_playbook` nie wymaga projektu: zwraca polskie reguły, receptury i prompt niezależnego krytyka. `analyze_export` wymaga `project_id`, `job_id` ukończonego eksportu oraz opcjonalnie `profile` calm/punchy/mute (domyślnie calm). Zapisuje raport pomiarowy, bez zmiany projektu i jego historii. `get_quality_report` wymaga projektu i zadania; odrzuca raport, jeśli SHA-256 MP4 uległo zmianie. Nie wymagają `expected_revision`, ponieważ dotyczą zamrożonego eksportu, a nie bieżącego montażu. Schematy MCP publikują wymagany `job_id`. Raport jest dostępny w ograniczonej ścieżce `/exports/<project>/<job>/quality-report.json` i dołączany do kolejnego ZIP. [Parametry i ograniczenia](docs/MOTION_VIDEO_KIT.md).

## Laboratorium ruchu — fframes

`resolve_frame_time` tłumaczy `spec` (scena@czas, procent, klatka, sekundy) na czas globalny. `create_motion_strip` wymaga rewizji, przyjmuje `start`, `end`, `count` 2–24 i generuje przegląd z planszą oraz onion PNG. MCP zwraca oba obrazy także przez `get_review`. `list_reviews` opisuje zapisane harmonogramy. `compare_reviews` wymaga `baseline_id`, `review_id`, opcjonalnie `threshold` i `max_diff_ratio`; porównuje identyczne harmonogramy i rozmiary, zapisuje diff PNG i raport. [Parametry i przykłady](docs/FFRAMES.md). [Połączenie i sterowanie z dashboardu](docs/AGENT_DASHBOARD.md) korzysta z odrębnych tras HTTP chronionych tokenem.

## Profile marek i company brain

Wspólny edytor udostępnia `list_brand_profiles`, `get_brand_profile`, `save_brand_profile`, `upload_brand_asset`, `remove_brand_asset`, `delete_brand_profile` oraz `apply_brand_profile`. Biblioteka ma własny `expected_version`; przypisanie do projektu wymaga także `expected_revision`. Kontekst klatki zwraca `companyBrain`, a projekt zachowuje kopię profilu i materiałów. [Schemat, research i przykłady](docs/COMPANY_BRAIN.md).

## Ręczny montaż po pracy agenta i lekcje

Nowe komendy `replace_clip_asset`, `add_track`, `set_project_fps`, `set_learning_brief`, `set_scene_learning` oraz `assemble_visual_lesson` korzystają z tej samej historii i rewizji co człowiek. `plan_visual_lesson`, `get_lesson_status` i `get_storytelling_playbook` są odczytami. [Parametry i zasady](docs/COLLABORATIVE_EDITING.md).
