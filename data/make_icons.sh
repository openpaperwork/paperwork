#!/bin/sh

for size in 16 22 24 30 32 36 42 48 50 64 72 96 100 128 150 160 192 256 512 ; do
	echo "Generating icon ${size}x${size} ..."
	mkdir -p ${size}
	inkscape -w ${size} -h ${size} -e ${size}/paperwork.png paperwork.svg
	if [ ${size} -lt 256 ]; then  # max size for .ico files
		convert ${size}/paperwork.png paperwork_${size}.ico
	fi

	if [ ${size} = "100" ]; then
		cp ${size}/paperwork.png paperwork_100.png
	fi
done
