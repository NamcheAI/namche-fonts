# Shadow Sans equal-ink source migration

Issue [#125](https://github.com/NamcheAI/namche-fonts/issues/125) replaces the
previous upright filter stack and baked italic treatment with a source-built,
compatible inner-corner recipe. This document describes the inputs and checks;
it does not assert that a particular build has passed final release validation.

## Design inputs and provenance

`sources/equal-ink/clean-outlines.json` is the explicit, pinned unrounded design
input. The default y in each style includes Michael’s [option B](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7104336521). It joins the left arm to the descender across all masters. In Black the intersection falls on the cubic below the short straight edge. Accented forms inherit the new base.

Original upright contours come from the maintained upright Glyphs foreground.
Italic contours come exclusively from the immutable
`originals/geist/sources/Geist-Italic.glyphspackage` **foreground**. Maintained
packages continue to supply metrics, components, anchors, layout and attribution.
The clean fixture records the source commit and each glyph's origin; the
initializer refuses to replace an existing fixture.

An initial migration experiment selected 127 italic backgrounds because their
master topology was compatible. That was unsafe: all 127 matched upstream's
historical backgrounds, and 118 differed from the actual italic foreground.
For example, H's Regular background has upright stems at x=106–192 and
x=549–635; the italic foreground shifts its left edge from x=37 at y=0 to
x=187 at y=710. Compatibility alone does not establish the intended design.
No italic background is now used. The nine backgrounds that happened to equal
the italic foreground do not need a special exception.

A read-only history audit compared all 513 retained glyphs' master foregrounds
at `e0d5ce6^`, immediately before the original italic Shadow-rounding commit,
with the immutable italic foreground: all matched exactly. The original italic
Shadow change (`e0d5ce6`, #5) baked rounding and interpolation repairs. The later
A-counter repair (`9e8e959`, #83) corrected boolean topology; it is not a reason
to use the stale backgrounds. This audit establishes the pre-rounding outline
baseline, not designer approval of the new recipe. Counter and shaping checks
remain necessary after migration.

The clean resolver preserves the complete nonzero-filled compound outline,
including islands inside counters. The historical resolver only kept nesting
levels zero and one, which discarded the letters inside copyright/registered.
Independent raw-outline tests cover these symbols, `.notdef`, A and H in all
three masters of both styles; the new resolver preserves their filled area.
The compiled before/after proof also includes these symbols explicitly.

## Corner recipe

The reference radius is `min(1.6 × stem, cap)`, capped at 70 units for capitals
and figures and 53 for the remaining glyphs. Stem width comes from the clean I
masters. The reference right-angle added area is
`(1 − π/4) × radius²`. Acute joins solve for that added area using boolean-filled
geometry; right and obtuse joins retain the reference radius where feasible.
Circular fillets are solved on the actual adjacent Bézier curves.
Thin with a 32-unit stem therefore rounds at 51.2 units. Michael requested a
softer wave at the exterior lowercase bowl and shoulder joins. There the
minimum radius for a b d h m n p q r u rises linearly from 0.40 × r90
at Thin (100) to 0.60 × r90 at Regular (400) and stays there through Black.
The available flank bounds the radius. A
fillet may use up to 90% of a flank whose opposite end is free. Opposing
fillets each retain the 45% limit. In Thin the designer’s prototype also
limits the tangent distance along the shorter free run. It sums the segment
chords up to the next turn of at least 12°. For run length L and interior
angle θ, the radius limit is 0.90 × L × tan(θ/2). Any additional reduction
from this limit tapers linearly to zero at Regular. The default italic a spans an additional
short curve where the bowl meets the tail. Its bridge meets the outgoing curve
tangentially and runs left to right without doubling back. The upright a uses
21, 34.75 and 38.75 font-unit radii in Thin, Regular and Black. The Thin
anchor scales the earlier fit by 0.4/0.6. The Regular and Black anchors come
from Michael’s [bowl-to-tail reference](https://github.com/NamcheAI/namche-fonts/blob/664bbad5fc32de40b9e8307bbbb532865c9ae313/documentation/proofs/issues/issue-125/runde-2/r2_a.png).
Intermediate masters interpolate these radii.

After the clean option-B edit, the y arm meets a descender built from several
smooth segments. Rounding considers the whole flank so the outgoing tangent
can land on either curve or on the flat terminal. The italic uses r90. In
the upright, the radius follows r90 through Regular, then reaches 42 units
at Bold and 37 at Black. Those heavy upright anchors were fitted to the
designer’s preview. The radius floor is 0.60 × r90 in both slopes, including
Thin. [Michael’s round-three preview, right column](https://github.com/NamcheAI/namche-fonts/blob/5ef6ee4c998e542f7a38c1656dd9d51aa598bdef/documentation/proofs/issues/issue-125/runde-3/r3_y_vorschau.png?raw=true)

For the two heavy counters Michael identified, upright four and italic A,
the reference radius for acute inner joins decreases linearly from its normal
value at 500 to half at 900. Other counter treatments retain their reviewed
design. The [first](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7103017258)
and [second](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7103995878)
reviews record the glyph and rendering decisions.

Component rotation, translation and scale are normalized to the Glyphs package
serializer precision before interpolation. In particular, the historical bullet
scales 1.7494/1.5899 become 1.749/1.590 before deriving intermediate weights;
otherwise a first build and a build from its saved sources disagree. Paths,
anchors and component metadata are not changed by this normalization. The
bullet adjustment moves the sampled intermediate component geometry by at most
0.229 units before integer conversion; a few compiled points move by one unit.

Clean intermediate masters are derived at 50-weight intervals before rounding,
through ufo2ft Instantiator, including the original sparse f master at 801. The
public family still has the same nine named weights. The italic B waist is
identified on its resolved filled boundary because the authored overlapping
contours do not expose that join. Its rounded outer contour has nine compatible
segments in every master; the tiny connector in heavier masters is replaced by
the solved arc. Both counter contours remain present.
Its actual added ink is measured against the full glyph.

The statics and variable fonts use the same solved arcs. The
previous review build included a second complete copy of every rounded glyph
in the variable font. FreeType’s grayscale rendering exposed that duplication
at small sizes. Four base glyphs need localized protection against a curved
edge moving inward between masters. Both slopes of @, upright 3 and its
superscript retain the clean boundary with local fillets. Both slopes of 8
retain strips along the affected curves. Derived components inherit their
base’s treatment. Static exports use the continuous solved contours alone.
Adding the interpolation guards to the statics produced subunit backtracking
segments after quadratic conversion in 8 and 3. The build therefore projects
the static boundaries before compilation.

A fillet member adding less than one square unit is left inactive and reported;
meaningful members at other weights remain active through compatible slots.
Inactive slots subdivide a short incoming tail and outgoing head exactly,
within the same flank limit, rather than collapsing into a single point or
placing both slots on one side of the cusp. Dense compiled probes caught tiny
loops from collapsed slots after delta rounding, and enclosed white slivers
from one-sided slots. The symmetric subdivision preserves the inactive
master's filled geometry. Regression cases cover italic a between masters,
italic sterling, upright superscript zero, and the bold italic ordinal static.

Both static and variable compilation explicitly select the Python cu2qu
implementation shipped with pinned fontTools 4.60.1. Its compiled extension can
differ by one floating-point ULP between macOS ARM and Linux; rounding a control
point near a half unit then changes an integer outline by one unit. The scoped
`fontmake_deterministic.py` entry point avoids that platform-dependent conversion
without modifying the installed environment. It retains the same 0.1-unit
conversion bound. The build logs the compiler version and Python-source hash.
The conversion correction moves integer-rounded reviewed points by at most one
unit. Across all glyphs at the 16 reviewed VF instances, the largest raw
fractional movement is 1.097258 units: upright `three`/`three.tf` at weight 550.
Existing integer-rounded gvar deltas combine with quantized tuple supports, so
their weighted changes can exceed the single-point integer conversion change.
Tuple supports, point/contour topology and advances remain unchanged; the
compiled geometry allowance stays at two units and remains independently tested.

Compilation disables the default lossy IUP optimization of variation deltas.
Finalization applies zero-tolerance IUP compression and re-expands every tuple
to verify exact delta equality; it keeps the full tuple if that check fails.
Thus file compression cannot introduce the half-unit point movements seen in
the discarded prototype. Cubic-to-quadratic conversion uses a 0.1-unit bound;
integer coordinates and variation-delta rounding still require compiled tests.

Flank limits use the original arc length. Space
limits or curved offset-branch limits can prevent reaching the requested radius
or area. Inspect `corner-report.json` for capped, skipped and inactive joins;
do not describe all joins as mathematically equal-area. In particular, obtuse
joins keep the reference radius and generally add less than the right-angle
target. A failed local solution is skipped consistently across all masters.

Local candidate ink loss is rejected; the completed master is also checked for
aggregate loss, excessive added area and counter-count changes. The fast source
checks use float32 PathOps. Their local added-area measurement is bounded by
an independent analytic Bézier patch area; impossible results are remeasured
with GEOS before making radius or inactivity decisions. Suspicious results are independently checked with
float64 GEOS, using adaptive curve flattening within 0.001 units and a combined
0.002-unit spatial envelope. Reports retain both raw and residual lost area.
Compiled-font checks separately cover quantization and interpolation. Neither
finite sampling nor a successful regression gate is artistic approval or
Google Fonts acceptance.

## Metadata finalization

`sources/equal-ink/release-metadata/` contains one-time TTX/JSON captures of the
public identity and layout contract for all 38 Sans OTF/TTF/VF inputs. They do
not contain old outline, variation-delta, metric or hint-program tables.
`finalize_equal_ink.py` reads fresh compiled geometry and these source fixtures;
normal builds do not bootstrap from previous release binaries.

The finalizer preserves public naming, credits, cmap, menu identity and layout.
It checks Latin Core encoding, required glyph names, units per em, variation
axis ranges/default and advances. Fully decompiled layout is remapped by glyph
name into the new compiled glyph order. New geometry, horizontal metrics and
variation deltas stay compiled. Old point-dependent hinting is stripped; these
outputs are unhinted, so small-size rendering remains part of visual review.
Only an explicit normalization of unencoded static ligatures by at most one
unit is permitted; their captured advances are restored and reported. Encoded
or variable advance changes, and larger static differences, are rejected. WOFF2
files are derived from finalized TTFs.

## Build and verification

Use the pinned repository environment. The ordinary migration build consumes
existing clean inputs and existing metadata fixtures:

```sh
venv/bin/python scripts/build_sans_equal_ink.py \
  --output /tmp/namche-equal-ink --finalize
venv/bin/python scripts/build_sans_equal_ink.py --clean \
  --output /tmp/namche-equal-ink-clean
venv/bin/python scripts/check_equal_ink.py \
  --baseline-dir /tmp/namche-equal-ink-clean/fonts \
  --candidate-dir /tmp/namche-equal-ink/finalized \
  --include-unencoded-variable --include-otf-statics --max-outline-loss-distance 2 \
  --output /tmp/namche-equal-ink-measurements.json
venv/bin/python -m unittest discover -s tests -p 'test_equal_ink*.py'
venv/bin/python -m unittest discover -s tests -p 'test_finalize_equal_ink.py'
```

Use fresh output directories. `make build-sans` builds and promotes all 58
binaries and both design/production source representations together, restoring
the prior trees if installation fails. `make check-sans-equal-ink` rebuilds and
compares the complete binary inventory and both design packages with the
committed versions.

The clean build provides matching unrounded statics and VFs; the validator refuses a missing static baseline rather than comparing integer
static advances with fractional variable instances. Its
default sweep checks both VFs at 100, 150, …, 900 and every named-weight static.
CI also checks every retained unencoded VF glyph at 33 weights and all named
OTF statics against matching clean OTF baselines. The validator
compares coverage through cmap, directional lost ink, counter count,
matched counter overlap and advances. A configured tolerance or sampling grid
is not proof about every weight or size.

Before release, also check deterministic rebuilds, exact Latin Core coverage,
source-copy policy, metadata, language shaping, npm artifacts and Google Fonts
candidate packaging. Inspect representative straight and diagonal joins,
figures and counters across upright/italic weights. The review site must link
the exact final font commit and SHA-256 manifest. Keep earlier feedback labeled
with its original snapshot; pending visual questions are not automatically
resolved by a successful build.

## Current review proofs

The [round-three sheets](proofs/issues/issue-125/round-3/README.md) show the
arm-to-descender join in all nine weights, the ten revised Thin lowercase joins
and native-size comparisons between each static and variable Regular at 11–16 px.

## Second review snapshot (7b47095)

The [review sheets and rendering measurements](proofs/issues/issue-125/round-2/README.md)
compare the compiled revisions with the November 22 build at `fc9062d`.
FreeType is sampled at every integer size from 11 to 16 px in both slopes and
all nine weights. The sheets show the small text at its native resolution.

The upright variable WOFF2 is 254,736 bytes (previously 301,608). Italic is
260,396 bytes (previously 305,740). Fontspector 1.9.0 on the 20 production
TTFs reports 264 warnings and the same seven existing failures. Both variable
contour-count warnings cleared. The file-size warnings remain. The projected
statics have no newly flagged glyphs in the outline checks.

## First review snapshot (fc9062d)

Fontspector 1.9.0 ran the Google Fonts profile on all 18 static TTFs and both
production VFs. Against the preceding Latin Core review snapshot, WARN results
change from 306 to 266 and FAIL results remain 7. Those production failures are
the existing long italic instance-name findings and repository-folder layout
finding. The separately renamed Google Fonts candidate has its own QA gate.

No static glyph is newly flagged by the outline checks; 51 previous glyph-warning
entries disappear. Seven existing entries retain one-unit slants or collinear
steps with changed coordinates. The variable fonts introduce `contour_count`
and `file_size` warnings for both styles. Their existing
`overlapping_path_segments` warnings also list 319 additional upright and 311
additional italic glyphs, all with the retained clean guard contours. These are
new representation and size costs of this implementation, not upstream tooling
bugs or waived Google Fonts requirements. Filled-counter and ink checks remain
necessary despite setting the overlap flags.

The webfont cost is measurable (bytes):

| Style | Previous WOFF2 | Review WOFF2 | Review TTF |
| --- | ---: | ---: | ---: |
| Upright | 196,776 | 301,608 | 1,461,680 |
| Italic | 222,908 | 305,740 | 1,515,800 |

The preceding figures describe the November 22 review snapshot.
