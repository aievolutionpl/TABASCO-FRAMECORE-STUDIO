# Wspólny montaż · szkic lekcji

Edytowalny przykład siedmiu etapów historii. 21 sekund, 640 × 360, 24 FPS. Tekst, kształty, logo i animacje są oddzielnymi klipami. To krótki prototyp typograficzny bez lektora i muzyki; nie jest ukończoną lekcją edukacyjną. Opisy przejść wymagają dopracowania w montażu.

Z katalogu repozytorium utwórz własną kopię przykładu w bibliotece projektów:

```bash
python -c 'from framecore.store import Store; from framecore.sample import create_creator_pack; print(create_creator_pack(Store(), "visual-lesson")["project"]["id"])'
python framecore.py editor
```

Wybierz projekt **Człowiek + agent · wspólny montaż**. Przeciągnij własne zdjęcie na klip logo lub użyj **Podmień materiał**. Czas i geometria klipu zostaną zachowane. W **Plan scen** otwórz **Cel i tekst lektora**, aby uzupełnić każdą scenę. Przed finalnym eksportem dodaj rzeczywiste audio, sprawdź napisy i wykonaj przegląd produkcyjny.

[Film roboczy](../../assets/framecore-visual-lesson-demo.mp4) · [Plansza klatek](../../assets/framecore-visual-lesson-review.jpg) · [Instrukcja montażu](../../docs/COLLABORATIVE_EDITING.md).

Logo jest własnym materiałem projektu; font Manrope jest lokalnie dostarczany przez bibliotekę studia na licencji OFL. [Informacje o licencjach](../../THIRD_PARTY_NOTICES.md).
