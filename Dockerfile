from debian
env DEBIAN_FRONTEND noninteractive
run sed -e 's/httpredir.debian.org/debian.mirrors.ovh.net/g' -i /etc/apt/sources.list
arg http_proxy
run apt update \
    && apt install -y \
      build-essential \
      ca-certificates \
      gir1.2-gtk-3.0 \
      gir1.2-poppler-0.18 \
      gnome-icon-theme \
      gnome-icon-theme-symbolic \
      libenchant-dev \
      gir1.2-gtk-3.0 \
      gir1.2-poppler-0.18 \
      python3-dev \
      python3-gi \
      python3-gi-cairo \
      python3-gi-cairo \
      python3-pil \
      python3-pip \
      python3-setuptools \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-fra \
    && apt-get clean

run pip3 install paperwork

add scripts/start /usr/local/bin/start
run chmod +x /usr/local/bin/start
cmd ["/usr/local/bin/start"]
#run paperwork-chkdeps
