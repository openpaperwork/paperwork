all: paperwork_installer.exe

dll/INetC.dll:
	mkdir -p dll
	rm -rf tmp
	mkdir tmp
	cd tmp ; wget http://nsis.sourceforge.net/mediawiki/images/c/c9/Inetc.zip
	cd tmp ; unzip Inetc.zip
	cd tmp ; mv Plugins/x86-ansi/INetC.dll ../dll
	rm -rf tmp

dll/nsisunz.dll:
	mkdir -p dll
	rm -rf tmp
	mkdir tmp
	cd tmp ; wget http://nsis.sourceforge.net/mediawiki/images/1/1c/Nsisunz.zip
	cd tmp ; unzip Nsisunz.zip
	cd tmp ; mv nsisunz/Release/nsisunz.dll ../dll
	rm -rf tmp

out.nsi: gen_installer_nsi.py
	if [ -z "${RELEASE}" ] ; then echo "Syntax: make RELEASE=x.y.z DOWNLOAD_URI=https://pouet" ; exit 1 ; fi
	echo Release: ${RELEASE}
	echo Download URI: ${DOWNLOAD_URI}
	python3 ./gen_installer_nsi.py ${RELEASE} ${DOWNLOAD_URI}

paperwork_installer.exe: dll/INetC.dll dll/nsisunz.dll out.nsi
	makensis ./out.nsi

clean:
	rm -rf dll
	rm -f out.nsi
	rm -f paperwork_installer.exe

.PHONY = all
