# Run paperwork with a Docker container

Install Docker and just run :

    docker run -ti --rm \
      -e DISPLAY=$DISPLAY -e XAUTHORITY=$HOME/.Xauthority -e HOME=$HOME -e USER=$USER \
      -v $HOME:$HOME -v /tmp/.X11-unix:/tmp/.X11-unix -v /etc/sane.d/:/etc/sane.d/ \
      tclavier/paperwork    

The docker container `tclavier/paperwork` is build on each commit. Each tags are also build and tag with same tag.

# Test your development with Docker container

Clone this repository, swith on good branch and run 

    docker build -t paperwork .
    docker run -ti --rm \
      -e DISPLAY=$DISPLAY -e XAUTHORITY=$HOME/.Xauthority -e HOME=$HOME -e USER=$USER \
      -v $HOME:$HOME -v /tmp/.X11-unix:/tmp/.X11-unix -v /etc/sane.d/:/etc/sane.d/ \
      paperwork    
