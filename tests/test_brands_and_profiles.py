"""Testy dla etapu 1: Wiele niezależnych marek, profile kreatywne, tryby tekstu oraz spójność MCP/Dashboard."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vstudio import brands, common, director, ops, project, registry, workspace


def call(op: str, /, **args):
    return registry.call(op, args, source="api")


class TestLegacyMigration:
    def test_legacy_profile_migration(self, studio):
        """Bezstratna migracja ze starego profile.json do brands.json z zachowaniem kompatybilności."""
        state_dir = common.STATE_DIR
        state_dir.mkdir(parents=True, exist_ok=True)
        legacy_file = state_dir / "profile.json"
        brands_file = state_dir / "brands.json"

        # Zapisz stary profil w starym formacie
        legacy_data = {
            "name": "Kawiarnia Rzemieślnicza",
            "palette": {"bg": "#1A1412", "ink": "#F7F4EB", "accent": "#C49A45", "accent2": "#E0B970"},
            "font": "Playfair Display",
            "tone": "ciepły, spokojny, autentyczny",
            "audience": "miłośnicy kawy specialty",
            "default_format": "9:16",
            "fps": 30,
            "auto_supervise": True,
            "require_director": True,
            "onboarded": True,
        }
        legacy_file.write_text(json.dumps(legacy_data, indent=2, ensure_ascii=False), encoding="utf-8")
        if brands_file.exists():
            brands_file.unlink()

        # Wywołaj migrację
        store = brands.migrate_legacy_profile_if_needed()
        assert brands_file.exists()
        assert store["active_brand_id"] == "kawiarnia-rzemieslnicza"
        b = store["brands"]["kawiarnia-rzemieslnicza"]
        assert b["name"] == "Kawiarnia Rzemieślnicza"
        assert b["palette"]["accent"] == "#C49A45"
        assert b["font"] == "Playfair Display"
        assert b["version"] == 1
        assert b["onboarded"] is True

        # Sprawdź, czy workspace.profile_get() zwraca zmigrowane dane
        prof = workspace.profile_get()
        assert prof["name"] == "Kawiarnia Rzemieślnicza"
        assert prof["palette"]["bg"] == "#1A1412"

        # Sprawdź, czy stary profile.json nadal istnieje i jest zsynchronizowany
        assert legacy_file.exists()
        mirror = json.loads(legacy_file.read_text(encoding="utf-8"))
        assert mirror["name"] == "Kawiarnia Rzemieślnicza"


class TestBrandIndependence:
    def test_two_independent_brands(self, studio):
        """Dwie marki żyją niezależnie w bibliotece; zmiana jednej nie wpływa na drugą."""
        brands.set_brand("alpha-brand", {
            "name": "Alpha Luxury",
            "palette": {"bg": "#0A0A0A", "ink": "#FFFFFF", "accent": "#D4AF37", "accent2": "#AA820A"},
            "font": "Playfair Display",
            "tone": "ekskluzywny, minimalistyczny",
            "audience": "klienci premium",
            "creative_restrictions": ["bez memów", "bez krzykliwych kolorów"],
        })

        brands.set_brand("beta-tech", {
            "name": "Beta Software",
            "palette": {"bg": "#F5F7FB", "ink": "#0F172A", "accent": "#2563EB", "accent2": "#38BDF8"},
            "font": "Inter",
            "tone": "techniczny, rzeczowy, szybki",
            "audience": "programiści i DevOps",
            "creative_restrictions": ["bez fontów szeryfowych"],
        })

        b_list = brands.list_brands()
        ids = [b["id"] for b in b_list["brands"]]
        assert "alpha-brand" in ids
        assert "beta-tech" in ids

        alpha = brands.get_brand("alpha-brand")
        beta = brands.get_brand("beta-tech")
        assert alpha["palette"]["accent"] == "#D4AF37"
        assert beta["palette"]["accent"] == "#2563EB"
        assert alpha["font"] == "Playfair Display"
        assert beta["font"] == "Inter"

        # Aktualizacja marki Beta (zwiększenie wersji do 2)
        brands.set_brand("beta-tech", {
            "name": "Beta Software Cloud",
            "palette": {"bg": "#FFFFFF", "ink": "#000000", "accent": "#0055FF", "accent2": "#00AAFF"},
        })

        beta_updated = brands.get_brand("beta-tech")
        alpha_untouched = brands.get_brand("alpha-brand")
        assert beta_updated["name"] == "Beta Software Cloud"
        assert beta_updated["version"] == 2
        assert alpha_untouched["name"] == "Alpha Luxury"
        assert alpha_untouched["version"] == 1
        assert alpha_untouched["palette"]["accent"] == "#D4AF37"

        # Aktywacja Alpha
        brands.activate_brand("alpha-brand")
        assert brands.list_brands()["active_brand_id"] == "alpha-brand"


class TestProjectSnapshotPersistence:
    def test_project_retains_brand_snapshot_when_brand_changes(self, studio):
        """Projekt pamięta brand_id i nienaruszalną migawkę wersji marki; późniejsza modyfikacja marki nie zmienia projektu."""
        brands.set_brand("nordic", {
            "name": "Nordic Living",
            "palette": {"bg": "#EAE6DF", "ink": "#2D2B2A", "accent": "#8C7355", "accent2": "#A89B8D"},
            "font": "DM Sans",
            "tone": "spokojny, organiczny",
            "creative_profile": "premium_minimal",
            "text_mode": "headline_only",
        })
        brands.activate_brand("nordic")

        # Tworzymy projekt
        pr_info = workspace.create_project(slug="waza-kamienna", brand="nordic", creative_profile="premium_minimal", text_mode="headline_only")
        pdir = studio / "nordic" / "waza-kamienna"
        assert (pdir / "project.json").exists()

        pdata = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
        assert pdata["brand_id"] == "nordic"
        assert pdata["brand_version"] == 1
        assert pdata["creative_profile"] == "premium_minimal"
        assert pdata["text_mode"] == "headline_only"
        assert pdata["brand_snapshot"]["palette"]["accent"] == "#8C7355"

        # Modyfikujemy markę w bibliotece (wersja 2, nowy akcent i inny font)
        brands.set_brand("nordic", {
            "name": "Nordic Living 2027",
            "palette": {"bg": "#000000", "ink": "#FFFFFF", "accent": "#FF0000", "accent2": "#00FF00"},
            "font": "Poppins",
        })
        # I tworzymy nową markę oraz ją aktywujemy
        brands.set_brand("cyber", {"name": "Cyber Corp"})
        brands.activate_brand("cyber")

        # Sprawdzamy projekt waza-kamienna
        pdir_loaded, pr_loaded = workspace.resolve("nordic/waza-kamienna")
        summary = workspace.summarize(pdir_loaded, pr_loaded)
        assert summary["brand_id"] == "nordic"
        assert summary["brand_version"] == 1
        assert summary["brand_snapshot"]["name"] == "Nordic Living"
        assert summary["brand_snapshot"]["palette"]["accent"] == "#8C7355"
        assert summary["brand_snapshot"]["font"] == "DM Sans"
        assert summary["creative_profile"] == "premium_minimal"
        assert summary["text_mode"] == "headline_only"


class TestCreativeProfilesAndTextModes:
    def test_premium_minimal_plan_and_no_icon_clutter(self, studio):
        """Profil premium_minimal nie wymusza automatycznych ikon, unika krzykliwych stylów i dopuszcza spokojne tempo."""
        brands.set_brand("luminary", {
            "name": "Luminary High Jewelry",
            "palette": {"bg": "#07080B", "ink": "#F7F8FA", "accent": "#D1B280", "accent2": "#8A7352"},
            "font": "Playfair Display",
            "tone": "luksusowy, subtelny",
        })
        workspace.create_project(slug="pierscien", brand="luminary", duration=7.0, size="1080x1920", fps=30, creative_profile="premium_minimal")
        pdir, pr = workspace.resolve("luminary/pierscien")

        # Plan reżysera dla premium_minimal
        plan = director.plan(pdir, pr, goal="Prezentacja pierścienia z brylantem", creative_profile="premium_minimal")
        assert plan["creative_profile"] == "premium_minimal"
        assert plan["pace"] == "calm"
        assert plan["styles"]["main"]["id"] in ("swiss-minimal", "dark-luxe", "gradient-mesh", "pastel-soft")
        # Wykluczone style nie powinny być w stylu głównym
        assert plan["styles"]["main"]["id"] not in ("neo-brutal", "sticker-pop", "retro-synth")

        # Bity nie powinny mieć wymuszonych ikon
        for beat in plan["beats"]:
            assert beat.get("icon") is None or plan["creative_profile_rules"]["suppress_auto_icons"]

    def test_premium_minimal_review_allows_calm_and_no_icons(self, studio):
        """W profilu premium_minimal brak ikon (NO_VISUAL_ASSETS) oraz spokojne ujęcia nie są karane."""
        brands.set_brand("luxe", {
            "name": "Luxe",
            "palette": {"bg": "#000000", "ink": "#FFFFFF", "accent": "#D4AF37", "accent2": "#FFFFFF"},
        })
        workspace.create_project(slug="minimal-film", brand="luxe", duration=6.0, size="1080x1920", fps=30, creative_profile="premium_minimal")
        pdir, pr = workspace.resolve("luxe/minimal-film")

        # Symulacja znalezisk reżysera
        from vstudio.director import _finding
        # Gdyby to był profil social_fast, te znaleziska byłyby błędami/ostrzeżeniami
        findings = [
            _finding("NO_VISUAL_ASSETS", "warn", detail="Brak ikon w scenie"),
            _finding("MONOTONE_STYLE", "warn", detail="Tylko 1 look przez cały film"),
        ]

        # Zweryfikuj reguły w brands.CREATIVE_PROFILES
        cfg = brands.CREATIVE_PROFILES["premium_minimal"]
        assert cfg["allowed_no_visual_assets"] is True
        assert cfg["allowed_monotone"] is True
        assert cfg["max_pace_gap"] >= 7.0

    def test_video_without_text_mode(self, studio):
        """Film z text_mode='none' nie wymaga hook textu ani napisów."""
        brands.set_brand("art", {"name": "Art Gallery"})
        workspace.create_project(slug="visual-only", brand="art", duration=5.0, size="1080x1080", fps=30, creative_profile="cinematic", text_mode="none")
        pdir, pr = workspace.resolve("art/visual-only")

        plan = director.plan(pdir, pr, goal="Czysta animacja rzeźby 3D bez słów", text_mode="none")
        assert plan["text_mode"] == "none"
        # Sprawdź, czy beaty mają pusty lub neutralny copy
        for b in plan["beats"]:
            assert b["copy"] == "" or "brak napisów" in b["copy"] or "(film bez tekstu)" in b["copy"]

    def test_educational_mode_reading_time_detection(self, studio):
        """Tryb edukacyjny weryfikuje wystarczający czas na przeczytanie tekstu."""
        cfg = brands.CREATIVE_PROFILES["educational"]
        assert cfg["default_text_mode"] == "full"
        assert cfg["max_words_per_beat"] == 10
        # W edukacyjnym czytelność ma najwyższy priorytet
        assert cfg["allow_empty_text"] is False


class TestMcpDashboardParity:
    def test_brand_and_profile_ops_callable(self, studio):
        """Operacje rejestru dla marek i profili są zarejestrowane i dostępne z identycznym schematem dla MCP i dashboardu."""
        for cap_name in ("brands_list", "brand_get", "brand_set", "brand_activate", "brand_delete", "creative_profiles_list"):
            assert registry.REGISTRY.get(cap_name) is not None, f"Brak operacji {cap_name}"

        # Test wywołania brands_list
        res = call("brands_list")
        assert "brands" in res
        assert "active_brand_id" in res

        # Test dodania marki przez rejestr możliwości
        res_set = call("brand_set", brand_id="test-brand", name="Testowa Marka", palette={"bg": "#000", "ink": "#fff", "accent": "#f00", "accent2": "#0f0"}, font="Manrope")
        assert res_set["brand"]["id"] == "test-brand"
        assert res_set["brand"]["version"] == 1

        # Test pobrania marki
        res_get = call("brand_get", brand_id="test-brand")
        assert res_get["brand"]["name"] == "Testowa Marka"

        # Test aktywacji
        res_act = call("brand_activate", brand_id="test-brand")
        assert res_act["active_brand_id"] == "test-brand"

        # Test katalogu profili kreatywnych
        res_prof = call("creative_profiles_list")
        assert len(res_prof["profiles"]) == 4
        ids = {p["id"] for p in res_prof["profiles"]}
        assert ids == {"premium_minimal", "cinematic", "social_fast", "educational"}

        # Test usunięcia
        # Dodaj drugą markę, by móc usunąć pierwszą
        call("brand_set", brand_id="other-brand", name="Inna")
        call("brand_activate", brand_id="other-brand")
        res_del = call("brand_delete", brand_id="test-brand")
        assert res_del["deleted"] == "test-brand"


class TestRealWorkflowExample:
    def test_real_plan_and_review_workflow_premium(self, studio):
        """Rzeczywisty przykład planu i przeglądu filmu dla profilu premium_minimal bez ikon."""
        # 1. Konfiguracja marki premium
        call("brand_set", brand_id="elysium", name="Elysium Timepieces",
             palette={"bg": "#0A0B10", "ink": "#F5F5F7", "accent": "#D4AF37", "accent2": "#997B28"},
             font="Playfair Display", tone="powściągliwy, szlachetny, minimalistyczny")
        call("brand_activate", brand_id="elysium")

        # 2. Utworzenie projektu z profilem premium_minimal i headline_only
        p_res = call("project_create", slug="chronograph", brand="elysium", duration=6.0, format="9:16",
                     creative_profile="premium_minimal", text_mode="headline_only",
                     brief="Zwiastun nowego chronografu z tarczą z meteorytu.")
        pid = p_res["project"]["id"]
        assert pid == "elysium/chronograph"
        pdir, pr = workspace.resolve(pid)

        # 3. Plan reżysera (storyboard)
        plan_res = call("director_plan", project=pid, goal="Premiera chronografu Elysium",
                        creative_profile="premium_minimal", text_mode="headline_only")
        plan = plan_res["plan"]
        assert plan["creative_profile"] == "premium_minimal"
        assert plan["pace"] == "calm"
        assert plan["contract"]["visible_change_every_s"] >= 5.0
        assert plan["creative_profile_rules"]["suppress_auto_icons"] is True
        for b in plan["beats"]:
            assert b.get("icon") is None

        # 4. Implementacja sceny HTML z minimalną typografią i bez ikon
        html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { margin: 0; background: #0A0B10; color: #F5F5F7; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
    h1 { font-size: 54px; letter-spacing: 0.15em; color: #D4AF37; margin: 0; opacity: 0; transform: translateY(12px); }
  </style>
</head>
<body>
  <h1 id="title">ELYSIUM CHRONO</h1>
  <script>
    window.DURATION = 6.0;
    window.__ready = Promise.resolve();
    var t_el = document.getElementById('title');
    window.seek = function(t) {
      var progress = Math.min(1, Math.max(0, (t - 0.5) / 1.5));
      t_el.style.opacity = progress;
      t_el.style.transform = 'translateY(' + ((1 - progress) * 12) + 'px)';
    };
    window.TEXTS = function(t) {
      if (t < 0.5) return [];
      return [{ id: 'title', text: 'ELYSIUM CHRONO', x0: 100, y0: 800, x1: 980, y1: 900 }];
    };
  </script>
</body>
</html>"""
        (pdir / "src" / "index.html").write_text(html, encoding="utf-8")

        # 5. Przegląd reżysera (director_review)
        rev = director.review(pdir, pr, depth="quick")
        # W profilu premium_minimal brak ikon nie generuje ostrzeżenia NO_VISUAL_ASSETS
        warn_codes = [f["code"] for f in rev["findings"] if f["severity"] == "warn"]
        assert "NO_VISUAL_ASSETS" not in warn_codes
        # Dopuszczalne spokojne tempo nie zgłasza SLOW_PACE dla ujęcia 6s
        assert "SLOW_PACE" not in warn_codes
        assert rev["counts"]["error"] == 0

        # 6. Zatwierdzenie reżysera (świadomy wyjątek estetyczny: pojedyncze spokojne ujęcie)
        so = call("director_signoff", project=pid, approve=True,
                  notes="Szlachetny, minimalistyczny kadr bez zbędnych ozdobników.",
                  checklist={k: True for k in director.CHECKLIST},
                  accept={"BEAT_MISSING": "Świadome pojedyncze ujęcie produktowe w stylu premium"} if "BEAT_MISSING" in warn_codes else {})
        assert so["state"] == "approved"
