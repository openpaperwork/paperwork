REPO = repo
APP = work.openpaper.Paperwork
APPS = $(patsubst %.json,%,$(wildcard *.json))

all: repo bundles

clean:
	rm -rf $(patsubst %,%.app,$(APPS)) $(patsubst %,%.flatpak,$(APPS))

dist-clean: clean
	rm -rf repo .flatpak-builder *.traineddata

%.traineddata:
	wget -c https://github.com/tesseract-ocr/tessdata/raw/3.04.00/$@

traineddata: eng.traineddata osd.traineddata \
	deu.traineddata \
	fra.traineddata

%.app: %.json traineddata
	@echo flatpak-builder $< --\> $@ \(${EXPORT_ARGS}\)
	flatpak-builder ${EXPORT_ARGS} $@ $<
	@echo configuring Tesseract traineddata
	mkdir -p $@/files/share/tessdata
	cp deu.traineddata $@/files/share/locale/de
	ln -s $@/files/share/locale/de/deu.traineddata $@/files/share/tessdata
	cp fra.traineddata $@/files/share/locale/fr
	ln -s $@/files/share/locale/fr/fra.traineddata $@/files/share/tessdata
	cp eng.traineddata $@/files/share/tessdata
	cp osd.traineddata $@/files/share/tessdata
	@echo exporting to repo
	flatpak build-export -s "Build of Paperwork $(@:%.app=%) `date`" ${EXPORT_ARG} $(REPO) $@ $(@:%.app=%)

repo: $(patsubst %,%.app,$(APPS))
	@echo flatpak build-update-repo $(REPO) \(${EXPORT_ARGS}\)
	flatpak build-update-repo ${EXPORT_ARGS} $(REPO)

%.flatpak: repo
	@echo flatpak build-bundle $(REPO) --\> $@ \(branch: $(@:%.flatpak=%)\)
	flatpak -v build-bundle $(REPO) $@ $(APP) $(@:%.flatpak=%)

bundles: $(patsubst %,%.flatpak,$(APPS))

.PHONY: all
