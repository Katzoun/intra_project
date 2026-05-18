# INTRA - Integrated Robotic Application

<p align="center">
  <img src="docs/system_concept.jpg" width="800">
</p>

**INTRA** is a modular ROS2 application for rapid prototyping of advanced robotic technology processes. It provides a unified architecture that enables quick proof-of-concept development of applications combining 3D vision, custom perception algorithms, motion planning, and robotic manipulation.

The application is designed to be hardware-agnostic at its core, with the current reference implementation integrating a **Photoneo 3D camera**, an **ABB robot arm**.

---

## Screenshots

<table>
  <tr>
    <td><img src="docs/dashboard_page.png" width="300"><br><em>Dashboard - system overview UI</em></td>
    <td><img src="docs/operations_page.jpg" width="300"><br><em>Operations - operation triggers UI</em></td>
    <td><img src="docs/systemcontrol.jpg" width="300"><br><em>System Control - node lifecycle management UI</em></td>
  </tr>
  <tr>
    <td><img src="docs/config_page.png" width="300"><br><em>Configuration - node parameter editing UI</em></td>
    <td><img src="docs/robot_page.jpg" width="300"><br><em>Robot - live robot visualization UI</em></td>
    <td></td>
  </tr>
</table>

---

## Hardware Setup

<p align="center">
  <img src="docs/workstationvirtual.png" width="700"><br>
  <em>Workspace visualisation</em>
</p>

---

## Requirements

| Component | Version |
|-----------|---------|
| OS | Ubuntu 22.04 (Jammy Jellyfish) |
| Python | 3.10 |
| ROS2 | Humble Hawksbill |
| MoveIt2 | Humble |
| PhoXiControl | 1.15.0 |
| Docker & Docker Compose | latest |

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Katzoun/intra_project.git
   cd intra_project
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   bash intra_init.sh
   ```

3. **Activate the environment** (sources ROS2 + venv + workspace overlay):
   ```bash
   source intra_activate.sh
   ```

4. **Build all packages:**

   > **Important:** Do not use bare `colcon build`. Always use the custom build script.

   ```bash
   bash intra_build.sh
   ```

5. **Configure environment variables:**

   Copy the template and fill in your values (database credentials, HuggingFace API key for SAM 3, etc.):

   ```bash
   cp example.env .env
   ```

---

## Quick Start

Start the full system (Docker database + PhoXiControl + ROS2 nodes):

```bash
bash intra_start.sh
```

The web interface is available at **http://localhost:8080**.

---

## Architecture Overview

INTRA is built bottom-up from reusable building blocks. All node communication uses ROS2 topics, services and actions.

<p align="center">
  <img src="docs/syspackages.jpg" width="800">
  <em>INTRA system package overview</em>
</p>

### INTRANode — The Foundation

Every application node inherits from **`INTRANode`** (`core_pkg`), which provides:

<p align="center">
  <img src="docs/intranode_abstract_scheme.jpg" width="500"><br>
  <em>Abstract INTRANode</em>
</p>

- **Lifecycle state machine** — thread-safe transitions managed via `python-statemachine`:

  <p align="center">
    <img src="docs/state_machine.jpg" width="800">
    <em>INTRANode lifecycle state machine</em>
  </p>


- **`@handle_operation_errors`** decorator — automatic error handling and state transitions in service callbacks
- **Client factory methods** — pre-built service/action clients to communicate with other nodes
- **Parameter management** — declare, get, set ROS2 parameters with YAML serialization
- **`SystemConstants`** — single source of truth for all ROS2 topic, service, and action names, operation phases, and node state enums

Adding a new node to the system requires only inheriting from `INTRANode` and implementing the application logic — all infrastructure is provided out of the box.

<p align="center">
  <img src="docs/classdiagram.jpg" width="800"><br>
  <em>INTRANode class hierarchy</em>
</p>

### MoveIt2 Integration

The `motion_planning` node wraps MoveIt2's `move_group` services, while `tool_controller` keeps the planning scene (attached collision geometries, tool transforms) in sync with the active gripper.

<p align="center">
  <img src="docs/moveitintegration.jpg" width="800"><br>
  <em>INTRA <--> MoveIt2 integration</em>
</p>

### Motion Planning

Motion planning services within INTRA are provided by the `motion_planning_node`, which exposes a uniform planning interface to the rest of the system and translates requests into MoveIt2 `move_group` calls.

<p align="center">
  <img src="docs/motion_planning_scheme.jpg" width="800"><br>
  <em>motion_planning_node - planning service internals</em>
</p>

### Scene Collision Representation

The MoveIt planning scene is composed from two independent sources of collision geometry:

- **Static geometry** — known fixtures of the workcell (table, frame, mounts) loaded from the workcell URDF.
- **Dynamic geometry** — an **Octomap** built online from the 3D sensor, capturing everything not described by the static model (objects on the table)


<table>
  <tr>
    <td><img src="docs/workspace_nocolision.jpg" width="220"><br><em>No collision geometry</em></td>
    <td><img src="docs/workspace_static.jpg" width="220"><br><em>Static geometry only</em></td>
    <td><img src="docs/workspace_octomap.jpg" width="220"><br><em>Dynamic geometry (Octomap)</em></td>
    <td><img src="docs/workspace_octomapstatic.jpg" width="220"><br><em>Fused static + dynamic</em></td>
  </tr>
</table>

#### Motion Planning Example

Avoiding a dynamic obstacle that appears in the robot's workspace - the planner re-routes around the obstacle observed via the Octomap.

<table>
  <tr>
    <td><img src="docs/stage1.jpg" width="150"><br></td>
    <td><img src="docs/stage2.jpg" width="150"><br></td>
    <td><img src="docs/stage3.jpg" width="150"><br></td>
    <td><img src="docs/stage4.jpg" width="150"><br></td>
    <td><img src="docs/stage5.jpg" width="150"><br></td>
    <td><img src="docs/stage6.jpg" width="150"><br></td>
  </tr>
</table>

### Operation Pipeline

The **coordinator node** is the central orchestrator. A typical operation follows this flow:

```
Frontend (user clicks START)
    │
    ▼  PerformOperation action goal
