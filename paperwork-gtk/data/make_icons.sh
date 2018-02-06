#!/bin/sh

for size in 16 22 24 30 32 36 42 48 50 64 72 96 100 128 150 160 192 256 512 ; do
	echo "Generating icon ${size}x${size} ..."

	source=paperwork_halo.svg
	if [ ${size} -ge 96 ]; then
		source=paperwork.svg
	fi

	inkscape -w ${size} -h ${size} -e paperwork_${size}.png ${source}
	if [ ${size} -lt 256 ]; then  # max size for .ico files
		convert paperwork_${size}.png paperwork_${size}.ico
	fi
done
