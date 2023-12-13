#!/bin/bash

LANGS="de_DE.UTF-8:de
es_ES.UTF-8:es
fr_FR.UTF-8:fr
oc_FR.UTF-8:oc
uk_UA.UTF-8:uk"

if [ -z "$1" ] || [ -z "$2" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ] ; then
	echo "Usage:"
	echo "  $0 <source_directory> <destination_directory> <mo_name>"
	echo
	echo "Examples:"
	echo "  $0 l10n src/paperwork_gtk/l10n paperwork_gtk"
	echo
	echo "You should probably use 'make l10_compile' instead of calling this script directly"
	exit 1
fi

if ! command -v msgfmt > /dev/null ; then
	echo "msgfmt is missing"
	echo "--> sudo apt install gettext"
	exit 2
fi

src_dir="$1"
dst_dir="$2"
mo_name="$3"

mkdir -p "${dst_dir}"
touch "${dst_dir}/__init__.py"
rm -rf "${dst_dir}/out"

for lang in ${LANGS}
do
	long_locale=$(echo $lang | cut -d: -f1)
	short_locale=$(echo $lang | cut -d: -f2)
	po_file="${src_dir}/${short_locale}.po"
	locale_dir="${dst_dir}/out/${short_locale}/LC_MESSAGES"

	echo "${po_file} --> ${locale_dir}/${mo_name}.mo"

	mkdir -p "${locale_dir}"
	touch "${dst_dir}/out/__init__.py"
	touch "${dst_dir}/out/${short_locale}/__init__.py"
	touch "${locale_dir}/__init__.py"

	if ! msgfmt "${po_file}" -o "${locale_dir}/${mo_name}.mo" ; then
		echo "msgfmt failed ! Unable to update .mo file !"
		exit 2
	fi
done
