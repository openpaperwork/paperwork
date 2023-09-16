PYTHON ?= python3

build: build_c build_py

install: install_py install_c

uninstall: uninstall_py

build_py: l10n_compile
	${PYTHON} ./setup.py build

build_c:

doc:

upload_doc:

data:

check:
	${PYTHON} -m pip install ${PIP_ARGS} .[lint]
	flake8 src/paperwork_shell

test: install
	${PYTHON} -m pip install ${PIP_ARGS} .[dev]
	python3 -m pytest -xv tests/

linux_exe:
	rm -rf AppDir appimage-build
	appimage-builder --skip-tests --recipe AppImageBuilder.cli.yml
	rm -rf AppDir appimage-build
	appimage-builder --skip-tests --recipe AppImageBuilder.json.yml

windows_exe: install
	# ugly, but "import pkg_resources" doesn't work in frozen environments
	# and I don't want to have to patch the build machine to fix it every
	# time.
	mkdir -p $(CURDIR)/../build/exe/data
	(cd $(CURDIR)/src && find . -name '*.mo' -exec cp --parents \{\} $(CURDIR)/../build/exe/data \; )

release:
ifeq (${RELEASE}, )
	@echo "You must specify a release version (make release RELEASE=1.2.3)"
	exit 1
else
	@echo "Will release: ${RELEASE}"
	@echo "Checking release is in ChangeLog ..."
	grep ${RELEASE} ChangeLog | grep -v "/xx"
endif

release_pypi:
	@echo "Releasing paperwork-shell ..."
	rm -rf /tmp/venv
	virtualenv /tmp/venv
	. /tmp/venv/bin/activate && pip install build
	. /tmp/venv/bin/activate && ${PYTHON} -m build -s
	rm -rf /tmp/venv
	twine upload $(CURDIR)/dist/*.tar.gz
	@echo "All done"

clean:
	rm -rf AppDir appimage-build
	rm -f *.AppImage
	rm -rf build dist *.egg-info

# PIP_ARGS is used by Flatpak build
install_py: l10n_compile
	${PYTHON} -m pip install ${PIP_ARGS} .

install_c:

uninstall_py:
	pip3 uninstall -y paperwork-shell

uninstall_c:

l10n_extract:
	$(CURDIR)/../tools/l10n_extract.sh "$(CURDIR)/src" "$(CURDIR)/l10n"

l10n_compile:
	$(CURDIR)/../tools/l10n_compile.sh \
		"$(CURDIR)/l10n" \
		"$(CURDIR)/src/paperwork_shell/l10n" \
		"paperwork_shell"

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
	l10n_compile \
	l10n_extract \
	release \
	test \
	uninstall \
	uninstall_c
