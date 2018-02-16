# order matters (dependencies)
ALL_COMPONENTS = paperwork-backend paperwork-gtk

build: $(ALL_COMPONENTS:%=%_build)

clean: $(ALL_COMPONENTS:%=%_clean)

install: $(ALL_COMPONENTS:%=%_install)

install_py: $(ALL_COMPONENTS:%=%_install_py)

install_c: $(ALL_COMPONENTS:%=%_install_c)

uninstall: $(ALL_COMPONENTS:%=%_uninstall)

uninstall_py: $(ALL_COMPONENTS:%=%_uninstall_py)

uninstall_c: $(ALL_COMPONENTS:%=%_uninstall_c)

version: $(ALL_COMPONENTS:%=%_version)

check: $(ALL_COMPONENTS:%=%_check)

test: $(ALL_COMPONENTS:%=%_test)

doc: $(ALL_COMPONENTS:%=%_doc)

release: $(ALL_COMPONENTS:%=%_release)

linux_exe: $(ALL_COMPONENTS:%=%_linux_exe)

windows_exe: $(ALL_COMPONENTS:%=%_windows_exe)

help:
	@echo "make build: run 'python3 ./setup.py build' in all components"
	@echo "make clean"
	@echo "make help: display this message"
	@echo "make install : run 'python3 ./setup.py install' on all components"
	@echo "make release"
	@echo "make uninstall : run 'pip3 uninstall -y (component)' on all components"
	@echo "Components:" ${ALL_COMPONENTS}

%_version:
	echo "Making version file $(@:%_version=%)"
	$(MAKE) -C $(@:%_version=%) version

%_check:
	echo "Checking $(@:%_check=%)"
	$(MAKE) -C $(@:%_check=%) check

%_test:
	echo "Checking $(@:%_test=%)"
	$(MAKE) -C $(@:%_test=%) test

%_doc:
	echo "Checking $(@:%_doc=%)"
	$(MAKE) -C $(@:%_doc=%) doc

%_build:
	echo "Building $(@:%_build=%)"
	$(MAKE) -C $(@:%_build=%) build

%_clean:
	echo "Building $(@:%_clean=%)"
	$(MAKE) -C $(@:%_clean=%) clean

%_install:
	echo "Installing $(@:%_install=%)"
	$(MAKE) -C $(@:%_install=%) install

%_build_py:
	echo "Building $(@:%_build_py=%)"
	$(MAKE) -C $(@:%_build=%) build_py

%_install_py:
	echo "Installing $(@:%_install_py=%)"
	$(MAKE) -C $(@:%_build=%) install_py

%_build_c:
	echo "Building $(@:%_build_c=%)"
	$(MAKE) -C $(@:%_build=%) build_c

%_install_c:
	echo "Installing $(@:%_install_c=%)"
	$(MAKE) -C $(@:%_build=%) install_c

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
	$(MAKE) -C $(@:%_release=%) release

%_linux_exe:
	echo "Building Linux exe for $(@:%_linux_exe=%)"
	$(MAKE) -C $(@:%_linux_exe=%) linux_exe

%_windows_exe:
	echo "Building Windows exe for $(@:%_windows_exe=%)"
	$(MAKE) -C $(@:%_windows_exe=%) windows_exe

.PHONY: help build clean test check install install_py install_c uninstall uninstall_c uninstall_py release
