"""Biblioteka stylów reżysera: jak dobrać wygląd filmu do celu, platformy i tonu marki i jak go zmieniać co kilka sekund.

Film nie może być cały w jednym „systemie”: stała jest MARKA (paleta, font, ton), a zmienia się TRAKTOWANIE wizualne
(układ, tło, język ruchu, przejście). Styl to gotowy zestaw takiego traktowania. Reżyser (`director.plan`) wybiera styl
główny i dwa akcenty o RÓŻNYCH układach, a potem przydziela je do bitów storyboardu.

Dane są po angielsku tam, gdzie czyta je model (receptury, zasady), a nazwy i opisy dla człowieka po polsku.
"""
from __future__ import annotations

import re
import unicodedata

from .common import StudioError

#: układy bitów: co jest na ekranie. Reżyser dobiera je do roli bitu i stylu.
LAYOUTS: dict[str, str] = {
    "big-type": "1-6 words, huge, one accent word; the whole beat is the sentence",
    "icon-grid": "3-6 icons in a grid or row with 2-word labels, popping in with a stagger",
    "device-mock": "phone or browser frame with UI moving inside it; 1-2 callouts pointing at the detail that matters",
    "split-compare": "before/after or A/B in two halves with a divider that moves",
    "number-counter": "one huge number counting up with a unit and a short caption",
    "product-hero": "one object centred, slow rotate or push-in, soft shadow, 1 label",
    "quote-card": "testimonial card: quote, name, stars or avatar",
    "full-bleed-caption": "full-frame texture, gradient or photo plate with a lower-third caption",
    "list-reveal": "3 lines revealed one by one, each with a check icon",
    "cta-card": "brand mark, one action line, handle or URL; holds still for at least 1.5 s",
}

#: przejścia między bitami: każde da się zrobić deterministycznie w GSAP (stany startowe w tl.set, brak losowości).
TRANSITIONS: dict[str, dict] = {
    "punch-in": {"name": "Uderzenie (punch-in)", "sound": "hit",
                 "how": "Outgoing layer cuts away on a 2-frame accent flash; incoming layer scales 1.12 -> 1 in 0.35 s, ease expo.out."},
    "wipe-slide": {"name": "Wsuw z maską", "sound": "whoosh",
                   "how": "Incoming layer clip-path inset(0 100% 0 0) -> inset(0) in 0.45 s power3.inOut while the outgoing layer drifts -8% x."},
    "push": {"name": "Pchnięcie", "sound": "whoosh",
             "how": "Both layers move together: outgoing xPercent 0 -> -100, incoming 100 -> 0, 0.5 s power3.inOut."},
    "morph": {"name": "Morf", "sound": "pop",
              "how": "One shared element animates width, height, borderRadius and background into the next beat's element (0.6 s power2.inOut); everything else fades in around it."},
    "flash-cut": {"name": "Błysk", "sound": "hit",
                  "how": "Two frames of a flat accent or white layer (opacity 1 for 0.07 s), swap the content underneath, fade the flash out in 0.12 s."},
    "mask-circle": {"name": "Okrągła maska", "sound": "whoosh",
                    "how": "Incoming layer clip-path circle(0% at 50% 50%) -> circle(75% at 50% 50%) in 0.6 s expo.out."},
    "slide-stack": {"name": "Stos kart", "sound": "pop",
                    "how": "New cards slide up from y 110% with a 0.08 s stagger over the old content, 0.5 s back.out(1.2)."},
    "zoom-through": {"name": "Przelot", "sound": "whoosh",
                     "how": "Outgoing layer scales 1 -> 3 while fading out, incoming scales 0.7 -> 1: reads as one camera flying through (0.6 s power3.in then out)."},
    "glitch-stutter": {"name": "Zacięcie (glitch)", "sound": "tick",
                       "how": "Three fixed offsets via tl.set at t, t+0.04, t+0.08 (x +14px, -9px, 0) on the outgoing layer, then cut. No Math.random."},
    "blur-dissolve": {"name": "Rozmycie", "sound": "reveal",
                      "how": "Outgoing filter blur(0 -> 18px) with opacity 1 -> 0 while incoming goes blur(18px -> 0) with opacity 0 -> 1 (0.5 s sine.inOut). Keep blur under 24px."},
    "tilt-flip": {"name": "Obrót karty", "sound": "pop",
                  "how": "Parent has perspective 1200px; outgoing child rotationX 0 -> -90, incoming 90 -> 0 (0.5 s back.out(1.1))."},
    "shutter": {"name": "Żaluzja", "sound": "whoosh",
                "how": "6 horizontal bars scaleY 0 -> 1 with a 0.05 s stagger cover the frame, content swaps, bars scaleY 1 -> 0 from the other end."},
}

_FONT_NOTE = ("Polish text needs Latin Extended (ą ć ę ł ń ó ś ź ż). Load the font with subset latin-ext (or vendor a full-coverage file) and "
              "keep a system fallback; director_review reports GLYPH_MISSING when a letter falls back to another font.")

