# Starting the Docker containter

## Run paperwork with a Docker container

Install Docker and just run :

    docker run -ti --rm \
      -e DISPLAY=$DISPLAY -e XAUTHORITY=$HOME/.Xauthority -e HOME=$HOME -e USER=$USER \
      -v $HOME:$HOME -v /tmp/.X11-unix:/tmp/.X11-unix -v /etc/sane.d/:/etc/sane.d/ \
      tclavier/paperwork    

The docker container `tclavier/paperwork` is build on each commit. Each tags are also build and tag with same tag.

## Test your development with Docker container

Clone this repository, swith on good branch and run 

    docker build -t paperwork .
    docker run -ti --rm \
      -e DISPLAY=$DISPLAY -e XAUTHORITY=$HOME/.Xauthority -e HOME=$HOME -e USER=$USER \
      -v $HOME:$HOME -v /tmp/.X11-unix:/tmp/.X11-unix -v /etc/sane.d/:/etc/sane.d/ \
      paperwork    

# Troubleshooting

## Docker Installation

At least on some systems the packages `apparmor` and `cgroup-lite` are required.

## Docker Image Execution

    Unable to init server: Could not connect: Connection refused
    (paperwork:22): Gtk-WARNING **: cannot open display: :0.0

Run this command: `xhost local:root` (source: http://stackoverflow.com/questions/28392949/running-chromium-inside-docker-gtk-cannot-open-display-0)
