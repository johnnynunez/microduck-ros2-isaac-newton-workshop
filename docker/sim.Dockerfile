# Public Ubuntu userspace; no host SDK, credentials or licensed meshes in layers.
ARG UBUNTU_BASE=ubuntu:24.04@sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c
ARG ROS_IMAGE=roscon/microduck-ros5:local
FROM scratch AS download-cache
FROM ${UBUNTU_BASE} AS sim
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive UV_LINK_MODE=copy UV_COMPILE_BYTECODE=0
RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates git python3.12 python3.12-venv python3-pip build-essential     libglib2.0-0 libgl1 libegl1 libx11-6 libxext6 libxrender1 libxi6 libxrandr2     libxfixes3 libxcursor1 libxinerama1 libxxf86vm1 libsm6 libice6 libgomp1     libvulkan1 libasound2t64 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0     libxcomposite1 libxdamage1 libxkbcommon0 libgbm1 libdrm2 libnuma1     && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/bootstrap && /opt/bootstrap/bin/pip install --index-url https://pypi.org/simple uv==0.13.1
ENV PATH=/opt/bootstrap/bin:/opt/IsaacLab/.venv/bin:$PATH
ARG ISAACLAB_COMMIT=e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4
RUN git clone --branch v3.0.0 --depth 1 https://github.com/isaac-sim/IsaacLab.git /opt/IsaacLab     && test "$(git -C /opt/IsaacLab rev-parse HEAD)" = "$ISAACLAB_COMMIT"
WORKDIR /opt/IsaacLab
# Optional --build-context download-cache=/path/to/private-uv-cache is a local
# acceleration only; the default empty stage downloads from the official lock URLs.
RUN --mount=from=download-cache,target=/uv-seed \
    --mount=type=cache,target=/root/.cache/uv \
    cp -a -n /uv-seed/. /root/.cache/uv/ && \
    UV_HTTP_TIMEOUT=600 UV_HTTP_RETRIES=5 UV_CONCURRENT_DOWNLOADS=8 \
    uv sync --frozen --extra isaacsim --python /usr/bin/python3.12 --python-preference only-system
# MaterialX's transitive libXt dependency is needed even for headless cameras.
RUN apt-get update && apt-get install -y --no-install-recommends libxt6t64 libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE NOTICE requirements-sim.txt /opt/workshop/
COPY src /opt/workshop/src
COPY provenance /opt/workshop/provenance
# Explicit security overlay, tested with actual Kit camera/JPEG. Do not re-sync afterwards.
RUN uv pip install --python .venv/bin/python --no-deps /opt/workshop -r /opt/workshop/requirements-sim.txt     && uv pip install --python .venv/bin/python --no-deps Pillow==13.0.0     && uv cache clean
ENV PYTHONUNBUFFERED=1 NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility
# Acceptance is deliberately NOT baked into this image.
WORKDIR /opt/workshop
ENTRYPOINT ["/opt/IsaacLab/.venv/bin/python"]
CMD ["-m", "microduck_workshop.sim.play", "--help"]

# CASCADE runs in the Lyrical Python environment, never inside Isaac Sim's ROS/Jazzy libs.
FROM ${ROS_IMAGE} AS agent
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]
COPY requirements-agent.txt /opt/workshop/requirements-agent.txt
COPY src /opt/workshop/src
# The rebuilt ROS image already installed requirements-agent.txt in this venv.
RUN /opt/workshop/venv/bin/python -m microduck_workshop.agent.api_check
ENV PATH=/opt/workshop/venv/bin:$PATH
ENTRYPOINT ["/bin/bash", "/opt/workshop/entrypoint.sh"]
CMD ["python", "-m", "microduck_workshop.agent.run", "--help"]
