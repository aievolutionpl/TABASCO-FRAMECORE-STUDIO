# Publiczna strona produktu

Adres: https://aievolutionpl.github.io/TABASCO-FRAMECORE-STUDIO/

Polski landing opisuje wspólny montaż człowieka i agenta, timeline, ruch, Company brain i lekcję przez historię. Pokazuje rzeczywisty zrzut edytora oraz 21-sekundowy szkic wideo bez lektora. Profil Studio Słońce jest podpisanym przykładem, nie realizacją klienta. Strona nie zawiera fikcyjnych opinii, kont, formularza przesyłania mediów ani narzędzi analitycznych.

`site/` zawiera HTML, CSS i mały skrypt pobierający wyłącznie publiczne metadane wydań GitHub. Przyciski instalatorów otrzymują bezpośrednie adresy tylko wtedy, gdy dane wydanie ma rzeczywiste pliki. Przy błędzie sieci lub limicie API pozostaje link do GitHub Releases. Edytor nie jest uruchamiany na stronie; działa na komputerze użytkownika.

## Budowanie i publikacja

```bash
python scripts/build-site.py
```

Skrypt kopiuje wybrane materiały, lokalny font Manrope z OFL i generuje poster z rzeczywistej klatki filmu. Wynik jest w `dist/site`. Nie pobiera fontów z CDN.

Workflow **Product website** publikuje wynik do GitHub Pages po zmianach strony na `main`, albo po ręcznym uruchomieniu. W repozytorium musi być włączone **Settings → Pages → Source: GitHub Actions**. Używa minimalnych uprawnień `pages:write` i `id-token:write`; nie potrzebuje kluczy dostawców AI.

Sprawdzenie Chromium obejmuje układy 320, 390, 760, 1050 i 1440 px, brak poziomego przepełnienia, FAQ, ograniczenie ruchu, odtwarzanie filmu oraz przyciski trzech instalatorów na kontrolowanej odpowiedzi wydań. Po wdrożeniu dodatkowo sprawdzany jest rzeczywisty publiczny adres.
