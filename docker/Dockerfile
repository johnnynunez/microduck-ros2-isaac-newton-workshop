ARG ROS_BASE=roscon/ros5-base:5.0
FROM ${ROS_BASE}
SHELL ["/bin/bash", "-c"]
# Reviewed no-work executor cooperation; rejects unreviewed rclpy version/source.
COPY docker/patch_rclpy_executor.py /opt/workshop/patch_rclpy_executor.py
RUN source /opt/ros/lyrical/setup.bash && python3 /opt/workshop/patch_rclpy_executor.py
COPY pyproject.toml README.md LICENSE NOTICE requirements-agent.txt /opt/workshop/
COPY provenance /opt/workshop/provenance
COPY src /opt/workshop/src
COPY ros_ws/src /opt/workshop/ros_ws/src
COPY docker/entrypoint.sh /opt/workshop/entrypoint.sh
WORKDIR /opt/workshop/ros_ws
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m venv --system-site-packages /opt/workshop/venv \
    && /opt/workshop/venv/bin/pip install --timeout 180 --retries 5 --no-deps /opt/workshop \
    && (for attempt in 1 2 3; do \
          /opt/workshop/venv/bin/pip install --timeout 180 --retries 5 --index-url https://pypi.org/simple -r /opt/workshop/requirements-agent.txt && exit 0; \
          echo "CASCADE dependency attempt $attempt failed; retaining build log" >&2; \
          sleep 5; \
        done; exit 1) \
    && source /opt/ros/lyrical/setup.bash && colcon build --parallel-workers 2
ENV ROS_DOMAIN_ID=27 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ENV PYTHONPATH=/opt/workshop/src
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENTRYPOINT ["/bin/bash", "/opt/workshop/entrypoint.sh"]
CMD ["ros2", "launch", "microduck_workshop_ros", "workshop.launch.py"]
