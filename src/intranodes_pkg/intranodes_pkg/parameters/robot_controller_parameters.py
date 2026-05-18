from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.parameter import Parameter
from core_pkg.settings import ROBOT_CONFIG_YAML
import yaml
import os

@dataclass(frozen=True)
class RobotParametersKeys:
    IP_ADDRESS = 'connection.ip_address'
    PORT = 'connection.port'
    USERNAME = 'connection.username'
    PASSWORD = 'connection.password'
    SEND_KEEPALIVE = 'utility.send_keepalive'
    KEEPALIVE_INTERVAL = 'utility.keepalive_interval'
    SEND_JOINT_STATES = 'utility.send_joint_states'
    JOINT_STATES_HZ = 'utility.joint_states_hz'
    DIPC_RETRY_MAX = 'dipc.retry_max'
    DIPC_RETRY_DELAY_S = 'dipc.retry_delay_s'


def _load_robot_defaults() -> Dict[str, Any]:
    """Load robot defaults from YAML. Raises if file is missing."""
    with open(ROBOT_CONFIG_YAML, 'r') as f:
        data = yaml.safe_load(f)
    return data['robot_parameters']

_DEFAULTS = _load_robot_defaults()


@dataclass
class RobotParameters:
    # Connection parameters
    ip_address: str = _DEFAULTS[RobotParametersKeys.IP_ADDRESS]
    port: int = _DEFAULTS[RobotParametersKeys.PORT]
    username: str = _DEFAULTS[RobotParametersKeys.USERNAME]
    password: str = _DEFAULTS[RobotParametersKeys.PASSWORD]

    # utility
    send_keepalive: bool = _DEFAULTS[RobotParametersKeys.SEND_KEEPALIVE]
    keepalive_interval: float = _DEFAULTS[RobotParametersKeys.KEEPALIVE_INTERVAL]
    send_joint_states: bool = _DEFAULTS[RobotParametersKeys.SEND_JOINT_STATES]
    joint_states_hz: float = _DEFAULTS[RobotParametersKeys.JOINT_STATES_HZ]

    # DIPC
    dipc_retry_max: int = _DEFAULTS[RobotParametersKeys.DIPC_RETRY_MAX]
    dipc_retry_delay_s: float = _DEFAULTS[RobotParametersKeys.DIPC_RETRY_DELAY_S]

    def to_ros_params(self) -> List[Tuple[str, Any, ParameterDescriptor]]:
        """Convert to ROS2 parameter list with descriptors for declare_parameters"""
        return [
            
            # Connection parameters
            (RobotParametersKeys.IP_ADDRESS, self.ip_address, ParameterDescriptor(
                description='Robot controller IP address',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (RobotParametersKeys.PORT, self.port, ParameterDescriptor(
                description='Robot controller port (443 for real robot, 80 for simulation)',
                type=Parameter.Type.INTEGER.value,
                read_only=False
            )),
            (RobotParametersKeys.USERNAME, self.username, ParameterDescriptor(
                description='Robot controller username for authentication',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (RobotParametersKeys.PASSWORD, self.password, ParameterDescriptor(
                description='Robot controller password for authentication',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            
            # Utility parameters
            (RobotParametersKeys.SEND_KEEPALIVE, self.send_keepalive, ParameterDescriptor(
                description='Enable keepalive messages to maintain connection',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (RobotParametersKeys.KEEPALIVE_INTERVAL, self.keepalive_interval, ParameterDescriptor(
                description='Keepalive message interval in seconds',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (RobotParametersKeys.SEND_JOINT_STATES, self.send_joint_states, ParameterDescriptor(
                description='Enable joint states publishing',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (RobotParametersKeys.JOINT_STATES_HZ, self.joint_states_hz, ParameterDescriptor(
                description='Joint states publishing frequency in Hz',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (RobotParametersKeys.DIPC_RETRY_MAX, self.dipc_retry_max, ParameterDescriptor(
                description='Maximum number of retries when DIPC queue is full (status 500)',
                type=Parameter.Type.INTEGER.value,
                read_only=False
            )),
            (RobotParametersKeys.DIPC_RETRY_DELAY_S, self.dipc_retry_delay_s, ParameterDescriptor(
                description='Delay in seconds between DIPC retries',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
        ]

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to flat dict keyed by RobotParametersKeys values."""
        return {
            RobotParametersKeys.IP_ADDRESS: self.ip_address,
            RobotParametersKeys.PORT: self.port,
            RobotParametersKeys.USERNAME: self.username,
            RobotParametersKeys.PASSWORD: self.password,
            RobotParametersKeys.SEND_KEEPALIVE: self.send_keepalive,
            RobotParametersKeys.KEEPALIVE_INTERVAL: self.keepalive_interval,
            RobotParametersKeys.SEND_JOINT_STATES: self.send_joint_states,
            RobotParametersKeys.JOINT_STATES_HZ: self.joint_states_hz,
            RobotParametersKeys.DIPC_RETRY_MAX: self.dipc_retry_max,
            RobotParametersKeys.DIPC_RETRY_DELAY_S: self.dipc_retry_delay_s,
        }

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> 'RobotParameters':
        """Create instance from flat dict keyed by RobotParametersKeys values."""
        return cls(
            ip_address=data[RobotParametersKeys.IP_ADDRESS],
            port=data[RobotParametersKeys.PORT],
            username=data[RobotParametersKeys.USERNAME],
            password=data[RobotParametersKeys.PASSWORD],
            send_keepalive=data[RobotParametersKeys.SEND_KEEPALIVE],
            keepalive_interval=data[RobotParametersKeys.KEEPALIVE_INTERVAL],
            send_joint_states=data[RobotParametersKeys.SEND_JOINT_STATES],
            joint_states_hz=data[RobotParametersKeys.JOINT_STATES_HZ],
            dipc_retry_max=data[RobotParametersKeys.DIPC_RETRY_MAX],
            dipc_retry_delay_s=data[RobotParametersKeys.DIPC_RETRY_DELAY_S],
        )

    def save_yaml(self, path: str) -> None:
        """Save parameters to a YAML file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump({'robot_parameters': self.to_flat_dict()}, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load_yaml(cls, path: str) -> 'RobotParameters':
        """Load parameters from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_flat_dict(data.get('robot_parameters', {}))
