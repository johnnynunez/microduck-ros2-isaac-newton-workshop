FROM ubuntu:24.04@sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c
COPY docker/install_ros5.sh /bootstrap/install_ros5.sh
RUN bash /bootstrap/install_ros5.sh
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
