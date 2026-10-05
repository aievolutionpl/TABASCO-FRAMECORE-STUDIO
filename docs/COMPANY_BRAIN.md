# Profile marek · Company brain

W **Ustawienia → Profile marek** zapisujesz kontekst firmy raz i używasz go w kolejnych filmach. Ten sam panel otworzysz z zakładki **Marka → Profile marek · Company brain**. Profile znajdują się lokalnie przy projektach FrameCore; nie wymagają dodatkowej usługi ani bazy danych.

![Profil firmy w ustawieniach](../assets/framecore-company-brain.png)

[Materiały marki](../assets/framecore-company-assets.png) · [Panel na telefonie](../assets/framecore-company-mobile.png). Zrzuty pokazują fikcyjny profil demonstracyjny.

## Co zawiera profil

- Informacje o firmie: nazwa, strona, branża, opis, grupa odbiorców i wyróżniki.
- Oferta usługowa, produktowa lub mieszana: katalog pozycji z nazwą, opisem i linkiem.
- Komunikacja: ton, domyślne CTA, ograniczenia oraz niedozwolone obietnice.
- Design guidelines: trzy kolory, font dostępny lokalnie, kompozycja, typografia, zasady logo i ruchu.
- Materiały: logo, zdjęcia produktu i obrazy referencyjne PNG/JPG/WebP do 20 MB, maksymalnie 60 obrazów na markę. Profil może mieć kilka wariantów logo; pierwsze na liście staje się domyślnym logo projektu.
- Research: lista adresów ze znaczeniem źródła oraz notatki o informacjach do potwierdzenia.

Dodawaj produkty, usługi i źródła zwykłymi przyciskami formularza. Nie musisz edytować JSON. Możesz mieć osobne profile klientów, własnych marek albo kampanii.

## Pierwszy film dla firmy

1. Otwórz Ustawienia, wpisz nazwę firmy i podstawowy opis. Uzupełnij ofertę i zasady wizualne, po czym wybierz **Zapisz profil**.
2. Wgraj logo oraz wybrane zdjęcia. Wgrywanie zapisuje także aktualne pola formularza; po dodaniu pliku panel wczytuje zapisaną wersję.
3. Wybierz **Wybierz markę dla tego projektu**. Opcja „Zastosuj także kolory i font” zmienia tło i istniejące teksty; domyślnie obecny montaż zachowuje wygląd, a nowe teksty korzystają z wybranego fontu i kolorów.
4. Logo i zdjęcia znajdziesz w Materiałach. Dodaj je na oś czasu lub zleć montaż agentowi. Wybranie profilu nie umieszcza automatycznie wszystkich zdjęć na filmie.
5. W nowym projekcie ponownie wybierz profil tej firmy. Przejrzyj klatki i gotowy MP4 przed wydaniem.

Wybranie profilu tworzy **kopię informacji i plików w projekcie**, powiązaną z konkretną wersją marki. Agent montujący film otrzymuje tę kopię jako `companyBrain`, wraz z katalogiem materiałów. Edytowanie lub usuwanie profilu w bibliotece nie zmienia starszych filmów. Aby zaktualizować film po rebrandingu, wybierz najnowszy profil ponownie. Wybór marki, razem z dodaniem materiałów, zapisuje się jako jeden krok historii i obsługuje Cofnij/Ponów.

## Uzupełnianie przez agenta

Połącz dostawcę w **Agent AI → Podłącz agenta**. W profilu rozwiń **Agent · przygotuj company brain**, wklej brief, treści ze strony firmy, opis oferty i linki do źródeł. Wybierz **Przygotuj szkic z agentem**, następnie **Przenieś szkic do formularza**. Sprawdź fakty, źródła, produkty i zasady; dopiero **Zapisz profil** utrwala zmiany. Szkic nie edytuje filmu ani profilu automatycznie. Zatrzymanie odrzuca późniejszą odpowiedź. Jedno połączenie obsługuje jedno zadanie naraz, wspólnie z montażem.

Wbudowany adapter porządkuje dostarczone materiały i **nie pobiera stron z internetu**. Sam URL nie oznacza odwiedzenia strony. Nowe twierdzenia wymagają sprawdzenia, a propozycje stylu należy oddzielić w notatkach od faktów firmy.

