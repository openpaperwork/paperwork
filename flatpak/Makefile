REPO = repo
APP = $(patsubst %.json,%,$(wildcard *.json))
VER = 1.2.1

all: app
build: app
app: $(APP)

uninstall:
	flatpak --user uninstall $(APP)

install: build
	flatpak --user install --bundle $(APP:%=%.bundle)

reinstall: uninstall install

clean:
	rm -rf app repo .flatpak-builder $(APP:%=%.bundle)


%: %.json
	rm -rf app
	echo $@
	flatpak-builder --repo=$(REPO) --subject="Build of $@ `date`" ${EXPORT_ARGS} app $<
	flatpak -v build-bundle repo $(patsubst %.json,%.flatpak,$<) $@ $(VER)

.PHONY: all uninstall install build