#: look: tło + układ dominujący; służy do wybierania akcentów, które WYGLĄDAJĄ inaczej niż styl główny
STYLES: list[dict] = [
    {"id": "kinetic-type", "name": "Kinetyczna typografia", "tagline": "Słowa uderzają w kadr, jedno słowo w kolorze akcentu.",
     "look": {"bg": "dark", "layout": "type"}, "energy": 5,
     "tags": ["bold", "punchy", "confident", "loud", "szybki", "mocny", "odważny", "dynamiczny"],
     "goals": ["announcement", "promo", "launch", "hook", "ogłoszenie", "promocja", "premiera"],
     "platforms": ["reels", "tiktok", "shorts", "story"],
     "palette": {"bg": "#0B0B0F", "ink": "#FFFFFF", "accent": "#FF3B30", "accent2": "#FFD60A"},
     "type": {"stack": "'Archivo Black','Inter',system-ui,sans-serif", "case": "upper", "weight": 900, "tracking": "-0.02em", "min_size": "6% of frame height"},
     "motion": {"duration": "0.25-0.6 s", "ease": "expo.out, back.out(1.6), power4.inOut", "stagger": "0.05-0.08 s per word", "camera": "punch-in 3-6% on every hit"},
     "transitions": ["punch-in", "flash-cut", "wipe-slide", "zoom-through"],
     "layouts": ["big-type", "list-reveal", "number-counter", "cta-card"],
     "assets": ["arrows", "underline doodle", "starburst", "exclamation marks"],
     "pairs_with": ["sticker-pop", "gradient-mesh", "neo-brutal", "retro-synth"],
     "composition": ["One idea per beat, 1-6 words.", "Scale contrast of at least 1:4 between the key word and the rest.",
                     "Colour only the word that carries the meaning.", "Let the last word stand still for 8 frames before anything moves."],
     "avoid": ["Paragraphs", "Slow fades", "More than 2 type sizes in one beat"],
     "recipe": (":root{--bg:#0B0B0F;--ink:#fff;--accent:#FF3B30}\n"
                ".w{display:inline-block;font:900 12vw/.95 'Archivo Black',Inter,system-ui,sans-serif;text-transform:uppercase;letter-spacing:-.02em}\n"
                "// word i: tl.set('#w'+i,{yPercent:110,rotation:4},0); tl.to('#w'+i,{yPercent:0,rotation:0,duration:.45,ease:'expo.out'},t0+i*.07);\n"
                "// key word: tl.to('#hit',{color:'#FF3B30',scale:1.08,duration:.18,ease:'back.out(2)'},t0+.5);  // then hold still 8 frames")},
    {"id": "glass-ui", "name": "Szkło i interfejs", "tagline": "Matowe panele nad gradientem, makiety UI z paralaksą.",
     "look": {"bg": "gradient", "layout": "ui"}, "energy": 3,
     "tags": ["tech", "saas", "modern", "app", "clean", "nowoczesny", "aplikacja", "technologia"],
     "goals": ["product", "saas", "app", "explainer", "demo", "produkt", "aplikacja"],
     "platforms": ["reels", "feed", "linkedin", "shorts", "web"],
     "palette": {"bg": "#0F1226", "ink": "#F5F7FF", "accent": "#7C5CFF", "accent2": "#2DE2E6"},
     "type": {"stack": "'Inter','Segoe UI',system-ui,sans-serif", "case": "sentence", "weight": 600, "tracking": "-0.01em", "min_size": "3.5% of frame height"},
     "motion": {"duration": "0.5-0.9 s", "ease": "power3.out, power2.inOut", "stagger": "0.1 s per panel", "camera": "slow parallax: panels at different speeds"},
     "transitions": ["push", "morph", "slide-stack", "blur-dissolve"],
     "layouts": ["device-mock", "icon-grid", "list-reveal", "big-type"],
     "assets": ["UI chips", "app icons", "soft glows", "mesh gradient"],
     "pairs_with": ["kinetic-type", "data-story", "gradient-mesh", "isometric-3d"],
     "composition": ["Cards at 3 depths: back (blurred, slow), mid (content), front (callouts, fast).",
                     "backdrop-filter blur 14-24px, never animate the blur radius.", "A 1px light border and a soft shadow make glass read as glass."],
     "avoid": ["Blur over 30px (slow and muddy)", "Text on glass without a darker tint behind it (LOW_CONTRAST)"],
     "recipe": (".card{background:rgba(255,255,255,.08);backdrop-filter:blur(18px);border:1px solid rgba(255,255,255,.18);border-radius:28px;box-shadow:0 20px 60px rgba(0,0,0,.35)}\n"
                "body{background:radial-gradient(60% 50% at 20% 10%,#7C5CFF55,transparent),radial-gradient(50% 50% at 90% 90%,#2DE2E655,transparent),#0F1226}\n"
                "// panel i: tl.set('#p'+i,{y:80,opacity:0},0); tl.to('#p'+i,{y:0,opacity:1,duration:.7,ease:'power3.out'},t0+i*.1);\n"
                "// parallax: tl.to('.layer-back',{y:-30,duration:D,ease:'none'},t0); tl.to('.layer-front',{y:-90,duration:D,ease:'none'},t0);")},
    {"id": "neo-brutal", "name": "Neo-brutalizm", "tagline": "Grube obrysy, twarde cienie, płaskie kolory i naklejki.",
     "look": {"bg": "color", "layout": "graphic"}, "energy": 4,
     "tags": ["playful", "bold", "youthful", "quirky", "gen-z", "fun", "zabawny", "młodzieżowy", "odważny"],
     "goals": ["launch", "promo", "ugc", "event", "social", "premiera", "wydarzenie"],
     "platforms": ["reels", "tiktok", "shorts", "story", "feed"],
     "palette": {"bg": "#FFF4D6", "ink": "#111111", "accent": "#FF5C39", "accent2": "#3A6BFF"},
     "type": {"stack": "'Space Grotesk','Inter',system-ui,sans-serif", "case": "mixed", "weight": 700, "tracking": "-0.02em", "min_size": "4% of frame height"},
     "motion": {"duration": "0.3-0.5 s", "ease": "back.out(1.7), power2.out", "stagger": "0.06 s", "camera": "none; objects bounce, the frame stays flat"},
     "transitions": ["slide-stack", "shutter", "flash-cut", "tilt-flip"],
     "layouts": ["big-type", "icon-grid", "split-compare", "quote-card"],
     "assets": ["stickers", "arrows", "stars", "price tags", "speech bubbles"],
     "pairs_with": ["sticker-pop", "kinetic-type", "paper-cut", "swiss-minimal"],
     "composition": ["4px black outline on every shape, hard offset shadow 8px 8px 0 #111.", "Two flat colours plus black, no gradients.",
                     "Rotate stickers 2-6 degrees, never text blocks."],
     "avoid": ["Soft shadows", "Thin lines", "More than 3 colours"],
     "recipe": (".box{background:var(--accent);border:4px solid #111;box-shadow:8px 8px 0 #111;border-radius:14px;padding:.6em .9em}\n"
                "// sticker i: tl.set('#s'+i,{scale:0,rotation:-12},0); tl.to('#s'+i,{scale:1,rotation:-4,duration:.4,ease:'back.out(1.7)'},t0+i*.08);\n"
                "// shadow press: tl.to('.btn',{x:6,y:6,boxShadow:'2px 2px 0 #111',duration:.1},tPress);")},
    {"id": "swiss-minimal", "name": "Szwajcarski minimalizm", "tagline": "Siatka, dużo światła, jeden kolor akcentu.",
     "look": {"bg": "light", "layout": "type"}, "energy": 2,
     "tags": ["minimal", "premium", "editorial", "calm", "corporate", "clean", "elegancki", "spokojny", "firmowy", "minimalistyczny"],
     "goals": ["educational", "brand", "b2b", "announcement", "report", "edukacja", "marka"],
     "platforms": ["linkedin", "feed", "web", "presentation"],
     "palette": {"bg": "#F4F2EE", "ink": "#111111", "accent": "#E63B2E", "accent2": "#1F3A5F"},
     "type": {"stack": "'Inter','Helvetica Neue',Arial,sans-serif", "case": "sentence", "weight": 600, "tracking": "-0.03em", "min_size": "3.5% of frame height"},
     "motion": {"duration": "0.6-1.0 s", "ease": "power3.inOut, expo.out", "stagger": "0.12 s per line", "camera": "very slow drift, 1-2%"},
     "transitions": ["push", "wipe-slide", "blur-dissolve", "morph"],
     "layouts": ["big-type", "list-reveal", "number-counter", "split-compare"],
     "assets": ["thin rules", "numbered labels", "single-colour icons", "grid lines"],
     "pairs_with": ["data-story", "neo-brutal", "cinematic-captions", "glass-ui"],
     "composition": ["12-column grid, text hangs from the left edge.", "Whitespace is at least half of the frame.",
                     "Small numbered labels (01, 02) give rhythm without decoration."],
     "avoid": ["Drop shadows", "More than one accent colour", "Centred paragraphs"],
     "recipe": (".t{font:600 7vw/1.02 Inter,'Helvetica Neue',Arial,sans-serif;letter-spacing:-.03em;color:#111}\n"
                "// line i: tl.set('#l'+i,{clipPath:'inset(0 0 100% 0)',y:24},0); tl.to('#l'+i,{clipPath:'inset(0 0 0% 0)',y:0,duration:.7,ease:'expo.out'},t0+i*.12);\n"
                "// rule: tl.set('#rule',{scaleX:0,transformOrigin:'left'},0); tl.to('#rule',{scaleX:1,duration:.8,ease:'power3.inOut'},t0);")},
    {"id": "dark-luxe", "name": "Ciemny luksus", "tagline": "Czerń, szampańskie złoto, szeryfy i powolne odsłony.",
     "look": {"bg": "dark", "layout": "type"}, "energy": 2,
     "tags": ["premium", "luxury", "elegant", "cinematic", "fashion", "jewelry", "luksus", "elegancki", "premium", "perfumy", "biżuteria"],
     "goals": ["product", "brand", "event", "launch", "produkt", "marka"],
     "platforms": ["feed", "reels", "web", "story"],
     "palette": {"bg": "#0A0A0A", "ink": "#F3EBDD", "accent": "#C9A45C", "accent2": "#8C7A5B"},
     "type": {"stack": "'Playfair Display','Cormorant Garamond',Georgia,serif", "case": "mixed", "weight": 500, "tracking": "0.01em", "min_size": "4% of frame height"},
     "motion": {"duration": "0.9-1.6 s", "ease": "power2.inOut, sine.inOut", "stagger": "0.18 s", "camera": "slow push-in 4-6% over the whole beat"},
     "transitions": ["blur-dissolve", "mask-circle", "wipe-slide", "morph"],
     "layouts": ["product-hero", "full-bleed-caption", "big-type", "cta-card"],
     "assets": ["thin gold rules", "light leaks", "dust particles", "monograms"],
     "pairs_with": ["cinematic-captions", "swiss-minimal", "gradient-mesh", "isometric-3d"],
     "composition": ["Centred, symmetrical, lots of black.", "One gold accent at a time.", "Highlights on the product come from a moving light, not from colour."],
     "avoid": ["Fast cuts", "Bright saturated colours", "More than one typeface family besides the serif"],
     "recipe": ("body{background:radial-gradient(80% 60% at 50% 40%,#1a1712,#0A0A0A)}\n"
                ".gold{color:#C9A45C;font:500 6vw/1.1 'Playfair Display',Georgia,serif}\n"
                "// reveal: tl.set('#h',{opacity:0,y:18,letterSpacing:'.08em'},0); tl.to('#h',{opacity:1,y:0,letterSpacing:'.01em',duration:1.2,ease:'power2.out'},t0);\n"
                "// push-in the whole stage: tl.to('#stage',{scale:1.05,duration:D,ease:'sine.inOut'},t0);")},
    {"id": "retro-synth", "name": "Retro synthwave", "tagline": "Neonowy zachód słońca, siatka w perspektywie, chrom.",
     "look": {"bg": "gradient", "layout": "graphic"}, "energy": 4,
     "tags": ["retro", "nostalgic", "music", "gaming", "neon", "80s", "bold", "muzyka", "gry", "nostalgia", "neonowy"],
     "goals": ["event", "entertainment", "promo", "launch", "wydarzenie", "rozrywka"],
     "platforms": ["reels", "tiktok", "shorts", "story"],
     "palette": {"bg": "#12002B", "ink": "#FFFFFF", "accent": "#FF2E97", "accent2": "#00E5FF"},
     "type": {"stack": "'Orbitron','Inter',system-ui,sans-serif", "case": "upper", "weight": 800, "tracking": "0.04em", "min_size": "5% of frame height"},
     "motion": {"duration": "0.4-0.8 s", "ease": "power2.out, expo.inOut", "stagger": "0.07 s", "camera": "the grid floor scrolls forward continuously (looped distance)"},
     "transitions": ["flash-cut", "glitch-stutter", "zoom-through", "shutter"],
     "layouts": ["big-type", "full-bleed-caption", "list-reveal", "cta-card"],
     "assets": ["sun disc", "perspective grid", "palm silhouettes", "scanlines"],
     "pairs_with": ["kinetic-type", "sticker-pop", "neo-brutal", "terminal-code"],
     "composition": ["Horizon at 55-60% of the frame, sun sliced by horizontal bars.", "Glow = text-shadow in the accent colour, 0 0 24px.",
                     "Grid scroll speed is a fixed distance per loop so the loop closes."],
     "avoid": ["Flat pastel colours", "Serif fonts", "Animated blur (slow)"],
     "recipe": (".sun{width:46vw;height:46vw;border-radius:50%;background:linear-gradient(#FFD60A,#FF2E97)}\n"
                ".glow{color:#fff;text-shadow:0 0 24px #FF2E97,0 0 60px #FF2E9788}\n"
                "// grid scroll (closes the loop): tl.fromTo('#grid',{backgroundPositionY:0},{backgroundPositionY:'120px',duration:DUR,ease:'none'},0);")},
    {"id": "sticker-pop", "name": "Naklejki i emoji", "tagline": "Kolorowe naklejki z białym obrysem wyskakują na płaskim tle.",
     "look": {"bg": "color", "layout": "collage"}, "energy": 5,
     "tags": ["fun", "playful", "friendly", "consumer", "young", "food", "retail", "zabawny", "przyjazny", "jedzenie", "sklep"],
     "goals": ["promo", "ugc", "social", "food", "retail", "sale", "promocja", "wyprzedaż"],
     "platforms": ["reels", "tiktok", "shorts", "story"],
     "palette": {"bg": "#FFD93D", "ink": "#1B1B1B", "accent": "#FF4D6D", "accent2": "#4D96FF"},
     "type": {"stack": "'Baloo 2','Poppins',system-ui,sans-serif", "case": "mixed", "weight": 800, "tracking": "-0.01em", "min_size": "5% of frame height"},
     "motion": {"duration": "0.3-0.5 s", "ease": "back.out(2), elastic.out(1,0.6) for one hero sticker", "stagger": "0.05 s", "camera": "none"},
     "transitions": ["slide-stack", "tilt-flip", "punch-in", "shutter"],
     "layouts": ["icon-grid", "big-type", "list-reveal", "quote-card"],
     "assets": ["icons as stickers (white 8px outline)", "emoji", "stars", "price badges"],
     "pairs_with": ["kinetic-type", "neo-brutal", "paper-cut", "pastel-soft"],
     "composition": ["Every sticker has a white outline (drop-shadow filter x4) and a soft shadow.", "5-9 stickers per beat max, one hero in front.",
                     "Stickers land with overshoot, then sit still."],
     "avoid": ["Tiny stickers (under 8% of frame width)", "Stickers over text"],
     "recipe": (".st{filter:drop-shadow(3px 0 0 #fff) drop-shadow(-3px 0 0 #fff) drop-shadow(0 3px 0 #fff) drop-shadow(0 -3px 0 #fff) drop-shadow(0 8px 14px rgba(0,0,0,.25))}\n"
                "// sticker i: tl.set('#s'+i,{scale:0,rotation:-18},0); tl.to('#s'+i,{scale:1,rotation:(i%2?6:-6),duration:.45,ease:'back.out(2)'},t0+i*.05);")},
    {"id": "gradient-mesh", "name": "Płynny gradient", "tagline": "Zorza z rozmytych plam, które powoli się przelewają.",
     "look": {"bg": "gradient", "layout": "type"}, "energy": 3,
     "tags": ["modern", "calm", "wellness", "saas", "soft", "creative", "nowoczesny", "spokojny", "kreatywny", "aurora"],
     "goals": ["brand", "product", "explainer", "announcement", "marka", "produkt"],
     "platforms": ["reels", "feed", "linkedin", "story", "web"],
     "palette": {"bg": "#101022", "ink": "#FFFFFF", "accent": "#8E7CFF", "accent2": "#FF7AB6"},
     "type": {"stack": "'Manrope','Inter',system-ui,sans-serif", "case": "sentence", "weight": 700, "tracking": "-0.02em", "min_size": "4% of frame height"},
     "motion": {"duration": "0.8-1.4 s", "ease": "sine.inOut, power2.inOut", "stagger": "0.1 s", "camera": "blobs drift 6-12% of the frame over the beat"},
     "transitions": ["morph", "blur-dissolve", "mask-circle", "push"],
     "layouts": ["big-type", "full-bleed-caption", "icon-grid", "cta-card"],
     "assets": ["blurred blobs", "grain overlay", "rounded chips", "line icons"],
     "pairs_with": ["glass-ui", "kinetic-type", "swiss-minimal", "pastel-soft"],
     "composition": ["3-4 blobs (radial gradients) at different sizes, each drifting on its own path.", "Add 3-5% grain so the gradient does not band.",
                     "Type is white on the darkest part of the mesh."],
     "avoid": ["Hard edges between colours", "Animating blur radius"],
     "recipe": (".blob{position:absolute;width:60vw;height:60vw;border-radius:50%;filter:blur(60px);opacity:.8}\n"
                "// drift: tl.to('#b1',{x:'18vw',y:'-10vh',duration:D,ease:'sine.inOut'},0); tl.to('#b2',{x:'-14vw',y:'12vh',duration:D,ease:'sine.inOut'},0);\n"
                "// loop closes if the last tween returns to the first position (tl.to back to 0 over the last third).")},
    {"id": "isometric-3d", "name": "Obiekt 3D", "tagline": "Bohater w CSS 3D: obrót, głębia, pływające chipy.",
     "look": {"bg": "gradient", "layout": "3d"}, "energy": 3,
     "tags": ["product", "tech", "premium", "hardware", "gadget", "produkt", "technologia", "sprzęt"],
     "goals": ["product", "launch", "demo", "produkt", "premiera"],
     "platforms": ["reels", "feed", "web", "shorts"],
     "palette": {"bg": "#0E1420", "ink": "#EAF2FF", "accent": "#4DA3FF", "accent2": "#FFB84D"},
     "type": {"stack": "'Inter','Segoe UI',system-ui,sans-serif", "case": "sentence", "weight": 600, "tracking": "-0.01em", "min_size": "3.5% of frame height"},
     "motion": {"duration": "0.8-1.5 s", "ease": "power3.inOut, sine.inOut", "stagger": "0.12 s", "camera": "object rotates 20-40 degrees over the beat; chips orbit slowly"},
     "transitions": ["zoom-through", "morph", "push", "mask-circle"],
     "layouts": ["product-hero", "icon-grid", "device-mock", "cta-card"],
     "assets": ["floating chips with icons", "soft floor shadow", "light sweep"],
     "pairs_with": ["glass-ui", "dark-luxe", "kinetic-type", "data-story"],
     "composition": ["perspective on the PARENT, rotate a child with rotationY.", "Fake thickness with a stack of planes at different translateZ.",
                     "A floor shadow (ellipse, blurred) that scales with the object sells the depth."],
     "avoid": ["Rotating more than 60 degrees (back faces look wrong)", "perspective on the rotated element itself"],
     "recipe": (".stage{perspective:1200px}.obj{transform-style:preserve-3d}\n"
                "// tl.set('#obj',{rotationY:-28,rotationX:8},0); tl.to('#obj',{rotationY:28,duration:D,ease:'sine.inOut'},0);\n"
                "// floor shadow follows: tl.to('#shadow',{scaleX:1.1,duration:D,ease:'sine.inOut'},0);")},
    {"id": "data-story", "name": "Opowieść z danych", "tagline": "Liczniki, słupki i linie, które rysują się na oczach widza.",
     "look": {"bg": "light", "layout": "data"}, "energy": 3,
     "tags": ["data", "analytical", "b2b", "finance", "trustworthy", "proof", "dane", "analityczny", "finanse", "wyniki", "raport"],
     "goals": ["educational", "report", "proof", "b2b", "explainer", "edukacja", "wyniki"],
     "platforms": ["linkedin", "feed", "reels", "web"],
     "palette": {"bg": "#F7FAFC", "ink": "#0F172A", "accent": "#2563EB", "accent2": "#F59E0B"},
     "type": {"stack": "'Inter','Segoe UI',system-ui,sans-serif", "case": "sentence", "weight": 700, "tracking": "-0.02em", "min_size": "3.5% of frame height"},
     "motion": {"duration": "0.6-1.2 s", "ease": "power3.out, expo.out for counters", "stagger": "0.1 s per bar", "camera": "none; the data is the motion"},
     "transitions": ["push", "morph", "wipe-slide", "slide-stack"],
     "layouts": ["number-counter", "split-compare", "list-reveal", "big-type"],
     "assets": ["bars", "line chart", "donut", "arrows with %"],
     "pairs_with": ["swiss-minimal", "glass-ui", "kinetic-type", "neo-brutal"],
     "composition": ["One number per beat, at least 25% of the frame height.", "Count up with ease expo.out and format with a thin space (12 400).",
                     "Annotate the one data point that matters, grey out the rest."],
     "avoid": ["Charts with more than 5 series", "Tiny axis labels (TEXT_TINY)"],
     "recipe": ("// counter without callbacks: build the value from t inside seek(): n = Math.round(target * easeOutExpo(clamp((t - t0) / 1.2, 0, 1))); el.textContent = fmt(n);\n"
                "// line draw: path.style.strokeDasharray = L; tl.fromTo(path,{strokeDashoffset:L},{strokeDashoffset:0,duration:1,ease:'power2.inOut'},t0);\n"
                "// bar i: tl.set('#bar'+i,{scaleY:0,transformOrigin:'bottom'},0); tl.to('#bar'+i,{scaleY:1,duration:.7,ease:'power3.out'},t0+i*.1);")},
    {"id": "paper-cut", "name": "Papierowy collage", "tagline": "Warstwy papieru, miękkie cienie i ruch jak w poklatkowej animacji.",
     "look": {"bg": "color", "layout": "collage"}, "energy": 3,
     "tags": ["craft", "warm", "handmade", "food", "lifestyle", "kids", "rzemiosło", "ciepły", "ręcznie", "jedzenie", "rodzina"],
     "goals": ["brand", "food", "lifestyle", "story", "marka", "jedzenie"],
     "platforms": ["reels", "feed", "story", "shorts"],
     "palette": {"bg": "#F2E4CF", "ink": "#3B2A20", "accent": "#D9534F", "accent2": "#4F8A6B"},
     "type": {"stack": "'Fraunces','Georgia',serif", "case": "mixed", "weight": 700, "tracking": "0", "min_size": "4.5% of frame height"},
     "motion": {"duration": "0.4-0.8 s", "ease": "steps(6) for stop-motion feel, power2.out for the rest", "stagger": "0.1 s", "camera": "layers slide at different speeds"},
     "transitions": ["slide-stack", "push", "tilt-flip", "mask-circle"],
     "layouts": ["full-bleed-caption", "icon-grid", "quote-card", "product-hero"],
     "assets": ["torn paper edges", "leaves and shapes", "stitches", "cardboard texture"],
     "pairs_with": ["sticker-pop", "neo-brutal", "pastel-soft", "cinematic-captions"],
     "composition": ["3-5 paper layers, each with a 0 6px 14px rgba(0,0,0,.18) shadow.", "Quantise time for the stop-motion feel: use ease steps(6) on position tweens.",
                     "Warm off-white, never pure white."],
     "avoid": ["Glossy gradients", "Perfect geometric edges everywhere"],
     "recipe": (".paper{background:#fff8ec;box-shadow:0 6px 14px rgba(0,0,0,.18);border-radius:6px}\n"
                "// stop-motion slide: tl.set('#p',{x:-300},0); tl.to('#p',{x:0,duration:.6,ease:'steps(6)'},t0);\n"
                "// shadow grows as a layer lifts: tl.to('#p',{boxShadow:'0 14px 28px rgba(0,0,0,.25)',y:-8,duration:.3},t1);")},
    {"id": "cinematic-captions", "name": "Kinowe napisy", "tagline": "Letterbox, powolny najazd, ziarno filmu i podpis w dolnej trzeciej.",
     "look": {"bg": "photo", "layout": "photo"}, "energy": 2,
     "tags": ["storytelling", "emotional", "documentary", "travel", "brand", "cinematic", "kinowy", "emocje", "podróże", "historia"],
     "goals": ["story", "testimonial", "recap", "brand", "historia", "opinia"],
     "platforms": ["feed", "web", "linkedin", "reels"],
     "palette": {"bg": "#0B0D10", "ink": "#F2F2F0", "accent": "#E8B04B", "accent2": "#5B8FA8"},
     "type": {"stack": "'Inter','Helvetica Neue',Arial,sans-serif", "case": "sentence", "weight": 500, "tracking": "0.01em", "min_size": "3.5% of frame height"},
     "motion": {"duration": "1.0-2.0 s", "ease": "sine.inOut, power1.inOut", "stagger": "0.2 s", "camera": "push-in 5-8% or lateral drift on every plate"},
     "transitions": ["blur-dissolve", "push", "mask-circle", "zoom-through"],
     "layouts": ["full-bleed-caption", "quote-card", "big-type", "cta-card"],
     "assets": ["photo or gradient plates", "film grain", "letterbox bars", "light leaks"],
     "pairs_with": ["dark-luxe", "swiss-minimal", "paper-cut", "gradient-mesh"],
     "composition": ["2.39:1 letterbox bars at 12% top and bottom keep captions in the safe zone.", "Captions in the lower third, max 2 lines.",
                     "Every plate moves; a still plate reads as a slideshow."],
     "avoid": ["Quick cuts", "Centred text on busy photos without a gradient scrim"],
     "recipe": (".bar{position:absolute;left:0;right:0;height:12%;background:#000}\n"
                ".scrim{background:linear-gradient(to top,rgba(0,0,0,.7),transparent 45%)}\n"
                "// plate drift: tl.set('#plate',{scale:1.0,x:0},0); tl.to('#plate',{scale:1.07,x:-30,duration:D,ease:'sine.inOut'},t0);")},
    {"id": "terminal-code", "name": "Terminal i kod", "tagline": "Mono, pisanie znak po znaku, poświata i panele z logami.",
     "look": {"bg": "dark", "layout": "ui"}, "energy": 3,
     "tags": ["dev", "tech", "hacker", "ai", "code", "developer", "kod", "programista", "sztuczna inteligencja"],
     "goals": ["product", "explainer", "launch", "demo", "dev", "produkt"],
     "platforms": ["reels", "linkedin", "web", "shorts"],
     "palette": {"bg": "#0A0F0D", "ink": "#D7FFE9", "accent": "#2EE59D", "accent2": "#FFB454"},
     "type": {"stack": "'JetBrains Mono','Fira Code',ui-monospace,monospace", "case": "mixed", "weight": 500, "tracking": "0", "min_size": "3.5% of frame height"},
     "motion": {"duration": "0.2-0.6 s", "ease": "steps(n) for typing, power2.out", "stagger": "0.03 s per character", "camera": "none"},
     "transitions": ["glitch-stutter", "flash-cut", "shutter", "push"],
     "layouts": ["device-mock", "list-reveal", "big-type", "number-counter"],
     "assets": ["window chrome", "cursor", "log lines", "badges"],
     "pairs_with": ["glass-ui", "kinetic-type", "retro-synth", "data-story"],
     "composition": ["Type by revealing characters: n = floor((t - t0) * 24); el.textContent = full.slice(0, n).", "Cursor blink derived from t: visible when floor(t * 2) % 2 == 0.",
                     "Monospace glyph coverage for Polish letters differs per font: run director_review."],
     "avoid": ["Real timers or setInterval for typing", "Tiny code (TEXT_TINY): crop to 3-5 lines"],
     "recipe": ("// typing, deterministic, inside seek(t): const n = Math.max(0, Math.min(full.length, Math.floor((t - t0) * 24))); el.textContent = full.slice(0, n) + (Math.floor(t * 2) % 2 === 0 ? '▌' : '');\n"
                ".term{background:#0A0F0D;border:1px solid #1d3a2f;border-radius:14px;color:#D7FFE9;font:500 3.6vw/1.4 'JetBrains Mono',ui-monospace,monospace}")},
    {"id": "pastel-soft", "name": "Miękki pastel", "tagline": "Zaokrąglone plamy, łagodne cienie i delikatne odbicia.",
     "look": {"bg": "light", "layout": "graphic"}, "energy": 2,
     "tags": ["wellness", "beauty", "kids", "friendly", "calm", "soft", "uroda", "dzieci", "łagodny", "zdrowie", "spokojny"],
     "goals": ["brand", "product", "lifestyle", "story", "marka", "produkt"],
     "platforms": ["feed", "reels", "story", "web"],
     "palette": {"bg": "#FDF3F0", "ink": "#4A3B47", "accent": "#F28CA8", "accent2": "#8FD3C8"},
     "type": {"stack": "'Nunito','Poppins',system-ui,sans-serif", "case": "sentence", "weight": 700, "tracking": "0", "min_size": "4% of frame height"},
     "motion": {"duration": "0.6-1.1 s", "ease": "back.out(1.2), sine.inOut", "stagger": "0.12 s", "camera": "gentle float: 6-10 px up and down on shapes"},
     "transitions": ["morph", "mask-circle", "blur-dissolve", "slide-stack"],
     "layouts": ["icon-grid", "big-type", "quote-card", "product-hero"],
     "assets": ["blobs", "rounded icons", "soft sparkles", "wavy lines"],
     "pairs_with": ["gradient-mesh", "sticker-pop", "paper-cut", "swiss-minimal"],
     "composition": ["Radius 28px or more on everything.", "Shadows tinted with the accent colour, never grey.",
                     "Float with sine.inOut over the whole beat, one period per beat so the loop closes."],
     "avoid": ["Sharp corners", "Black text on pastel at small sizes (check LOW_CONTRAST)"],
     "recipe": (".pill{background:#fff;border-radius:32px;box-shadow:0 14px 34px rgba(242,140,168,.28);padding:.7em 1.1em}\n"
                "// float, loops: tl.fromTo('#o',{y:0},{y:-10,duration:D/2,ease:'sine.inOut'},0); tl.to('#o',{y:0,duration:D/2,ease:'sine.inOut'},D/2);")},
]

