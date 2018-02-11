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

check: $(ALL_COMPONENTS:%=%_check)

test: $(ALL_COMPONENTS:%=%_test)

doc: $(ALL_COMPONENTS:%=%_doc)

release: $(ALL_COMPONENTS:%=%_release)

exe: $(ALL_COMPONENTS:%=%_exe)

help:
	@echo "make build: run 'python3 ./setup.py build' in all components"
	@echo "make clean"
	@echo "make help: display this message"
	@echo "make install : run 'python3 ./setup.py install' on all components"
	@echo "make release"
	@echo "make uninstall : run 'pip3 uninstall -y (component)' on all components"
	@echo "Components:" ${ALL_COMPONENTS}

%_check:
	echo "Checking $(@:%_check=%)"
	make -C $(@:%_check=%) check

%_test:
	echo "Checking $(@:%_test=%)"
	make -C $(@:%_test=%) test

%_doc:
	echo "Checking $(@:%_doc=%)"
	make -C $(@:%_doc=%) doc

%_build:
	echo "Building $(@:%_build=%)"
	make -C $(@:%_build=%) build

%_clean:
	echo "Building $(@:%_clean=%)"
	make -C $(@:%_clean=%) clean

%_install:
	echo "Installing $(@:%_install=%)"
	make -C $(@:%_install=%) install

%_build_py:
	echo "Building $(@:%_build_py=%)"
	make -C $(@:%_build=%) build_py

%_install_py:
	echo "Installing $(@:%_install_py=%)"
	make -C $(@:%_build=%) install_py

%_build_c:
	echo "Building $(@:%_build_c=%)"
	make -C $(@:%_build=%) build_c

%_install_c:
	echo "Installing $(@:%_install_c=%)"
	make -C $(@:%_build=%) install_c

%_uninstall:
	echo "Uninstalling $(@:%_uninstall=%)"
	make -C $(@:%_uninstall=%) uninstall

%_uninstall_py:
	echo "Uninstalling $(@:%_uninstall_py=%)"
	make -C $(@:%_uninstall=%) uninstall_py

%_uninstall_c:
	echo "Uninstalling $(@:%_uninstall_c=%)"
	make -C $(@:%_uninstall=%) uninstall_c

%_release:
	echo "Releasing $(@:%_release=%)"
	make -C $(@:%_release=%) release

%_exe:
	echo "Building exe for $(@:%_exe=%)"
	make -C $(@:%_exe=%) exe

.PHONY: help build clean test check install install_py install_c uninstall uninstall_c uninstall_py release
