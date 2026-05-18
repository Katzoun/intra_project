#!/bin/bash
# set -e

echo "=== Starting INTRA Project ==="

echo "Starting Docker Desktop..."
# Start Docker Desktop (Linux) if available
systemctl --user start docker-desktop >/dev/null 2>&1 || true

# Wait a bit until Docker is ready
for i in $(seq 1 20); do
    docker info >/dev/null 2>&1 && break
    sleep 1
done

# Start Docker containers
echo "Starting Docker containers..."
docker compose up -d

# wait for PostgreSQL
echo "Waiting for PostgreSQL..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if docker exec intra-postgresql pg_isready -U postgres > /dev/null 2>&1; then
        echo "PostgreSQL is ready"
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: PostgreSQL did not start in time"
    exit 1
fi


# Activating environment
echo "Activating environment..."
source intra_activate.sh

# Check and run database migrations if needed
echo "Checking database migrations..."
python3 migrations/check_and_migrate.py
if [ $? -ne 0 ]; then
    echo "ERROR: Database migration check/execution failed"
    sleep 15
    exit 1
fi

# Starting PhoXiControl
echo "Starting PhoXiControl..."
PHOXI_BIN="${PHOXI_CONTROL_PATH:-/opt/Photoneo/PhoXiControl-1.15.0}/bin/PhoXiControl"
if pgrep -xi "phoxicontrol" > /dev/null 2>&1; then
    echo "PhoXiControl is already running"
else
    if [ -x "$PHOXI_BIN" ]; then
        "$PHOXI_BIN" &
        sleep 3
        echo "PhoXiControl started"
    else
        echo "ERROR: PhoXiControl not found at $PHOXI_BIN"
        sleep 3
        exit 1
    fi
fi

# Starting ROS2 services
echo "Starting ROS2 services..."


# ros2 launch intra_launch_pkg intra.launch.py
ros2 launch intra_launch_pkg intrafull.launch.py
