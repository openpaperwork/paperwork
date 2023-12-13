#!/bin/sh

input_file="$1"

if ! [ -f "${input_file}" ] ; then
  echo "You must specify an input file to upload"
  exit 1
fi

if [ -z "$RCLONE_CONFIG_OPENPAPERWORK_ACCESS_KEY_ID" ] ; then
  echo "Delivery: No rclone credentials provided."
  exit 0
fi

if ! command -v rclone; then
  echo "rclone not available."
  exit 1
fi

echo "Delivering: ${input_file} (${CI_COMMIT_REF_NAME} - ${CI_COMMIT_SHORT_SHA})"

out_name="${CI_COMMIT_REF_NAME}_${CI_COMMIT_SHORT_SHA}"
latest_name="${CI_COMMIT_REF_NAME}_latest"

if ! rclone --config ./ci/rclone.conf copy \
    "${input_file}" \
    "openpaperwork:openpaperwork-download/data/paperwork/${out_name}/" ; then
  echo "rclone failed"
  exit 1
fi

if ! rclone --config ./ci/rclone.conf sync \
    "${input_file}" \
    "openpaperwork:openpaperwork-download/data/paperwork/${latest_name}/" ; then
  echo "rclone failed"
  exit 1
fi

echo Success
exit 0
