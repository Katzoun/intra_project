from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.parameter import Parameter
from core_pkg.settings import TOOL_CONTROLLER_CONFIG_YAML
import yaml
import os


@dataclass(frozen=True)
class ToolControllerParametersKeys:
    FLANGE_LINK = 'scene.flange_link'
    PUBLISH_COUNT = 'scene.publish_count'
    PUBLISH_DELAY = 'scene.publish_delay'


def _load_tool_controller_defaults() -> Dict[str, Any]:
    """Load tool controller defaults from YAML. Raises if file is missing."""
    try:
        with open(TOOL_CONTROLLER_CONFIG_YAML, 'r') as f:
            data = yaml.safe_load(f)
        return data['tool_controller_parameters']
    except Exception as e:
        raise ValueError(e)


_DEFAULTS = _load_tool_controller_defaults()


@dataclass
class ToolControllerParameters:
    flange_link: str = _DEFAULTS[ToolControllerParametersKeys.FLANGE_LINK]
    publish_count: int = _DEFAULTS[ToolControllerParametersKeys.PUBLISH_COUNT]
    publish_delay: float = _DEFAULTS[ToolControllerParametersKeys.PUBLISH_DELAY]

    def to_ros_params(self) -> List[Tuple[str, Any, ParameterDescriptor]]:
        """Convert to ROS2 parameter list with descriptors for declare_parameters"""
        return [
            (ToolControllerParametersKeys.FLANGE_LINK, self.flange_link, ParameterDescriptor(
                description='Robot flange link name for collision attachment',
                type=Parameter.Type.STRING.value,
                read_only=False,
            )),
            (ToolControllerParametersKeys.PUBLISH_COUNT, self.publish_count, ParameterDescriptor(
                description='Number of times to publish each PlanningScene diff for reliability',
                type=Parameter.Type.INTEGER.value,
                read_only=False,
            )),
            (ToolControllerParametersKeys.PUBLISH_DELAY, self.publish_delay, ParameterDescriptor(
                description='Delay in seconds between repeated PlanningScene publishes',
                type=Parameter.Type.DOUBLE.value,
                read_only=False,
            )),
        ]

    def to_ros_params_dict(self) -> Dict[str, Any]:
        """Convert to simple dictionary"""
        param_tuples = self.to_ros_params()
        return {name: value for name, value, _ in param_tuples}

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to flat dict keyed by ToolControllerParametersKeys values."""
        return {
            ToolControllerParametersKeys.FLANGE_LINK: self.flange_link,
            ToolControllerParametersKeys.PUBLISH_COUNT: self.publish_count,
            ToolControllerParametersKeys.PUBLISH_DELAY: self.publish_delay,
        }

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> 'ToolControllerParameters':
        """Create instance from flat dict keyed by ToolControllerParametersKeys values."""
        return cls(
            flange_link=data[ToolControllerParametersKeys.FLANGE_LINK],
            publish_count=data[ToolControllerParametersKeys.PUBLISH_COUNT],
            publish_delay=data[ToolControllerParametersKeys.PUBLISH_DELAY],
        )

    def save_yaml(self, path: str) -> None:
        """Save parameters to a YAML file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump({'tool_controller_parameters': self.to_flat_dict()}, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load_yaml(cls, path: str) -> 'ToolControllerParameters':
        """Load parameters from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_flat_dict(data.get('tool_controller_parameters', {}))
