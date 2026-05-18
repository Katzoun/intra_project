from dataclasses import dataclass, field, fields, asdict
from typing import Dict, Any, List, Tuple
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.parameter import Parameter
from core_pkg.settings import COORDINATOR_CONFIG_YAML
import yaml
import os

@dataclass(frozen=True)
class CoordinatorParametersKeys:

    WAIT_FOR_USER_INPUT = 'wait_for_user_input'
    ENABLE_RVIZ_TOOL_SWAP = 'enable_rviz_tool_swap'


def _load_coordinator_defaults() -> Dict[str, Any]:
    """Load coordinator defaults from YAML. Raises if file is missing."""
    try: 
        with open(COORDINATOR_CONFIG_YAML, 'r') as f:
            data = yaml.safe_load(f)
        return data['coordinator_parameters']
    except Exception as e:
        raise ValueError(e)


_DEFAULTS = _load_coordinator_defaults()


@dataclass
class CoordinatorParameters:

    wait_for_user_input: bool = _DEFAULTS[CoordinatorParametersKeys.WAIT_FOR_USER_INPUT]
    enable_rviz_tool_swap: bool = _DEFAULTS[CoordinatorParametersKeys.ENABLE_RVIZ_TOOL_SWAP]


    def to_ros_params(self) -> List[Tuple[str, Any, ParameterDescriptor]]:
        """Convert to ROS2 parameter list with descriptors for declare_parameters"""
        return [
       
            
            # Wait for user input
            (CoordinatorParametersKeys.WAIT_FOR_USER_INPUT, self.wait_for_user_input, ParameterDescriptor(
                description='Wait for user input before proceeding',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            # Enable RViz tool swap
            (CoordinatorParametersKeys.ENABLE_RVIZ_TOOL_SWAP, self.enable_rviz_tool_swap, ParameterDescriptor(
                description='Send tool swap service calls to tool controller node for RViz visualization',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
        ]

    def to_ros_params_dict(self) -> Dict[str, Any]:
        """Convert to simple dictionary (for backward compatibility)"""
        param_tuples = self.to_ros_params()
        return {name: value for name, value, _ in param_tuples}

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to flat dict keyed by CoordinatorParametersKeys values."""
        return {
            CoordinatorParametersKeys.WAIT_FOR_USER_INPUT: self.wait_for_user_input,
            CoordinatorParametersKeys.ENABLE_RVIZ_TOOL_SWAP: self.enable_rviz_tool_swap,
        }

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> 'CoordinatorParameters':
        """Create instance from flat dict keyed by CoordinatorParametersKeys values."""
        return cls(
            wait_for_user_input=data[CoordinatorParametersKeys.WAIT_FOR_USER_INPUT],
            enable_rviz_tool_swap=data[CoordinatorParametersKeys.ENABLE_RVIZ_TOOL_SWAP],
        )

    def save_yaml(self, path: str) -> None:
        """Save parameters to a YAML file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump({'coordinator_parameters': self.to_flat_dict()}, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load_yaml(cls, path: str) -> 'CoordinatorParameters':
        """Load parameters from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_flat_dict(data.get('coordinator_parameters', {}))