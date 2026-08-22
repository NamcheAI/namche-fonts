SOURCES=$(shell python3 scripts/read-config.py --sources )
PIXEL_SOURCES=$(shell find sources/NamcheShadowPixel.glyphspackage -type f)
FAMILY=$(shell python3 scripts/read-config.py --family )
PYTHON?=venv/bin/python
SHAPING_REPORTS=out/fontspector/NamcheShadowSansVF-fontspector-report.json out/fontspector/NamcheShadowSans-fontspector-report.json out/fontspector/NamcheShadowMonoVF-fontspector-report.json out/fontspector/NamcheShadowMono-fontspector-report.json
SHAPING_FONT_DIRS=fonts/NamcheShadowSans/variable fonts/NamcheShadowSans/ttf fonts/NamcheShadowMono/variable fonts/NamcheShadowMono/ttf

help:
	@echo "###"
	@echo "# Build targets for $(FAMILY)"
	@echo "###"
	@echo
	@echo "  make build:  Builds the fonts and places them in the fonts/ directory"
	@echo "  make finalize-sans-statics GLYPHS_SANS_EXPORT=/path: merge native Glyphs OTF/TTF exports into the release files"
	@echo "  make build-sans-variable GLYPHS_SANS_EXPORT=/path: build the rounded upright Sans VF from compatible Glyphs OTF exports"
	@echo "  make refresh-sans-shaping COMPILED_SANS_BUILD=/path: refresh layout without changing approved outlines"
	@echo "  make test:   Tests the fonts with fontspector"
	@echo "  make proof:  Creates HTML proof documents in the proof/ directory"
	@echo "  make images: Regenerates the README banners in .docs/img/"
	@echo

build: build.stamp

venv: venv/touchfile

venv-pixel: venv-pixel/touchfile

customize: venv
	. venv/bin/activate; python3 scripts/customize.py

build.stamp: venv venv-pixel sources/config-NamcheShadowSans.yaml \
	sources/compile-NamcheShadowPixelStatics.yaml \
	$(PIXEL_SOURCES) $(SOURCES)
	$(MAKE) check-source-copies
	rm -rf fonts namche-shadow-font namche-shadow-font.zip
	$(MAKE) build-mono
	$(MAKE) build-pixel
	# Namche Shadow Sans statics are native Glyphs exports: gftools does not run
	# the seven RoundCorner instance filters. A Linux build restores and validates
	# the committed approved release instead of replacing its outlines.
	@echo "Using committed native Glyphs exports for Namche Shadow Sans"
	# Sans statics and Pixel statics/webfonts are native Glyphs exports committed
	# to the repository. Restore them after the clean build so release and npm
	# artifacts use the approved outlines.
	git checkout -- fonts/NamcheShadowSans/otf fonts/NamcheShadowSans/ttf fonts/NamcheShadowSans/webfonts fonts/NamcheShadowSans/variable
	. venv/bin/activate; python3 scripts/rename_font_metadata.py --check fonts
	. venv/bin/activate; python3 scripts/check_sans_variable.py
	$(MAKE) copy-npm-fonts
	$(MAKE) create-release-zip
	touch build.stamp

# Family-scoped targets let pull-request CI compile only the source that changed.
# They intentionally stop before assembling cross-family npm/release artifacts.
build-mono: venv sources/config-NamcheShadowMono.yaml \
	sources/NamcheShadowMono.glyphspackage \
	sources/NamcheShadowMono-Italic.glyphspackage
	rm -rf fonts/NamcheShadowMono
	. venv/bin/activate; gftools builder sources/config-NamcheShadowMono.yaml
	. venv/bin/activate; python3 scripts/rename_font_metadata.py fonts/NamcheShadowMono

build-pixel: venv venv-pixel sources/config-NamcheShadowPixel.yaml \
	sources/compile-NamcheShadowPixelStatics.yaml $(PIXEL_SOURCES)
	# Pixel's virtual-master support needs the pinned dev gftools build.
	rm -rf fonts/NamcheShadowPixel out/pixel-compiled
	. venv-pixel/bin/activate; gftools builder sources/config-NamcheShadowPixel.yaml
	# Compile reviewed source additions and layout separately. The finalizer
	# merges only those additions and GDEF/GSUB/GPOS into native statics.
	. venv-pixel/bin/activate; gftools builder sources/compile-NamcheShadowPixelStatics.yaml
	git checkout -- fonts/NamcheShadowPixel/otf fonts/NamcheShadowPixel/ttf fonts/NamcheShadowPixel/webfonts
	. venv/bin/activate; python3 scripts/finalize_pixel_statics.py fonts/NamcheShadowPixel --compiled out/pixel-compiled
	. venv/bin/activate; python3 scripts/rename_font_metadata.py fonts/NamcheShadowPixel

