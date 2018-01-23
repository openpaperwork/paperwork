REPO ?= repo
APP = work.openpaper.Paperwork
ALL_TARGETS = $(patsubst %.json,%,$(wildcard *.json))
ALL_BRANCHES = master develop

all: upd_branches

# clean: remove all intermediate files
clean:
	rm -rf $(patsubst %,%.app,$(ALL_TARGETS)) $(patsubst %,%.flatpak,$(ALL_TARGETS))

# dist-clean: remove *everything* that is not stored in Git
dist-clean: clean
	rm -rf $(REPO) .flatpak-builder

# Build a specific branch / tag
# Will export to the Flatpak repository $(REPO)
%.app: %.json
	@echo flatpak-builder $< --\> $@ \($(REPO) ${EXPORT_ARGS} ${ARCH_ARGS}\)
	flatpak-builder --repo=$(REPO) -s "Build of Paperwork $(@:%.app=%) `date`" ${EXPORT_ARGS} ${ARCH_ARGS} $@ $<

# Build all branches and tags and update the Flatpak repository $(REPO)
mk_all: $(patsubst %,%.app,$(ALL_TARGETS))
	@echo flatpak build-update-repo $(REPO) \($(REPO) ${EXPORT_ARGS} ${ARCH_ARGS}\)
	flatpak build-update-repo --generate-static-deltas ${EXPORT_ARGS} $(REPO)

# Build only the branches and update the Flatpak repository $(REPO)
upd_branches: $(patsubst %,%.app,$(ALL_BRANCHES))
	@echo flatpak build-update-repo $(REPO) \($(REPO) ${EXPORT_ARGS} ${ARCH_ARGS}\)
	flatpak build-update-repo --generate-static-deltas ${EXPORT_ARGS} $(REPO)

# Build a Flatpak bundle
%.flatpak: mk_all
	@echo flatpak build-bundle $(REPO) --\> $@ \(${EXPORT_ARGS} ${ARCH_ARGS} branch: $(@:%.flatpak=%)\)
	flatpak -v build-bundle ${ARCH_ARGS} $(REPO) $@ $(APP) $(@:%.flatpak=%)

# Build all Flatpak bundles
bundles: $(patsubst %,%.flatpak,$(ALL_TARGETS))

.PHONY: all clean dist-clean mkrepo bundles
