#!/bin/sh

directory="$1"
destination="$2"

if ! [ -d "${directory}" ] || [ -z "${destination}" ] ; then
  echo "You must specify a directory to upload and a destination directory"
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

echo "Delivering: ${directory} (${CI_COMMIT_REF_NAME} - ${CI_COMMIT_SHORT_SHA})"

out_name="$(date "+%Y%m%d_%H%M%S")_${CI_COMMIT_REF_NAME}_${CI_COMMIT_SHORT_SHA}"
latest_name="latest"

if ! rclone --config ./ci/rclone.conf copy \
    "${directory}/" \
    "openpaperwork:openpaperwork-doc/${destination}/${out_name}" ; then
  echo "rclone failed"
  exit 1
fi

if ! rclone --config ./ci/rclone.conf sync \
    "${directory}/" \
    "openpaperwork:openpaperwork-doc/${destination}/latest" ; then
  echo "rclone failed"
  exit 1
fi

echo Success
exit 0