_BY_ID = {s["id"]: s for s in STYLES}

_STOP = {"i", "w", "z", "na", "do", "to", "się", "jest", "że", "o", "dla", "oraz", "the", "a", "an", "and", "of", "for", "in", "is", "to", "with",
         "film", "video", "wideo", "reklama", "ad", "film", "chce", "chcę", "zrób", "make", "create"}


def tokens(*texts: str) -> list[str]:
    """Słowa kluczowe z opisu: małe litery, bez krótkich i bez słów pustych; kolejność pierwszego wystąpienia."""
    out: list[str] = []
    for text in texts:
        for w in re.findall(r"[\w'-]+", (text or "").lower()):
            if len(w) >= 3 and w not in _STOP and w not in out:
                out.append(w)
    return out


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def get(style_id: str) -> dict:
    if style_id not in _BY_ID:
        raise StudioError(f"nieznany styl '{style_id}'. Dostępne: {', '.join(_BY_ID)}")
    return _BY_ID[style_id]


def summary(s: dict) -> dict:
    return {k: s[k] for k in ("id", "name", "tagline", "energy", "tags", "goals", "platforms", "palette", "look", "pairs_with")}


def listing(platform: str | None = None, energy_min: int | None = None, query: str | None = None) -> list[dict]:
    rows = []
    q = _fold(query) if query else None
    for s in STYLES:
        if platform and platform not in s["platforms"]:
            continue
        if energy_min and s["energy"] < energy_min:
            continue
        if q and q not in _fold(" ".join([s["id"], s["name"], s["tagline"], *s["tags"], *s["goals"]])):
            continue
        rows.append(summary(s))
    return rows


