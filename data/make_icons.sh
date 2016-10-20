#!/bin/sh

for size in 16 24 30 32 48 50 64 100 150 256 ; do
	echo "Generating icon ${size}x${size} ..."
	inkscape -w ${size} -h ${size} -e paperwork_${size}.png paperwork.svg
	if [ ${size} -lt 256 ]; then  # max size for .ico files
		convert paperwork_${size}.png paperwork_${size}.ico
	fi
done