Coordinator
    │
    ├─► Phase: SCANNING
    │       └─► ScanAcquisitionSrv → camera_controller → Point Cloud
    .
    .
    .
    ├─► Custom user defined data processing
    .
    .
    .
    │
    ├─► Phase: EXECUTING_MOTION
    │       └─► ExecutePoseArray action → robot_controller → ABB RWS
    │
    └─► Phase: COMPLETED
            └─► Result returned to frontend
```

<p align="center">
  <img src="docs/op1_pipeline.jpg" width="600"><br>
  <em>Demo operation 1 - frame-by-frame capture of the executed pipeline</em>
</p>

<p align="center">
  <img src="docs/op2_pipeline_grid.jpg" width="600"><br>
  <em>Demo operation 2 - frame-by-frame capture of the executed pipeline</em>
</p>

---

## Packages

### interface_pkg

CMake package defining all custom ROS2 interfaces (`PerformOperation.action`, `ExecutePoseArray.action`, `ProcessVisionSrv.srv`, `ScanAcquisitionSrv.srv`, `RobotRequestSrv.srv`, `GraspResult.msg`, etc.).

### core_pkg

Foundational package: `INTRANode` base class with lifecycle state machine, `SystemConstants` (single source of truth for all ROS2 names), database models (SQLAlchemy ORM with role-based access control), configuration loader, and custom exceptions.

### intranodes_pkg

Application nodes:

| Node | Description |
|------|-------------|
| `camera_controller` | 3D camera acquisition via Harvester/GenICam |
| `vision_processing` | vision processing methods |
| `robot_controller` | ABB robot control via RWS protocol |
| `coordinator_node` | Central orchestrator driving the operation pipeline |
| `tool_controller` | Gripper/tool definitions and MoveIt collision management |
| `motion_planning` | MoveIt2 motion planning integration |

Also includes supporting modules: `robot_controller_interface.py` (low-level RWS), `vision_helpers.py` (RANSAC, grasp estimation), and per-node `parameters/` dataclasses with YAML serialization.

#### Custom hardware drivers

- **ABB RWS driver** (`robot_controller_interface.py`) — from-scratch implementation of ABB's Robot Web Services REST API plus a DIPC channel for low-latency messaging. Built because no publicly available driver for ABB **OmniCore** controllers existed at the time. Wrapped by the `robot_controller` node.

  <p align="center">
    <img src="docs/robot_controller_node_scheme.jpg" width="700"><br>
    <em>robot_controller node - RWS driver internals</em>
  </p>

- **Photoneo / GenICam driver** — `harvesters`-based (GenTL consumer) driver in the `camera_controller` node.

  <p align="center">
    <img src="docs/camera_controller_scheme.jpg" width="700"><br>
    <em>camera_controller node - GenICam driver internals</em>
  </p>

### user_interface_pkg

NiceGUI web interface with JWT authentication. Pages: Dashboard, Operations (real-time feedback with images and point clouds), Robot visualization, Tool Controller, System Control (node lifecycle), Configuration (live parameter editing + YAML), User Management.

### intra_launch_pkg

Launch files: `intrafull.launch.py` (full system with MoveIt + RViz), `intramoveit.launch.py` (MoveIt only), `intra.launch.py` (nodes only).

### Robot & Workcell

`robotarm_pkg` (URDF/meshes), `workcell_pkg` (scene URDF + collision objects), `robotarm_moveit_pkg` (MoveIt Setup Assistant config).

---

## Configuration

All config files are in the `config/` directory:

| File | Description |
|------|-------------|
| `camera_config.yaml` | Photoneo device ID, output formats, capture settings, calibration transform etc...|
| `robot_config.yaml` | Robot connection (IP, port, credentials), keepalive, joint state publishing, etc... |
| `coordinator_config.yaml` | Operation behavior |
| `vision_processing_config.yaml` | Vision pipeline settings |
| `tool_config.yaml` | Tool controller settings |
| `tools.yaml` | Gripper definitions, collision geometries |

Parameters can also be edited at runtime through the web interface (**Configuration** page).

---

## Database

PostgreSQL 16 in Docker (`docker-compose.yml`) with Alembic migrations. Stores user accounts and roles with permission flags. Migrations run automatically on first launch - no manual steps required.

---

## Project Structure

```
master_project/
├── intra_init.sh / intra_activate.sh / intra_build.sh / intra_start.sh
├── docker-compose.yml                 # PostgreSQL + pgAdmin
├── requirements.txt
├── .env                               # Credentials & API keys
│
├── config/                            # YAML configuration for all nodes
│
├── src/
│   ├── interface_pkg/                 # Custom ROS2 msg/srv/action (CMake)
│   ├── core_pkg/                      # Base classes, state machine, DB models
│   ├── intranodes_pkg/                # Application nodes + parameters
│   ├── user_interface_pkg/                  # NiceGUI web interface + pages
│   ├── intra_launch_pkg/              # Launch files
│   ├── robotarm_pkg/                  # Robot URDF & meshes
│   ├── workcell_pkg/                  # Workcell URDF & collision objects
│   └── robotarm_moveit_pkg/           # MoveIt configuration
│
├── migrations/                        # Alembic DB migrations
├── calibration_scripts/               # Robot-camera calibration
├── experimental/                      # Test scripts & notebooks
└── docs/                              # Screenshots
```

---

## Key Dependencies

| Category | Libraries |
|----------|-----------|
| Vision & ML | `torch`, `transformers` (SAM 3), `opencv-python`, `open3d`, `scikit-learn`, `scipy` |
| Web UI | `nicegui`, `fastapi` |
| Database | `sqlalchemy`, `psycopg2-binary`, `alembic`, `pydantic` |
| Camera | `harvesters` (GenICam/GigE Vision) |
| Auth | `bcrypt`, `pyjwt` |
| ROS2 | `rclpy`, MoveIt2, `python-statemachine` |

---

## Tests

Unit tests cover the lifecycle state machine, motion-planning helpers, vision processing math, and auth validators.

Run via colcon (the standard ROS2 way):

```bash
source intra_activate.sh
python -m colcon test --packages-select core_pkg intranodes_pkg
python -m colcon test-result --all
```

Or directly with pytest from the project root

```bash
source intra_activate.sh
python -m pytest src/core_pkg/test src/intranodes_pkg/test -v
```

> Note: `colcon` must be invoked via `python -m colcon ...` so it picks up the venv's Python interpreter - the system `colcon` uses a hard-coded `/usr/bin/python3` shebang that bypasses the activated venv.

---

## Author

**Tomáš Janoušek**  
Brno University of Technology  
Faculty of Mechanical Engineering  
Institute of Automation and Computer Science  
Supervisor: prof. Ing. Zdeněk Hadaš, Ph.D.  
Year: 2026

This project is part of a master's thesis.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
