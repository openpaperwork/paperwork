# order matters (dependencies)
ALL_COMPONENTS = paperwork-backend paperwork-gtk

build: $(ALL_COMPONENTS:%=%_build)

install: $(ALL_COMPONENTS:%=%_install)

uninstall: $(ALL_COMPONENTS:%=%_uninstall)

help:
	@echo "make build: run 'python3 ./setup.py build' in all components"
	@echo "make help: display this message"
	@echo "make install : run 'python3 ./setup.py install' on all components"
	@echo "make uninstall : run 'pip3 uninstall -y (component)' on all components"
	@echo "Components:" $(ALL_COMPONENTS:%=%_install)

%_build:
	echo "Building $(@:%_build=%)"
	(cd $(@:%_build=%) ; python3 ./setup.py build)

%_install:
	echo "Installing $(@:%_install=%)"
	(cd $(@:%_install=%) ; python3 ./setup.py install ${PIP_ARGS})

%_uninstall:
	echo "Uninstalling $(@:%_uninstall=%)"
	pip3 uninstall -y $(subst -,_,$(@:%_uninstall=%))

paperwork-gtk_uninstall:
	echo "Uninstalling paperwork-gtk"
	pip3 uninstall -y paperwork

.PHONY: help build install uninstall
