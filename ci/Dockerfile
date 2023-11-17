FROM debian:trixie

RUN mkdir -p /usr/share/man/man1
RUN apt-get update \
    && apt-get install -y -q \
        binutils \
        build-essential \
        ca-certificates \
        cmake \
        coreutils \
        desktop-file-utils \
        doxygen \
        fakeroot \
        flake8 \
        fuse3 \
        gcc \
        gettext \
        git \
        gobject-introspection \
        graphviz \
        gtk-doc-tools \
        imagemagick \
        libcunit1-ncurses-dev \
        libgdk-pixbuf2.0-dev \
        libgirepository1.0-dev \
        libgtk-3-dev \
        libjpeg-dev \
        libreoffice \
        libsane-dev \
        make \
        meson \
        openjdk-11-jre \
        patchelf \
        plantuml \
        po4a \
        pycodestyle \
        python3 \
        python3-dev \
        python3-gi \
        python3-importlib-metadata \
        python3-pefile \
        python3-pil \
        python3-pip \
        python3-pkg-resources \
        python3-recommonmark \
        python3-scipy \
        python3-sphinx \
        python3-sphinxcontrib.plantuml \
        python3-virtualenv \
        python3-wheel \
        rclone \
        squashfs-tools \
        strace \
        texlive \
        texlive-lang-english \
        texlive-lang-french \
        texlive-lang-german \
        texlive-latex-extra \
        texlive-latex-recommended \
        tox \
        util-linux \
        valac \
        valgrind \
        virtualenv \
        wget \
        xvfb \
        zlib1g-dev \
        zsync \
        && apt-get clean

# Libinsane build dependencies
# WORKAROUND(Jflesch): manpages is required to install some of the
# openjdk-jre and openjdk-jre is required for plantuml, which is required
# to generate documentation
RUN apt-get install --no-install-recommends -y -q \
        doxygen \
        graphviz \
        gtk-doc-tools \
        plantuml \
        && apt-get clean