Agent zewnętrzny, który ma narzędzia wyszukiwania i przeglądarkę, może przeprowadzić research oraz zapisać profil przez MCP. Najpierw powinien sprawdzić oficjalną stronę i ofertę, zapisać adresy i datę dostępu w `sources`, oznaczyć luki w `researchNotes`, a następnie skorzystać z `save_brand_profile`. Obrazy z legalnie pozyskanych materiałów umieszcza w katalogu `imports` i dodaje przez `upload_brand_asset`; przypisuje rolę `logo`, `reference` albo `product`. Nie powinien dopisywać niepotwierdzonych cen, wyników ani obietnic. Profil przygotowany przez agenta pozostaje widoczny w tej samej bibliotece i może zostać poprawiony przez człowieka.

Treść profilu i materiały źródłowe trafiają do wybranego dostawcy przy odpowiednim zadaniu AI. Nie wpisuj tam kluczy API ani haseł. Połączenie zachowuje klucz wyłącznie w pamięci procesu; nie dodaje go do profilu. Zdjęcia w tym trybie nie są przesyłane do modelu, więc agent nie ocenia ich pikseli.

## API i MCP

| Narzędzie | Wymagane dane |
|---|---|
| `list_brand_profiles` | brak |
| `get_brand_profile` | `brand_id` |
| `save_brand_profile` | `profile`; przy aktualizacji także `brand_id`, `expected_version` |
| `delete_brand_profile` | `brand_id`, `expected_version` |
| `upload_brand_asset` | `brand_id`, `expected_version`, `source_file` (obraz w katalogu `imports` obok katalogu projektów); opcjonalne `role` |
| `remove_brand_asset` | `brand_id`, `expected_version`, `asset_id` |
| `apply_brand_profile` | `project_id`, `expected_revision`, `brand_id`, `expected_version`; opcjonalne `restyle` |

`profile` ma pola `name`, `website`, `industry`, `about`, `offer`, `audience`, `positioning`, `tone`, `cta`, `guidelines`, `logoRules`, `motionRules`, `restrictions`, `researchNotes`, `businessType` (`services`, `products`, `both`), `colors` (`background`, `text`, `accent` w hex), `font`, `products` i `sources`. Pozycja produktu/usługi to `{name, description, url}`; pozycja źródła to `{url, note}`. Nieznany adres może być pusty. Lista produktów oraz źródeł ma limit po 60 pozycji. `save_brand_profile` zapisuje cały formularz; przed aktualizacją odczytaj profil, zachowaj istniejące pola i zmodyfikuj potrzebne wartości. Tablica `assets` jest zarządzana oddzielnie; nie wysyłaj jej w formularzu zapisu.

Przykład tworzenia przez MCP:

```json
{
  "name": "save_brand_profile",
  "arguments": {
    "profile": {
      "name": "Przykładowy Serwis",
      "businessType": "services",
      "about": "Firma zajmuje się serwisem instalacji.",
      "products": [{"name": "Przegląd", "description": "Zakres do potwierdzenia w briefie klienta", "url": ""}],
      "sources": [{"url": "https://example.com", "note": "Przykładowy adres; zastąp sprawdzonym źródłem"}],
      "researchNotes": "Profil demonstracyjny; wymaga potwierdzenia przez klienta."
    }
  }
}
```

HTTP: `GET /api/brands` zwraca profile, a narzędzia są wywoływane przez tokenowane `POST /api/command`. Wgrywanie binarne używa `POST /api/brand-upload/{brand_id}?version=…&role=logo|reference|product&name=…`, z nagłówkiem `X-Studio-Token`. Przygotowanie szkicu: `POST /api/agent/brand-draft` z `profile` i `notes`; wynik `draft` odczytasz z `/api/agent/status`. Wszystkie zapisy chronią dotychczasowe reguły Host/Origin/tokena. Konflikt wersji wymaga ponownego odczytu, a nie nadpisania.

Pliki biblioteki: `output/.framecore/_brands/{brand_id}/profile.json` i `assets/`. Kopia projektu jest zapisana w `brandProfile`, a skopiowane obrazy w jego zwykłej bibliotece `assets`. Trafia do źródeł projektu w pakiecie produkcyjnym ZIP. Profile starego silnika CLI `vstudio.brands` pozostają oddzielne — ta funkcja dotyczy wspólnego edytora FrameCore.
