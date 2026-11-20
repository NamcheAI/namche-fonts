# Namche Shadow – Rundungs-Prototyp (20.11.2026)

Prototyp, kein Produktionsweg. Er baut die Innenecken aus den Geist-Instanzen neu auf,
um die Regel zu zeigen. Die Konturen sind nicht kompatibel und taugen nicht für den VF.

Regel
- r90 = min(c × Stammstärke von I, Höchstwert); Höchstwert 70 (Versalien, Ziffern), 53 (Rest), c = 1.2
- Jede Innenecke bekommt dieselbe Tintenfläche A = r90² × (1 − π/4).
  Der Radius je Ecke wird so gelöst, dass die tatsächlich gefüllte Fläche A trifft
  (gilt auch für Kurvenanschlüsse und fast tangentiale Anschlüsse wie б, n, a).
- Stumpfe Ecken (> 90°) behalten r90. Platzgrenze: Tangentenlänge ≤ 0.45 × Länge bis zur nächsten Ecke.
- Füllung als lokale morphologische Schließung (konvexe Ecken bleiben scharf), je Ecke auf ihre Voronoi-Zelle begrenzt.

Skripte
- make_instances.py – statische Instanzen von Namche (main, codex/gf-latin-core) und Geist
- measure.py / evaluate.py – zugefügte Tinte je Ecke, jetzt gegen Vorschlag
- proto.py – die Regel (fill_corners)
- proof.py / render.py – Proofbilder
- sweep.py – Prüfung: 76 Zeichen × 7 Gewichte, keine Punze geschlossen, keine Tinte verloren

Abhängigkeiten: fonttools, skia-pathops, uharfbuzz, skia-python
