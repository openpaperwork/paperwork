from debian
env DEBIAN_FRONTEND noninteractive
run sed -e 's/httpredir.debian.org/debian.mirrors.ovh.net/g' -i /etc/apt/sources.list
arg http_proxy
run apt-get update \
    && apt-get install -y \
      build-essential \
      ca-certificates \
      gir1.2-gtk-3.0 \
      gir1.2-poppler-0.18 \
      gnome-icon-theme \
      gnome-icon-theme-symbolic \
      libenchant-dev \
      python-dev \
      python-gi \
      python-gi-cairo \
      python-gi-cairo \
      python-pil \
      python-setuptools \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-fra \
    && apt-get clean
add . /usr/local/share/paperwork
workdir /usr/local/share/paperwork
run python ./setup.py install 
add start /usr/local/bin/start
run chmod +x /usr/local/bin/start
cmd ["/usr/local/bin/start"]
#run paperwork-chkdeps
