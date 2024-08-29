#!/bin/sh

binary="$1"
os="$2"
exe_suffix="$3"
name="$4"
arch="amd64"

if [ -z "$RCLONE_CONFIG_OPENPAPERWORK_ACCESS_KEY_ID" ] ; then
  echo "Delivery: No rclone credentials provided."
  exit 0
fi

if ! command -v rclone; then
  echo "rclone not available."
  exit 1
fi

if [ -z "$name" ] ; then
  name=paperwork
fi

echo "Delivering: ${binary} (${CI_COMMIT_REF_NAME} - ${CI_COMMIT_SHORT_SHA})"
echo "Destination: ${os}/${arch} (${name} ${exe_suffix})"

out_name="${name}-${CI_COMMIT_REF_NAME}-${CI_COMMIT_SHORT_SHA}${exe_suffix}"
latest_name="${name}-${CI_COMMIT_REF_NAME}-latest${exe_suffix}"


echo "rclone: ${out_name}"

if ! rclone --config ./ci/rclone.conf copyto "${binary}" "openpaperwork:openpaperwork-download/${os}/${arch}/${out_name}" ; then
  echo "rclone failed"
  exit 1
fi

echo "rclone: ${latest_name}"

if ! rclone --config ./ci/rclone.conf copyto \
    "openpaperwork:openpaperwork-download/${os}/${arch}/${out_name}" \
    "openpaperwork:openpaperwork-download/${os}/${arch}/${latest_name}" ; then
  echo "rclone failed"
  exit 1
fi

echo Success
exit 0
