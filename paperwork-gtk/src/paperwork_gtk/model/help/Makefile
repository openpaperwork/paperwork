all: data

out/paperwork_going_up.png: data/paperwork_going_up.svg
	convert $< $@

out/main_window.png:
	# screnshots
	[ -f $(CURDIR)/${OUT_INTRO_PDF} ] || LANG=C WAYLAND_DISPLAY= xvfb-run -a -e /dev/stderr sh ./screenshot.sh

l10n_extract:
	# will generate out/translated_*_$lang.tex files
	cd $(CURDIR) && po4a -M UTF-8 -k 0 po4a.conf

l10n_compile: l10n_extract

out/%.tex:
	rm -f out/*.tex
	cp data/intro.tex out/intro.tex
	cp data/usage.tex out/usage.tex
	$(MAKE) l10n_compile

out/%.pdf: out/%.tex out/main_window.png out/paperwork_going_up.png
	# run pdflatex twice because of the TOC
	pdflatex --output-directory=out ../$<
	pdflatex --output-directory=out ../$<

clean:
	rm -f $(CURDIR)/out/*.png
	rm -f $(CURDIR)/out/*.pdf
	rm -f $(CURDIR)/out/*.toc
	rm -f $(CURDIR)/data/*.aux
	rm -f $(CURDIR)/data/*.log

data:
	rm -f $(CURDIR)/out/*.pdf
	rm -f $(CURDIR)/out/*.toc
	$(MAKE) out/intro.pdf
	$(MAKE) out/translated_intro_de.pdf
	$(MAKE) out/translated_intro_fr.pdf
	$(MAKE) out/usage.pdf
	$(MAKE) out/translated_usage_de.pdf
	$(MAKE) out/translated_usage_fr.pdf

.PHONY: all clean data l10n_extract l10n_compile
