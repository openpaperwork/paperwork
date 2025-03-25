REPO ?= $(abspath paperwork_repo)
APP = work.openpaper.Paperwork
ALL_TARGETS = $(patsubst %.json,%,$(wildcard *.json))
ALL_BRANCHES = master testing develop

all: upd_branches

# clean: remove all intermediate files
clean:
	rm -rf *.app *.flatpak

# dist-clean: remove *everything* that is not stored in Git
dist-clean: clean
	rm -rf $(REPO) .flatpak-builder

# Build a specific branch / tag
# Will export to the Flatpak repository $(REPO)
%.app: ../work.openpaper.Paperwork.json
	@echo flatpak-builder $< --\> $@ \($(REPO) ${EXPORT_ARGS} ${ARCH_ARGS}\)
	cd ../ && flatpak-builder --install-deps-from=flathub --repo=$(REPO) -s "Build of Paperwork $(@:%.app=%) `date`" ${EXPORT_ARGS} ${ARCH_ARGS} $(CURDIR)/$@ $(CURDIR)/../work.openpaper.Paperwork.json

upd_repo:
	@echo flatpak build-update-repo $(REPO) \($(REPO) ${EXPORT_ARGS} ${ARCH_ARGS}\)
	flatpak build-update-repo --generate-static-deltas --prune ${EXPORT_ARGS} $(REPO)

# Build all branches and tags and update the Flatpak repository $(REPO)
mk_all: $(patsubst %,%.app,$(ALL_TARGETS))
	$(MAKE) upd_repo

# Build only the branches and update the Flatpak repository $(REPO)
upd_branches: $(patsubst %,%.app,$(ALL_BRANCHES))
	$(MAKE upd_repo)

# Can be used if you call %.app manually first
# Build a Flatpak bundle
%.flatpak: %.app
	$(MAKE) upd_repo
	@echo flatpak build-bundle $(REPO) --\> $@ \(${EXPORT_ARGS} ${ARCH_ARGS} branch: $(@:%.flatpak=%)\)
	flatpak -v build-bundle ${ARCH_ARGS} $(REPO) $@ $(APP) $(@:%.flatpak=%)

# Build all Flatpak bundles
bundles: $(patsubst %,%.flatpak,$(ALL_TARGETS))

.PHONY: all clean dist-clean mkrepo bundles upd_repo