def _score(s: dict, words: list[str], platform: str | None, prefer: list[str], pace: str | None) -> tuple[float, list[str]]:
    why: list[str] = []
    score = 0.0
    folded = [_fold(w) for w in words]
    for tag in s["tags"]:
        if _fold(tag) in folded:
            score += 3
            why.append(f"ton: {tag}")
    for goal in s["goals"]:
        if _fold(goal) in folded:
            score += 2
            why.append(f"cel: {goal}")
    if platform and platform in s["platforms"]:
        score += 1.5
        why.append(f"platforma: {platform}")
    if pace == "fast":
        score += (s["energy"] - 3) * 0.7
    elif pace == "calm":
        score += (3 - s["energy"]) * 0.7
    if s["id"] in prefer:
        score += 6
        why.append("wybrany przez użytkownika")
    return score, why


def recommend(goal: str = "", tone: str = "", platform: str | None = None, pace: str | None = None, prefer: list[str] | None = None,
              avoid: list[str] | None = None) -> dict:
    """Styl główny + dwa akcenty o innym układzie (żeby film zmieniał wygląd), z uzasadnieniem. Deterministycznie."""
    prefer, avoid = list(prefer or []), list(avoid or [])
    for sid in prefer + avoid:
        get(sid)
    words = tokens(goal, tone)
    pool = [s for s in STYLES if s["id"] not in avoid]
    if not pool:
        raise StudioError("wszystkie style są wykluczone (avoid)")
    scored = sorted(((*_score(s, words, platform, prefer, pace), i, s) for i, s in enumerate(pool)), key=lambda x: (-x[0], x[2]))
    main_score, main_why, _, main = scored[0]
    if main_score <= 0:
        main = next((s for s in pool if s["id"] == ("kinetic-type" if pace == "fast" or platform in ("reels", "tiktok", "shorts") else "swiss-minimal")), pool[0])
        main_why = ["domyślny wybór dla tej platformy i tempa (brak dopasowanych słów kluczowych)"]
    ranked = {s["id"]: sc for sc, _, _, s in scored}
    accents: list[dict] = []
    used_layouts = {main["look"]["layout"]}
    candidates = [_BY_ID[i] for i in main["pairs_with"] if i in _BY_ID and i not in avoid] + [s for _, _, _, s in scored]
    for want_diff in (True, False):                  # najpierw akcenty o innym układzie, potem dowolne, jeśli brakuje
        for s in sorted(candidates, key=lambda x: -ranked.get(x["id"], -9)):
            if len(accents) == 2:
                break
            if s["id"] == main["id"] or s in accents:
                continue
            if want_diff and s["look"]["layout"] in used_layouts:
                continue
            accents.append(s)
            used_layouts.add(s["look"]["layout"])
    return {"main": summary(main), "main_why": main_why, "accents": [summary(a) for a in accents],
            "accent_why": [f"{a['name']}: inny układ ({a['look']['layout']}) niż styl główny ({main['look']['layout']}), pasuje do {main['name']}" for a in accents]}


