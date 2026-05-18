from dotenv import load_dotenv
import sys
import os

if not load_dotenv(".env"):
    sys.exit("Error: .env file missing or no variables loaded.")


APP_TITLE = "INTRA Project"
APP_SUBTITLE = "Integrated robotic application"
APP_TIMEZONE = 'Europe/Prague'

INACTIVITY_TIMEOUT_SECONDS = 3600  # 1 hour

# PostgreSQL Configuration
POSTGRES_USER= os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD= os.environ["POSTGRES_PASSWORD"]
POSTGRES_DB= os.environ["POSTGRES_DB"]
POSTGRES_HOST= os.environ["POSTGRES_HOST"]
POSTGRES_PORT= os.environ["POSTGRES_PORT"]

DB_ECHO = False # Set to False in real deployment, True for debugging

assert POSTGRES_USER
assert POSTGRES_PASSWORD
assert POSTGRES_DB
assert POSTGRES_HOST
assert POSTGRES_PORT

# DB ROLES PASSWORDS
DB_OWNER_PASSWORD= os.environ["DB_OWNER_PASSWORD"]
DB_USER_PASSWORD= os.environ["DB_USER_PASSWORD"]
DB_READONLY_PASSWORD= os.environ["DB_READONLY_PASSWORD"]
assert DB_OWNER_PASSWORD
assert DB_USER_PASSWORD
assert DB_READONLY_PASSWORD

POSTGRES_DB_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


# pgAdmin Configuration
PGADMIN_EMAIL= os.environ["PGADMIN_EMAIL"]
PGADMIN_PASSWORD= os.environ["PGADMIN_PASSWORD"]
assert PGADMIN_EMAIL
assert PGADMIN_PASSWORD

# Robot Controller Configuration
ROBOT_USERNAME= os.environ["ROBOT_USERNAME"]
ROBOT_PASSWORD= os.environ["ROBOT_PASSWORD"]
assert ROBOT_USERNAME
assert ROBOT_PASSWORD


# ui
UI_STORAGE_SECRET = os.environ["UI_STORAGE_SECRET"]
assert UI_STORAGE_SECRET
JWT_SECRET = os.environ["JWT_SECRET"]
assert JWT_SECRET

# Initial Admin Accessor Configuration
INITIAL_ADMIN_LOGIN= os.environ["INITIAL_ADMIN_LOGIN"]
INITIAL_ADMIN_PASSWORD= os.environ["INITIAL_ADMIN_PASSWORD"]
assert INITIAL_ADMIN_LOGIN
assert INITIAL_ADMIN_PASSWORD

INITIAL_OPER_LOGIN= os.environ["INITIAL_OPER_LOGIN"]
INITIAL_OPER_PASSWORD= os.environ["INITIAL_OPER_PASSWORD"]
assert INITIAL_OPER_LOGIN
assert INITIAL_OPER_PASSWORD


# Initial System Accessor Configuration
INITIAL_SYSTEM_LOGIN= os.environ["INITIAL_SYSTEM_LOGIN"]
INITIAL_SYSTEM_PASSWORD= os.environ["INITIAL_SYSTEM_PASSWORD"]
assert INITIAL_SYSTEM_LOGIN
assert INITIAL_SYSTEM_PASSWORD

# Configuration YAML paths
CONFIG_DIR = 'config'
ROBOT_CONFIG_YAML = os.path.join(CONFIG_DIR, 'robot_config.yaml')
CAMERA_CONFIG_YAML = os.path.join(CONFIG_DIR, 'camera_config.yaml')
COORDINATOR_CONFIG_YAML = os.path.join(CONFIG_DIR, 'coordinator_config.yaml')
VISION_PROCESSING_CONFIG_YAML = os.path.join(CONFIG_DIR, 'vision_processing_config.yaml')
TOOLS_CONFIG_YAML = os.path.join(CONFIG_DIR, 'tools.yaml')
TOOL_CONTROLLER_CONFIG_YAML = os.path.join(CONFIG_DIR, 'tool_config.yaml')
TOOL_MESHES_DIR = os.path.join(CONFIG_DIR, 'tool_meshes')
MOTION_PLANNING_CONFIG_YAML = os.path.join(CONFIG_DIR, 'motion_planning_config.yaml')
MOTION_PLANNING_POSES_YAML = os.path.join(CONFIG_DIR, 'motion_planning_poses.yaml')
ROBOT_SHADOW_PATH = os.path.join("src", "robotarm_pkg", "urdf", "robotarmwebpreview.urdf")

HUGGINGFACE_API_KEY= os.environ["HUGGINGFACE_API_KEY"]
assert HUGGINGFACE_API_KEY