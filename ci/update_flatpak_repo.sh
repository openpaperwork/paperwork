#!/usr/bin/bash
echo $PWD
git log -1

USER=gitlab-runner

LOCKDIR=/tmp/build.lock.d
PIDFILE=${LOCKDIR}/pid

branch="${CI_COMMIT_REF_NAME}"

echo "Branch: ${branch}"

if [ "${branch}" != "master" ] && [ "${branch}" != "testing" ] && [ "${branch}" != "develop" ]; then
	echo Nothing to do
	exit 0
fi

msg() {
	echo "#####" "$@" "######"
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

export LANG=C

if ! mkdir ${LOCKDIR} ; then
	pid=$(cat ${PIDFILE})
	msg "Lock directory present (PID: ${pid})"
	if kill -0 ${pid} ; then
		msg "PID ${pid} alive"
		exit 1
	fi
fi

cleanup() {
	msg "Cleaning up ${LOCKDIR}"
	rm -rf ${LOCKDIR}
}

# possible race condition if the other was stopping
# -> re-mkdir
mkdir -p ${LOCKDIR}

msg "PID: $$ \> ${PIDFILE}"
echo $$ > ${PIDFILE}

# We make our own copy of the repository: there will be a big .flatpak-builder
# created in it with a lot of cache files we want to reuse later.
mkdir -p ~/git
cd ~/git
if ! [ -d paperwork ] ; then
	if ! git clone https://gitlab.gnome.org/World/OpenPaperwork/paperwork.git ;
	then
		echo "Clone failed !"
		exit 1
	fi
fi
cd paperwork
# reinit work.openpaper.Paperwork.json (only file we modify later)
if ! git checkout work.openpaper.Paperwork.json ; then
	echo "Git checkout work.openpaper.Paperwork.json failed !"
	exit 1
fi
if ! git checkout "${branch}" || ! git pull ; then
	echo "Git pull failed !"
	exit 1
fi

# Set the branches correctly
jq \
	--arg branch "${branch}" \
	'.branch |= $branch' \
	work.openpaper.Paperwork.json \
	| sponge work.openpaper.Paperwork.json
jq \
	--arg branch "${branch}" \
	'(((.modules[] | select(type == "object")) | select(.name == "python-paperwork")).sources[] | select(.type == "git")).branch |= $branch' \
	work.openpaper.Paperwork.json \
	| sponge work.openpaper.Paperwork.json

mkdir -p ~/flatpak  # directory that contains the repository directory

cd flatpak/

rm -f data.tar.gz

download "https://download.openpaper.work/data/paperwork/${branch}_latest/data.tar.gz" ../data.tar.gz

export EXPORT_ARGS="--gpg-sign=E5ACE6FEA7A6DD48"
export REPO=/home/${USER}/flatpak/paperwork_repo

for arch in x86_64 ; do
	msg "=== Architecture: ${arch} ==="

	export ARCH_ARGS=--arch=${arch}

	msg "Cleaning ..."
	if ! make clean ; then
		msg "Clean failed"
		cleanup
		exit 2
	fi

	if [ -z "${branch}" ]; then
		msg "Building ..."
		if ! make ; then
			msg "Build failed"
			cleanup
			exit 2
		fi
	else
		msg "Building branch ${branch} ..."
		if ! make ${branch}.app ; then
			msg "Build failed"
			cleanup
			exit 2
		fi
		if ! make upd_repo ; then
			msg "Repo update failed"
			cleanup
			exit 2
		fi
	fi

	msg "Cleaning ..."
	if ! make clean ; then
		msg "Clean failed"
		cleanup
		exit 2
	fi
done

cd ..

chmod -R a+rX ${HOME}/flatpak

cleanup
