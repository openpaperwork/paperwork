# order matters (dependencies)
ALL_COMPONENTS = \
	openpaperwork-core \
	openpaperwork-gtk \
	paperwork-backend \
	paperwork-shell \
	paperwork-gtk

RELEASE ?=

build:


openpaperwork-core_install_py:
	echo "Installing openpaperwork-core"
	$(MAKE) -C openpaperwork-core install_py

openpaperwork-gtk_install_py: openpaperwork-core_install_py
	echo "Installing openpaperwork-gtk"
	$(MAKE) -C openpaperwork-gtk install_py

paperwork-backend_install_py: openpaperwork-core_install_py
	echo "Installing paperwork-backend"
	$(MAKE) -C paperwork-backend install_py

paperwork-shell_install_py: \
		openpaperwork-core_install_py \
		paperwork-backend_install_py
	echo "Installing paperwork-shell"
	$(MAKE) -C paperwork-shell install_py

paperwork-gtk_install_py: \
		openpaperwork-core_install_py \
		openpaperwork-gtk_install_py \
		paperwork-backend_install_py
	echo "Installing paperwork-gtk"
	$(MAKE) -C paperwork-gtk install_py

clean: $(ALL_COMPONENTS:%=%_clean)
	rm -rf build dist
	rm -rf venv
	rm -f data.tar.gz
	make -C sub/libinsane clean || true
	make -C sub/libpillowfight clean || true
	make -C sub/pyocr clean || true

install_py: download_data $(ALL_COMPONENTS:%=%_install_py)

install: install_py

uninstall: $(ALL_COMPONENTS:%=%_uninstall)

uninstall_py: $(ALL_COMPONENTS:%=%_uninstall_py)

uninstall_c: $(ALL_COMPONENTS:%=%_uninstall_c)

check: $(ALL_COMPONENTS:%=%_check)

test: $(ALL_COMPONENTS:%=%_test)

data: $(ALL_COMPONENTS:%=%_data)

