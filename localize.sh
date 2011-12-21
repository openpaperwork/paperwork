#!/bin/sh

# List of langs supported by Paperwork. Langs are separated by spaces.
# For each language, the most common system locale and its short writing
# must be specified (separated by ':')
LANGS="fr_FR.UTF-8:fr"

if [ $# -ne 1 ]
then
	echo "usage:" >&2
	echo "  $0 (upd-po|gen-mo)" >&2
	echo "" >&2
	echo "  upd-po: Will generate or update .po files" >&2
	echo "  gen-mo: Will use .po files to regenerate the .mo file" >&2
	exit 1
fi

if ! [ -d src ]
then
	echo "$0: Must be run from the root of the paperwork source tree" >&2
	exit 2
fi

if [ "$1" = "upd-po" ]
then
	mkdir -p locale

	rm -f locale/messages.pot
	for glade_file in src/*.glade
	do
		echo "${glade_file} --> .glade.h ..."
		intltool-extract --type=gettext/glade ${glade_file} > /dev/null
	done
	echo "*.py + *.glade.h --> locale/messages.pot"
	xgettext -k_ -kN_ -o locale/messages.pot src/*.py src/*.glade.h > /dev/null
	rm -f src/*.glade.h

	for lang in ${LANGS}
	do
		locale=$(echo $lang | cut -d: -f1)
		po_file=locale/$(echo $lang | cut -d: -f2).po

		if ! [ -f ${po_file} ]
		then
			echo "locale/messages.pot --> ${po_file} (gen)"
			msginit --no-translator -l ${locale} -i locale/messages.pot -o ${po_file} > /dev/null
		else
			echo "locale/messages.pot --> ${po_file} (upd)"
			msgmerge -U ${po_file} locale/messages.pot > /dev/null
		fi
	done

	echo "Done"
	exit 0
fi

if [ "$1" = "gen-mo" ]
then
	for lang in ${LANGS}
	do
		long_locale=$(echo $lang | cut -d: -f1)
		short_locale=$(echo $lang | cut -d: -f2)
		po_file="locale/${short_locale}.po"
		locale_dir=locale/${short_locale}/LC_MESSAGES

		echo "${po_file} --> ${locale_dir}/paperwork.mo"
		rm -rf local/${short_locale}
		mkdir -p ${locale_dir}
		msgfmt ${po_file} -o ${locale_dir}/paperwork.mo
	done

	echo "Done"
	exit 0
fi

