#!/usr/bin/bash
git log -1

USER=gitlab-runner

WORKDIR=/flatpak/build
MNTDIR=/flatpak/mnt

LOCKDIR=/tmp/build.lock.d
PIDFILE=${LOCKDIR}/pid

REPO_SSHFS_SERVER=flatpak@flatpak-builder-internal.svc
REPO_SSHFS_PATH_GPG=/data/gnupg
REPO_SSHFS_PATH_REPO=/data/repository
REPO_SSHFS_OPTS="-o IdentityFile=${LOCKDIR}/ssh_key"

EXTENSION_VERSION=22.08

branch="${CI_COMMIT_REF_NAME}"
if [ -z "${branch}" ] ; then
	branch=master
fi

echo "Branch: ${branch}"

if [ -z "${FLATPAK_BUILDER_SSH_KEY}" ] ; then
	echo No SSH key. Nothing to do
	exit 0
fi



msg() {
	echo "#####" "$@"
}

download()
{
	url="$1"
	out="$2"

	echo "${url} --> ${out} ..."
	if ! wget -q "${url}" -O "${out}" ; then
		echo "FAILED"
		rm -f "${out}"
		exit 1
	fi
	echo "OK"
}

cleanup() {
	fusermount -u ${MNTDIR}/gpg
	fusermount -u ${MNTDIR}/repo
	msg "Cleaning up ${LOCKDIR}"
	rm -rf ${LOCKDIR}
}

runx() {
	msg "$@"
	if ! "$@" ; then
		echo FAILED
		cleanup
		exit 1
	fi
}

export LANG=C

if ! mkdir ${LOCKDIR} ; then
	pid=$(cat ${PIDFILE})
	msg "Lock directory present (PID: ${pid})"
	if kill -0 ${pid} ; then
		msg "PID ${pid} alive"
		exit 1
	fi
fi

# possible race condition if the other was stopping
# -> re-mkdir
mkdir -p ${LOCKDIR}
chmod 700 ${LOCKDIR}

msg "PID: $$ \> ${PIDFILE}"
echo $$ > ${PIDFILE}
echo ${FLATPAK_BUILDER_SSH_KEY} | base64 -d > ${LOCKDIR}/ssh_key
chmod 600 ${LOCKDIR}/ssh_key

fusermount -u ${MNTDIR}/gpg
fusermount -u ${MNTDIR}/repo

mkdir -p ${MNTDIR}/gpg
runx sshfs ${REPO_SSHFS_SERVER}:${REPO_SSHFS_PATH_GPG} ${MNTDIR}/gpg ${REPO_SSHFS_OPTS}

mkdir -p ${MNTDIR}/repo
runx sshfs ${REPO_SSHFS_SERVER}:${REPO_SSHFS_PATH_REPO} ${MNTDIR}/repo ${REPO_SSHFS_OPTS}

# We make our own opy of the repository: there will be a big .flatpak-builder
# created in it with a lot of cache files we want to reuse later.
mkdir -p "${WORKDIR}/git"
cd "${WORKDIR}/git"
if ! [ -d paperwork ] ; then
	runx git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git ;
fi
cd paperwork
runx git checkout "${branch}"
runx git pull

runx flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

cd flatpak/

rm -f data.tar.gz

download "https://download.openpaper.work/data/paperwork/${branch}_latest/data.tar.gz" ../data.tar.gz

export EXPORT_ARGS="--gpg-sign=E5ACE6FEA7A6DD48"
export REPO=${MNTDIR}/repo

for arch in x86_64 ; do
	msg "=== Architecture: ${arch} ==="

	export ARCH_ARGS=--arch=${arch}

	runtime=$(jq -r "(.runtime + \"/${arch}/\" + .\"runtime-version\")" ../work.openpaper.Paperwork.json)
	msg "Runtime: $runtime"
	sdk=$(echo $runtime | sed s/Platform/Sdk/g)
	msg "SDK: $sdk"
	runx flatpak install -y --user ${runtime}
	runx flatpak install -y --user ${sdk}

	for extension in $(jq -r '."sdk-extensions"[]' ../work.openpaper.Paperwork.json) ; do
		extension="${extension}/${arch}/${EXTENSION_VERSION}"
		msg "Extension: ${extension}"
		runx flatpak install -y --user ${extension}
	done

	runx make clean
	runx make ${branch}.app
	runx make upd_repo
	runx make clean
done

chmod -R a+rX ${REPO}

cleanup
