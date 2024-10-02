all: paperwork_stable_installer.exe

dll/INetC.dll:
	mkdir -p dll
	rm -rf tmp
	mkdir tmp
	cd tmp ; wget http://nsis.sourceforge.net/mediawiki/images/c/c9/Inetc.zip
	cd tmp ; unzip Inetc.zip
	cd tmp ; mv Plugins/x86-unicode/INetC.dll ../dll
	rm -rf tmp

dll/nsisunz.dll:
	mkdir -p dll
	rm -rf tmp
	mkdir tmp
	cd tmp ; wget http://nsis.sourceforge.net/mediawiki/images/5/5a/NSISunzU.zip
	cd tmp ; unzip NSISunzU.zip
	cd tmp ; mv "NSISunzU/Plugin unicode/nsisunz.dll" ../dll
	rm -rf tmp

out.nsi: gen_installer_nsi.py
	if [ -z "${RELEASE}" ] ; then echo "Syntax: make RELEASE=x.y.z DOWNLOAD_URI=https://pouet" ; exit 1 ; fi
	echo Release: ${RELEASE}
	echo Download URI: ${DOWNLOAD_URI}
	python ./gen_installer_nsi.py ${RELEASE} ${DOWNLOAD_URI}

paperwork_stable_installer.exe: dll/INetC.dll dll/nsisunz.dll
	rm -f out.nsi
	$(MAKE) out.nsi RELEASE=stable DOWNLOAD_URI=https://download.openpaper.work/windows/amd64/paperwork-master-latest.zip
	makensis ./out.nsi
	mv -f paperwork_installer.exe paperwork_stable_installer.exe

clean:
	rm -rf dll
	rm -f out.nsi
	rm -f paperwork_installer.exe
	rm -f paperwork_stable_installer.exe

upload:
	rclone --config ../ci/rclone.conf \
		copyto \
		paperwork_stable_installer.exe \
		openpaperwork:openpaperwork-download/windows/installer/paperwork_stable_installer.exe

.PHONY: all clean upload
