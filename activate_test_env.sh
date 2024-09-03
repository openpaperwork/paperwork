if ! [ -e sub/libinsane/Makefile ] ; then
	git submodule init
	git submodule update --recursive --remote --init
fi

make venv && \
source venv/bin/activate && \
pip install setuptools && \
cd sub/libinsane && \
source ./activate_test_env.sh && \
cd ../.. && \
make -C sub/pyocr install_py && \
make -C sub/libpillowfight install_py