def font_note() -> str:
    return _FONT_NOTE


def style_text(s: dict) -> str:
    """Pełny opis stylu dla agenta (knowledge_get / style_get)."""
    pal = s["palette"]
    lines = [f"# Style: {s['name']} ({s['id']})", "", s["tagline"], "",
             f"- Energy {s['energy']}/5. Best for: {', '.join(s['goals'])}. Platforms: {', '.join(s['platforms'])}. Tone: {', '.join(s['tags'][:6])}.",
             f"- Default palette (brand palette wins when set): bg {pal['bg']}, ink {pal['ink']}, accent {pal['accent']}, accent 2 {pal['accent2']}.",
             f"- Type: {s['type']['stack']}, {s['type']['case']} case, weight {s['type']['weight']}, tracking {s['type']['tracking']}, min size {s['type']['min_size']}. {_FONT_NOTE}",
             f"- Motion: durations {s['motion']['duration']}, ease {s['motion']['ease']}, stagger {s['motion']['stagger']}, camera {s['motion']['camera']}.",
             f"- Transitions: {', '.join(s['transitions'])}. Layouts: {', '.join(s['layouts'])}. Assets: {', '.join(s['assets'])}.",
             f"- Pairs well with: {', '.join(s['pairs_with'])}.", "", "Composition:"]
    lines += [f"- {c}" for c in s["composition"]]
    lines += ["", "Avoid:"] + [f"- {a}" for a in s["avoid"]] + ["", "Recipe:", "```", s["recipe"], "```"]
    return "\n".join(lines) + "\n"


def library_text() -> str:
    rows = ["# Style library", "",
            "The brand (palette, font, tone) stays constant; the TREATMENT changes every 2-3 s (layout, background, motion language, transition). "
            "director_plan picks a main style and two accents with different layouts. Pick by goal and tone, not by taste.", ""]
    for s in STYLES:
        rows.append(f"- **{s['id']}** ({s['name']}, energy {s['energy']}): {s['tagline']} Tone: {', '.join(s['tags'][:5])}. Layouts: {', '.join(s['layouts'][:3])}.")
    rows += ["", "# Transitions (all deterministic in GSAP)", ""]
    rows += [f"- **{k}** ({t['name']}, sound {t['sound']}): {t['how']}" for k, t in TRANSITIONS.items()]
    rows += ["", "# Beat layouts", ""] + [f"- **{k}**: {v}" for k, v in LAYOUTS.items()]
    return "\n".join(rows) + "\n"
