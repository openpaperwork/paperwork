ALL_COMPONENTS = $(wildcard paperwork-*)

help:
	@echo "make help: display this message"
	@echo "make install : run 'python3 ./setup.py install' on all components"
	@echo "make uninstall : run 'pip3 uninstall -y (component)' on all components"
	@echo "Components:" $(ALL_COMPONENTS:%=%_install)

%_install:
	echo "Installing $(@:%_install=%)"
	(cd $(@:%_install=%) ; python3 ./setup.py install)

%_uninstall:
	echo "Uninstalling $(@:%_uninstall=%)"
	pip3 uninstall -y $(subst -,_,$(@:%_uninstall=%))

paperwork-gtk_uninstall:
	echo "Uninstalling paperwork-gtk"
	pip3 uninstall -y paperwork

install: $(ALL_COMPONENTS:%=%_install)

uninstall: $(ALL_COMPONENTS:%=%_uninstall)

.PHONY: help install uninstall
