#!/bin/sh

# List of langs supported by Paperwork. Langs are separated by spaces.
# For each language, the most common system locale and its short writing
# must be specified (separated by ':')
LANGS="fr_FR.UTF-8:fr
de_DE.UTF-8:de"

usage()
{
	echo "usage:" >&2
	echo "  $0 (upd-po|gen-mo)" >&2
	echo "" >&2
	echo "  upd-po: Will generate or update .po files" >&2
	echo "  gen-mo: Will use .po files to regenerate the .mo file" >&2
	echo
	echo "Usual steps to update translations are:"
	echo "1) upd-po"
	echo "2) Edit locale/<lang>.po (look for the \"fuzzy\" keyword and empty strings !)"
	echo "3) gen-mo"
	echo "4) commit"
	exit 1
}

if ! [ -d data ]
then
	echo "$0: Must be run from the root of the paperwork source tree" >&2
	exit 2
fi

if [ "$1" = "--help" ] || [ "$1" = "-h" ]
then
	usage
	exit 0
elif [ "$1" = "upd-po" ]
then
	mkdir -p locale
	pot_file=locale/messages.pot

	rm -f ${pot_file}
	for glade_file in \
		$(find data/paperwork -name \*.glade) \
		$(find data/paperwork -name \*.xml)
	do
		echo "${glade_file} --> .(glade|xml).h ..."
		if ! intltool-extract --type=gettext/glade ${glade_file} > /dev/null; then
			echo "intltool-extract Failed ! Unable to extract strings to translate from .glade files !"
			exit 2
		fi
	done
	echo "*.py + *.glade.h --> ${pot_file}"
	xgettext -k_ -kN_ -o ${pot_file} \
		$(find data/paperwork -name \*.py ! -path data/paperwork/labeleditor/__init__.py) \
		$(find data/paperwork -name \*.glade.h) \
		$(find data/paperwork -name \*.xml.h) \
		> /dev/null
	if [ $? -ne 0 ]; then
		echo "xgettext failed ! Unable to extract strings to translate !"
		exit 3
	fi
	rm -f $(find data/paperwork -name \*.glade.h)
	rm -f $(find data/paperwork -name \*.xml.h)

	for lang in ${LANGS}
	do
		locale=$(echo $lang | cut -d: -f1)
		po_file=locale/$(echo $lang | cut -d: -f2).po

		if ! [ -f ${po_file} ]
		then
			echo "${pot_file} --> ${po_file} (gen)"
			msginit --no-translator -l ${locale} -i ${pot_file} -o ${po_file} > /dev/null
		else
			echo "${pot_file} --> ${po_file} (upd)"
			msgmerge -U ${po_file} ${pot_file} > /dev/null
		fi
		if [ $? -ne 0 ] ; then
			echo "msginit / msgmerge failed ! Unable to create or update .po file !"
			exit 4
		fi
	done

	echo "Done"
	exit 0

elif [ "$1" = "gen-mo" ]
then
	for lang in ${LANGS}
	do
		long_locale=$(echo $lang | cut -d: -f1)
		short_locale=$(echo $lang | cut -d: -f2)
		po_file="locale/${short_locale}.po"
		locale_dir=data/locale/${short_locale}/LC_MESSAGES

		echo "${po_file} --> ${locale_dir}/paperwork.mo"
		rm -rf data/locale/${short_locale}
		mkdir -p ${locale_dir}
		if ! msgfmt ${po_file} -o ${locale_dir}/paperwork.mo ; then
			echo "msgfmt failed ! Unable to update .mo file !"
			exit 5
		fi
	done

	echo "Done"
	exit 0

else
	usage
	exit 1
fi