upload_data: data
	tar -cvzf data.tar.gz \
		paperwork-backend/src/paperwork_backend/authors/*.json \
		paperwork-gtk/src/paperwork_gtk/model/help/out/*.pdf \
		paperwork-gtk/src/paperwork_gtk/icon/out/*.png
	ci/deliver_data.sh data.tar.gz

data.tar.gz:
	ci/download_data.sh data.tar.gz

paperwork-gtk/src/paperwork_gtk/model/help/out/usage.pdf: data.tar.gz
	tar -xvzf data.tar.gz
	touch paperwork-gtk/src/paperwork_gtk/model/help/out/usage.pdf

download_data: paperwork-gtk/src/paperwork_gtk/model/help/out/usage.pdf

doc: $(ALL_COMPONENTS:%=%_doc)

upload_doc: $(ALL_COMPONENTS:%=%_upload_doc)

release_pypi: download_data l10n_compile
	$(MAKE) $(ALL_COMPONENTS:%=%_release_pypi) RELEASE=${RELEASE}

release: $(ALL_COMPONENTS:%=%_release)
ifeq (${RELEASE}, )
	@echo "You must specify a release version (make release RELEASE=1.2.3)"
	@echo "Also makes sure to update:"
	@echo "- AUTHORS.ui.json"
	exit 1
else
	@echo "Will release: ${RELEASE}"
	git tag -a ${RELEASE} -m ${RELEASE}
	git push origin ${RELEASE}
	make clean
	make release_pypi
	@echo "All done"
	@echo "IMPORTANT: Don't forgot to add the latest release on Flathub !"
endif

linux_exe: $(ALL_COMPONENTS:%=%_linux_exe)

libinsane_win64:
	${MAKE} -C sub/libinsane clean
	${MAKE} -C sub/libinsane install PREFIX=/ucrt64

pyocr_win64:
	${MAKE} -C sub/pyocr install

libpillowfight_win64:
	${MAKE} -C sub/libpillowfight install_py

windows_exe:
	# dirty hack to make cx_freeze happy
	# Cx_freeze looks for a file sqlite3.dll whereas in MSYS2, it's called
	# libsqlite3-0.dll
	mkdir -p /ucrt64/DLLs
	cp /ucrt64/bin/libsqlite3-0.dll /ucrt64/DLLs/sqlite3.dll

	rm -rf $(CURDIR)/build/exe
	$(MAKE) $(ALL_COMPONENTS:%=%_windows_exe)

	# a bunch of things are missing
	mkdir -p $(CURDIR)/build/exe/lib
	cp -Ra /ucrt64/lib/gdk-pixbuf-2.0 $(CURDIR)/build/exe/lib
	# 2nd part of the dirty hack to make cx_freeze happy
	rm -f $(CURDIR)/build/exe/lib/sqlite3.dll

	mkdir -p $(CURDIR)/build/exe/share
	cp -Ra /ucrt64/share/icons $(CURDIR)/build/exe/share
	cp -Ra /ucrt64/share/locale $(CURDIR)/build/exe/share
	cp -Ra /ucrt64/share/themes $(CURDIR)/build/exe/share
	cp -Ra /ucrt64/share/fontconfig $(CURDIR)/build/exe/share
	cp -Ra /ucrt64/share/poppler $(CURDIR)/build/exe/share
	cp -Ra /ucrt64/share/glib-2.0 $(CURDIR)/build/exe/share

	mkdir -p dist
	(cd $(CURDIR)/build/exe ; zip -r ../../dist/paperwork.zip *)

l10n_extract: $(ALL_COMPONENTS:%=%_l10n_extract)

l10n_compile: $(ALL_COMPONENTS:%=%_l10n_compile)

help:
	@echo "make build: run 'python3 ./setup.py build' in all components"
	@echo "make clean"
	@echo "make help: display this message"
	@echo "make install : run 'python3 ./setup.py install' on all components"
	@echo "make release"
	@echo "make uninstall : run 'pip3 uninstall -y (component)' on all components"
	@echo "make l10n_extract"
	@echo "make l10n_compile"
	@echo "Components:" ${ALL_COMPONENTS}

%_check:
	echo "Checking $(@:%_check=%)"
	$(MAKE) -C $(@:%_check=%) check

%_test:
	echo "Testing $(@:%_test=%)"
	$(MAKE) -C $(@:%_test=%) test

%_upload_doc:
	echo "Uploading doc of $(@:%_upload_doc=%)"
	$(MAKE) -C $(@:%_upload_doc=%) upload_doc

%_doc:
	echo "Generating doc of $(@:%_doc=%)"
	$(MAKE) -C $(@:%_doc=%) doc

%_data:
	echo "Generating data files of $(@:%_data=%)"
	$(MAKE) -C $(@:%_data=%) data

%_clean:
	echo "Cleaning $(@:%_clean=%)"
	$(MAKE) -C $(@:%_clean=%) clean

%_uninstall:
	echo "Uninstalling $(@:%_uninstall=%)"
	$(MAKE) -C $(@:%_uninstall=%) uninstall

%_uninstall_py:
	echo "Uninstalling $(@:%_uninstall_py=%)"
	$(MAKE) -C $(@:%_uninstall=%) uninstall_py

%_uninstall_c:
	echo "Uninstalling $(@:%_uninstall_c=%)"
	$(MAKE) -C $(@:%_uninstall=%) uninstall_c

%_release:
	echo "Releasing $(@:%_release=%)"
	$(MAKE) -C $(@:%_release=%) release RELEASE=$(RELEASE)

%_release_pypi:
	echo "Releasing $(@:%_release_pypi=%)"
	$(MAKE) -C $(@:%_release_pypi=%) release_pypi

%_linux_exe:
	echo "Building Linux exe for $(@:%_linux_exe=%)"
	$(MAKE) -C $(@:%_linux_exe=%) linux_exe

%_windows_exe: l10n_compile download_data libinsane_win64 pyocr_win64 libpillowfight_win64
	echo "Building Windows exe for $(@:%_windows_exe=%)"
	$(MAKE) -C $(@:%_windows_exe=%) windows_exe

%_l10n_extract:
	echo "Extracting translatable strings from $(@:%_l10n_extract=%)"
	$(MAKE) -C $(@:%_l10n_extract=%) l10n_extract

%_l10n_compile:
	echo "Compiling translated strings for $(@:%_l10n_compile=%)"
	$(MAKE) -C $(@:%_l10n_compile=%) l10n_compile

venv/bin/activate:
	echo "Building virtual env"
	make -C sub/libinsane build_c
	virtualenv venv

venv: venv/bin/activate

.PHONY: help build clean test check install install_py install_c uninstall \
	uninstall_c uninstall_py release release_pypi libinsane_win64 \
	pyocr_win64 libpillowfight_win64 doc upload_doc data upload_data \
	download_data l10n_extract l10n_compile
