VERSION_FILE = src/paperwork/_version.py
PYTHON ?= python3

build: build_c build_py

install: install_py install_c

uninstall: uninstall_py

build_py: ${VERSION_FILE}
	${PYTHON} ./setup.py build

build_c:

version: ${VERSION_FILE}

${VERSION_FILE}:
	echo "# -*- coding: utf-8 -*-" >| $@
	echo -n "version = \"" >> $@
	echo -n $(shell git describe --always) >> $@
	echo "\"" >> $@
	echo "authors_code = \"\"\"" >> $@
	echo "    Code contributors:" >> $@
	git shortlog -sne >> $@
	echo "\"\"\"" >> $@
	echo >> $@
	cat ../AUTHORS.py >> $@

doc:

check:
	flake8 --exclude=_version.py src/paperwork

test:

exe:
ifeq ($(OS),Windows_NT)
	pyinstaller pyinstaller/win64.spec
else
	echo "paperwork-gtk: make exe: Windows Only"
endif

release:
ifeq (${RELEASE}, )
	@echo "You must specify a release version (make release RELEASE=1.2.3)"
else
	@echo "Will release: ${RELEASE}"
	@echo "Checking release is in ChangeLog ..."
	grep ${RELEASE} ChangeLog
	@echo "Checking release is in data/work.openpaper.Paperwork.appdata.xml ..."
	grep ${RELEASE} data/work.openpaper.Paperwork.appdata.xml
	@echo "Checking Flatpak files ..."
	[ -e flatpak/${RELEASE}.json ]
	grep ${RELEASE} flatpak/release.json
	@echo "Releasing ..."
	git tag -a ${RELEASE} -m ${RELEASE}
	git push origin ${RELEASE}
	make clean
	make version
	${PYTHON} ./setup.py sdist upload
	@echo "All done"
	@echo "IMPORTANT: Don't forgot to update the latest release on Flathub !"
endif

clean:
	rm -f ${VERSION_FILE}
	rm -rf build dist src/*.egg-info

# PIP_ARGS is used by Flatpak build
install_py: ${VERSION_FILE}
	${PYTHON} ./setup.py install ${PIP_ARGS}

install_c:

uninstall_py:
	pip3 uninstall -y paperwork

uninstall_c:

help:
	@echo "make build || make build_py"
	@echo "make check"
	@echo "make help: display this message"
	@echo "make install || make install_py"
	@echo "make uninstall || make uninstall_py"
	@echo "make release"

.PHONY: \
	build \
	build_c \
	build_py \
	check \
	doc \
	exe \
	help \
	install \
	install_c \
	install_py \
	release \
	test \
	uninstall \
	uninstall_c \
	version