check-source-copies:
	# Mono remains outline-identical; Pixel permits reviewed source additions.
	# The checker also permits only reviewed Mono anchor metadata.
	python3 scripts/check_source_copies.py

check-sans-variable: venv
	. venv/bin/activate; python3 scripts/check_sans_variable.py

finalize-sans-statics: venv
	test -n "$(GLYPHS_SANS_EXPORT)" || (echo "Set GLYPHS_SANS_EXPORT to a directory containing otf/ and ttf/." && exit 1)
	. venv/bin/activate; python3 scripts/finalize_glyphs_statics.py --gftools fonts/NamcheShadowSans --glyphs "$(GLYPHS_SANS_EXPORT)" --output fonts/NamcheShadowSans
	. venv/bin/activate; python3 scripts/rename_font_metadata.py --check fonts/NamcheShadowSans
	$(MAKE) copy-npm-fonts

build-sans-variable: venv
	test -n "$(GLYPHS_SANS_EXPORT)" || (echo "Set GLYPHS_SANS_EXPORT to a directory containing compatible otf/ exports." && exit 1)
	. venv/bin/activate; python3 scripts/build_sans_variable.py --glyphs-export "$(GLYPHS_SANS_EXPORT)" --statics fonts/NamcheShadowSans --output fonts/NamcheShadowSans
	. venv/bin/activate; python3 scripts/rename_font_metadata.py --check fonts/NamcheShadowSans
	$(MAKE) copy-npm-fonts

refresh-sans-shaping: venv
	test -n "$(COMPILED_SANS_BUILD)" || (echo "Set COMPILED_SANS_BUILD to a fresh gftools Sans output." && exit 1)
	. venv/bin/activate; python3 scripts/refresh_shaping_tables.py --compiled "$(COMPILED_SANS_BUILD)" --output fonts/NamcheShadowSans
	. venv/bin/activate; python3 scripts/rename_font_metadata.py fonts/NamcheShadowSans
	. venv/bin/activate; python3 scripts/rename_font_metadata.py --check fonts/NamcheShadowSans
	$(MAKE) copy-npm-fonts

