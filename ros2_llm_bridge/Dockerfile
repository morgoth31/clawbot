FROM ros:humble-ros-base-jammy

# Internal system setup
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement list (we'll assume a requirements.txt with FastAPI etc.)
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy our package
COPY . .

# Build our ROS 2 package
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build --symlink-install"

# Health check setup (pinging the FastAPI application)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
