ARG ROS_BASE=roscon/ros5-base:5.0
FROM ${ROS_BASE}
SHELL ["/bin/bash", "-c"]
COPY pyproject.toml README.md LICENSE /opt/workshop/
COPY src /opt/workshop/src
COPY ros_ws/src /opt/workshop/ros_ws/src
COPY docker/entrypoint.sh /opt/workshop/entrypoint.sh
WORKDIR /opt/workshop/ros_ws
RUN python3 -m venv --system-site-packages /opt/workshop/venv && /opt/workshop/venv/bin/pip install --no-deps /opt/workshop && source /opt/ros/lyrical/setup.bash && colcon build --parallel-workers 2
ENV ROS_DOMAIN_ID=27 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ENV PYTHONPATH=/opt/workshop/src
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENTRYPOINT ["/bin/bash", "/opt/workshop/entrypoint.sh"]
CMD ["ros2", "launch", "microduck_workshop_ros", "workshop.launch.py"]