copy-npm-fonts:
	# Clear any pre-existing build artifacts
	rm -rf packages/next/dist/fonts
	# Copy over the relevant font files
	mkdir -p packages/next/dist/fonts/namche-shadow-sans packages/next/dist/fonts/namche-shadow-mono packages/next/dist/fonts/namche-shadow-pixel
	cp fonts/NamcheShadowSans/ttf/*.ttf packages/next/dist/fonts/namche-shadow-sans/
	cp fonts/NamcheShadowSans/webfonts/*.woff2 packages/next/dist/fonts/namche-shadow-sans/
	cp fonts/NamcheShadowSans/variable/*.ttf packages/next/dist/fonts/namche-shadow-sans/
	cp fonts/NamcheShadowMono/ttf/*.ttf packages/next/dist/fonts/namche-shadow-mono/
	cp fonts/NamcheShadowMono/webfonts/*.woff2 packages/next/dist/fonts/namche-shadow-mono/
	cp fonts/NamcheShadowMono/variable/*.ttf packages/next/dist/fonts/namche-shadow-mono/
	cp fonts/NamcheShadowPixel/webfonts/*.woff2 packages/next/dist/fonts/namche-shadow-pixel/
	# Apparently there is a naming mismatch between the font files for npm distribution and the actual font files,
	# so we need to rename them to the correct names.
	cd packages/next/dist/fonts/namche-shadow-sans && \
		mv NamcheShadowSans-ExtraLight.ttf NamcheShadowSans-UltraLight.ttf && \
		mv NamcheShadowSans-ExtraLight.woff2 NamcheShadowSans-UltraLight.woff2 && \
		mv NamcheShadowSans-ExtraLightItalic.ttf NamcheShadowSans-UltraLightItalic.ttf && \
		mv NamcheShadowSans-ExtraLightItalic.woff2 NamcheShadowSans-UltraLightItalic.woff2 && \
		mv NamcheShadowSans-Black.ttf NamcheShadowSans-UltraBlack.ttf && \
		mv NamcheShadowSans-Black.woff2 NamcheShadowSans-UltraBlack.woff2 && \
		mv NamcheShadowSans-ExtraBold.ttf NamcheShadowSans-Black.ttf && \
		mv NamcheShadowSans-ExtraBold.woff2 NamcheShadowSans-Black.woff2 && \
		mv NamcheShadowSans-BlackItalic.ttf NamcheShadowSans-UltraBlackItalic.ttf && \
		mv NamcheShadowSans-BlackItalic.woff2 NamcheShadowSans-UltraBlackItalic.woff2 && \
		mv NamcheShadowSans-ExtraBoldItalic.ttf NamcheShadowSans-BlackItalic.ttf && \
		mv NamcheShadowSans-ExtraBoldItalic.woff2 NamcheShadowSans-BlackItalic.woff2 && \
		mv 'NamcheShadowSans[wght].ttf' NamcheShadowSans-Variable.ttf && \
		mv 'NamcheShadowSans[wght].woff2' NamcheShadowSans-Variable.woff2
	cd packages/next/dist/fonts/namche-shadow-mono && \
		mv NamcheShadowMono-ExtraLight.ttf NamcheShadowMono-UltraLight.ttf && \
		mv NamcheShadowMono-ExtraLight.woff2 NamcheShadowMono-UltraLight.woff2 && \
		mv NamcheShadowMono-ExtraBold.ttf NamcheShadowMono-UltraBlack.ttf && \
		mv NamcheShadowMono-ExtraBold.woff2 NamcheShadowMono-UltraBlack.woff2 && \
		mv 'NamcheShadowMono[wght].ttf' NamcheShadowMono-Variable.ttf && \
		mv 'NamcheShadowMono[wght].woff2' NamcheShadowMono-Variable.woff2
	$(PYTHON) scripts/rename_font_metadata.py --check packages/next/dist/fonts
	node scripts/build-webfont-css.mjs

create-release-zip:
	mkdir -p namche-shadow-font/fonts
	cp -r fonts/* namche-shadow-font/fonts/
	node scripts/build-webfont-css.mjs --cdn --tag v$$(node -p "require('./packages/next/package.json').version") --out namche-shadow-font
	node scripts/check-release-webfont-css.mjs --tag v$$(node -p "require('./packages/next/package.json').version") --styles namche-shadow-font --fonts namche-shadow-font/fonts
	cp documentation/DESCRIPTION.en_us.html namche-shadow-font/ || true
	cp documentation/article/ARTICLE.en_us.html namche-shadow-font/ || true
	cp OFL.txt namche-shadow-font/
	zip -r namche-shadow-font.zip namche-shadow-font
	rm -rf namche-shadow-font

venv/touchfile: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	touch venv/touchfile

# Namche Shadow Pixel's virtual-master support only exists in an unreleased gftools dev
# build (Simon Cozens' fix). Pin the exact commit for reproducibility; revisit
# once it ships in an official gftools release and we can fold it into venv.
GFTOOLS_PIXEL_REF = 47ec3706b

venv-pixel/touchfile: Makefile
	test -d venv-pixel || python3 -m venv venv-pixel
	. venv-pixel/bin/activate; pip install "gftools @ git+https://github.com/googlefonts/gftools@$(GFTOOLS_PIXEL_REF)"
	touch venv-pixel/touchfile

test: build.stamp fontspector-release check-language-shaping check-pixel-separators \
	check-pixel-ligature-carets check-pixel-rupee check-pixel-shaping check-mono-hmetrics

test-scripts: venv
	. venv/bin/activate; python3 -m unittest discover -s tests -p 'test_*.py'

fontspector: build.stamp fontspector-release

fontspector-release:
	rm -rf out/fontspector out/badges
	$(MAKE) fontspector-sans fontspector-mono fontspector-pixel

fontspector-prepare:
	which fontspector || (echo "fontspector not found. Please install it with 'cargo install fontspector'." && exit 1)
	mkdir -p out/fontspector out/badges

fontspector-sans: fontspector-prepare
	TOCHECK=$$(find fonts/NamcheShadowSans/variable -type f 2>/dev/null); mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --json out/fontspector/NamcheShadowSansVF-fontspector-report.json --badges out/badges $$TOCHECK  || echo '::warning file=sources/config-NamcheShadowSans.yaml,title=fontspector failures::The Sans variable-font QA check reported errors. Please check the generated report.'
	TOCHECK=$$(find fonts/NamcheShadowSans/ttf -type f 2>/dev/null); mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --json out/fontspector/NamcheShadowSans-fontspector-report.json --badges out/badges $$TOCHECK  || echo '::warning file=sources/config-NamcheShadowSans.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'

fontspector-mono: fontspector-prepare
	TOCHECK=$$(find fonts/NamcheShadowMono/variable -type f 2>/dev/null); mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --json out/fontspector/NamcheShadowMonoVF-fontspector-report.json --badges out/badges $$TOCHECK  || echo '::warning file=sources/config-NamcheShadowMono.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'
	TOCHECK=$$(find fonts/NamcheShadowMono/ttf -type f 2>/dev/null); mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --json out/fontspector/NamcheShadowMono-fontspector-report.json --badges out/badges $$TOCHECK  || echo '::warning file=sources/config-NamcheShadowMono.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'

fontspector-pixel: fontspector-prepare
	TOCHECK=$$(find fonts/NamcheShadowPixel/ttf -type f 2>/dev/null); mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --json out/fontspector/NamcheShadowPixel-fontspector-report.json --badges out/badges $$TOCHECK  || echo '::warning file=sources/config-NamcheShadowPixel.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'

check-language-shaping:
	python3 scripts/check_language_shaping.py $(foreach dir,$(SHAPING_FONT_DIRS),--font-dir $(dir)) $(SHAPING_REPORTS)
	$(PYTHON) scripts/check_pixel_shaping.py --fontspector-report out/fontspector/NamcheShadowPixel-fontspector-report.json

check-language-shaping-sans:
	python3 scripts/check_language_shaping.py \
		--font-dir fonts/NamcheShadowSans/variable \
		--font-dir fonts/NamcheShadowSans/ttf \
		out/fontspector/NamcheShadowSansVF-fontspector-report.json \
		out/fontspector/NamcheShadowSans-fontspector-report.json

check-language-shaping-mono:
	python3 scripts/check_language_shaping.py \
		--font-dir fonts/NamcheShadowMono/variable \
		--font-dir fonts/NamcheShadowMono/ttf \
		out/fontspector/NamcheShadowMonoVF-fontspector-report.json \
		out/fontspector/NamcheShadowMono-fontspector-report.json

check-pixel-separators: venv
	. venv/bin/activate; python3 scripts/check_pixel_separators.py

check-pixel-ligature-carets: venv
	. venv/bin/activate; python3 scripts/check_pixel_ligature_carets.py

check-pixel-rupee: venv
	. venv/bin/activate; python3 scripts/check_pixel_rupee.py

check-pixel-shaping: venv
	. venv/bin/activate; python3 scripts/check_pixel_shaping.py

check-mono-hmetrics: venv
	. venv/bin/activate; python3 scripts/check_mono_hmetrics.py

proof: venv build.stamp
	TOCHECK=$$(find fonts/NamcheShadowSans/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/NamcheShadowSans/ttf -type f 2>/dev/null); fi ; . venv/bin/activate; mkdir -p out/ out/proof; diffenator2 proof $$TOCHECK -o out/proof

images: venv build.stamp
	. venv/bin/activate; python3 scripts/render_banners.py

%.png: %.py build.stamp
	. venv/bin/activate; python3 $< --output $@

clean:
	rm -rf venv venv-pixel
	find . -name "*.pyc" -delete

update-project-template:
	npx update-template https://github.com/googlefonts/googlefonts-project-template/

update: venv
	venv/bin/pip install --upgrade pip-tools
	# See https://pip-tools.readthedocs.io/en/latest/#a-note-on-resolvers for
	# the `--resolver` flag below.
	venv/bin/pip-compile --upgrade --verbose --resolver=backtracking requirements.in
	venv/bin/pip-sync requirements.txt

	git commit -m "Update requirements" requirements.txt
	git push
