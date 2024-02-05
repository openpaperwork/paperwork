#!/usr/bin/env bash

if [ -z "$1" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ] ; then
	echo "Convert all your Paperwork documents into PDF."
	echo "Requires 'paperwork-json', 'paperwork-cli' and GNU parallel."
	echo
	echo "Syntax:"
	echo "  $0 <output directory>"
	exit 1
fi

out_dir="$1"

mkdir -p "$out_dir"

for doc_id in $(paperwork-json search --limit 10000000 "" | jq -r ".[]") ; do
	echo paperwork-cli export ${doc_id} \
			-f automatic_pdf \
			-o "${out_dir}/${doc_id}.pdf"
done | parallel --halt now,fail=1 sh -c {}

echo "All done !"
