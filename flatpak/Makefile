REPO ?= repo
APP = work.openpaper.Paperwork
APPS = $(patsubst %.json,%,$(wildcard *.json))

all: mkrepo

clean:
	rm -rf $(patsubst %,%.app,$(APPS)) $(patsubst %,%.flatpak,$(APPS))

dist-clean: clean
	rm -rf $(REPO) .flatpak-builder

%.app: %.json
	@echo flatpak-builder $< --\> $@ \($(REPO) ${EXPORT_ARGS} ${ARCH_ARGS}\)
	flatpak-builder --repo=$(REPO) -s "Build of Paperwork $(@:%.app=%) `date`" ${EXPORT_ARGS} ${ARCH_ARGS} $@ $<

mkrepo: $(patsubst %,%.app,$(APPS))
	@echo flatpak build-update-repo $(REPO) \($(REPO) ${EXPORT_ARGS} ${ARCH_ARGS}\)
	flatpak build-update-repo --generate-static-deltas ${EXPORT_ARGS} $(REPO)

%.flatpak: mkrepo
	@echo flatpak build-bundle $(REPO) --\> $@ \(${EXPORT_ARGS} ${ARCH_ARGS} branch: $(@:%.flatpak=%)\)
	flatpak -v build-bundle ${ARCH_ARGS} $(REPO) $@ $(APP) $(@:%.flatpak=%)

bundles: $(patsubst %,%.flatpak,$(APPS))

.PHONY: all clean dist-clean mkrepo bundles
