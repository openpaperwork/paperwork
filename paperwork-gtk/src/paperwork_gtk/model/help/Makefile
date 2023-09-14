all: data

out/paperwork_going_up.png: data/paperwork_going_up.svg
	convert $< $@

screenshots:
	[ -f $(CURDIR)/${OUT_INTRO_PDF} ] || LANG=C WAYLAND_DISPLAY= xvfb-run sh ./screenshot.sh

l10n_extract:
	cd $(CURDIR) && po4a -M UTF-8 -k 0 po4a.conf

l10n_compile: l10n_extract

out/translated_%.tex: l10n_compile

out/translated_%.pdf: out/translated_%.tex l10n_compile screenshots out/paperwork_going_up.png
	# run pdflatex twice because of the TOC
	pdflatex --output-directory=out ../$<
	pdflatex --output-directory=out ../$<

out/%.pdf: data/%.tex l10n_compile screenshots out/paperwork_going_up.png
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

.PHONY: all clean screenshots data l10n_extract l10n_compile
