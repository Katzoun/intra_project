from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.parameter import Parameter
from core_pkg.settings import MOTION_PLANNING_CONFIG_YAML
import yaml
import os


@dataclass(frozen=True)
class MotionPlanningParametersKeys:
    NUM_PLANNING_ATTEMPTS    = 'planning.num_attempts'
    ALLOWED_PLANNING_TIME    = 'planning.allowed_time'
    PLANNER_ID               = 'planning.planner_id'
    VELOCITY_SCALING         = 'planning.velocity_scaling'
    ACCELERATION_SCALING     = 'planning.acceleration_scaling'
    POSITION_TOLERANCE       = 'joint_space.position_tolerance'
    ORIENTATION_TOLERANCE    = 'joint_space.orientation_tolerance'
    CARTESIAN_MAX_STEP       = 'cartesian.max_step'
    CARTESIAN_JUMP_THRESHOLD = 'cartesian.jump_threshold'
    CARTESIAN_AVOID_COLLISIONS = 'cartesian.avoid_collisions'
    CARTESIAN_MIN_FRACTION   = 'cartesian.min_fraction'


def _load_defaults() -> Dict[str, Any]:
    with open(MOTION_PLANNING_CONFIG_YAML, 'r') as f:
        data = yaml.safe_load(f)
    return data['motion_planning_parameters']


_DEFAULTS = _load_defaults()


@dataclass
class MotionPlanningParameters:
    num_planning_attempts:     int   = _DEFAULTS[MotionPlanningParametersKeys.NUM_PLANNING_ATTEMPTS]
    allowed_planning_time:     float = _DEFAULTS[MotionPlanningParametersKeys.ALLOWED_PLANNING_TIME]
    planner_id:                str   = _DEFAULTS[MotionPlanningParametersKeys.PLANNER_ID]
    velocity_scaling:          float = _DEFAULTS[MotionPlanningParametersKeys.VELOCITY_SCALING]
    acceleration_scaling:      float = _DEFAULTS[MotionPlanningParametersKeys.ACCELERATION_SCALING]
    position_tolerance:        float = _DEFAULTS[MotionPlanningParametersKeys.POSITION_TOLERANCE]
    orientation_tolerance:     float = _DEFAULTS[MotionPlanningParametersKeys.ORIENTATION_TOLERANCE]
    cartesian_max_step:        float = _DEFAULTS[MotionPlanningParametersKeys.CARTESIAN_MAX_STEP]
    cartesian_jump_threshold:  float = _DEFAULTS[MotionPlanningParametersKeys.CARTESIAN_JUMP_THRESHOLD]
    cartesian_avoid_collisions: bool = _DEFAULTS[MotionPlanningParametersKeys.CARTESIAN_AVOID_COLLISIONS]
    cartesian_min_fraction:    float = _DEFAULTS[MotionPlanningParametersKeys.CARTESIAN_MIN_FRACTION]

    def to_ros_params(self) -> List[Tuple[str, Any, ParameterDescriptor]]:
        return [
            (MotionPlanningParametersKeys.NUM_PLANNING_ATTEMPTS, self.num_planning_attempts, ParameterDescriptor(
                description='Number of planning attempts for joint-space planner',
                type=Parameter.Type.INTEGER.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.ALLOWED_PLANNING_TIME, self.allowed_planning_time, ParameterDescriptor(
                description='Maximum allowed planning time in seconds',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.PLANNER_ID, self.planner_id, ParameterDescriptor(
                description='Planner ID (OMPL: RRTConnect, RRTstar, PRM, … | other: CHOMP). See MotionPlanningConstants.Planners.',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.VELOCITY_SCALING, self.velocity_scaling, ParameterDescriptor(
                description='Max velocity scaling factor [0.0–1.0] applied during planning (affects trajectory timing for visualization)',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.ACCELERATION_SCALING, self.acceleration_scaling, ParameterDescriptor(
                description='Max acceleration scaling factor [0.0–1.0] applied during planning (affects trajectory timing for visualization)',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.POSITION_TOLERANCE, self.position_tolerance, ParameterDescriptor(
                description='Position tolerance for joint-space goal constraints in metres',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.ORIENTATION_TOLERANCE, self.orientation_tolerance, ParameterDescriptor(
                description='Orientation tolerance for joint-space goal constraints in radians',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.CARTESIAN_MAX_STEP, self.cartesian_max_step, ParameterDescriptor(
                description='Max Cartesian step size in metres — controls path resolution',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.CARTESIAN_JUMP_THRESHOLD, self.cartesian_jump_threshold, ParameterDescriptor(
                description='Max allowed joint-space jump between steps (0.0 = disabled)',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.CARTESIAN_AVOID_COLLISIONS, self.cartesian_avoid_collisions, ParameterDescriptor(
                description='Enable collision checking for Cartesian paths',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (MotionPlanningParametersKeys.CARTESIAN_MIN_FRACTION, self.cartesian_min_fraction, ParameterDescriptor(
                description='Minimum fraction of path that must be reachable [0.0–1.0]',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
        ]

    def to_ros_params_dict(self) -> Dict[str, Any]:
        """Convert to simple dictionary."""
        param_tuples = self.to_ros_params()
        return {name: value for name, value, _ in param_tuples}

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to flat dict keyed by MotionPlanningParametersKeys values."""
        return {
            MotionPlanningParametersKeys.NUM_PLANNING_ATTEMPTS:      self.num_planning_attempts,
            MotionPlanningParametersKeys.ALLOWED_PLANNING_TIME:      self.allowed_planning_time,
            MotionPlanningParametersKeys.PLANNER_ID:                 self.planner_id,
            MotionPlanningParametersKeys.VELOCITY_SCALING:           self.velocity_scaling,
            MotionPlanningParametersKeys.ACCELERATION_SCALING:       self.acceleration_scaling,
            MotionPlanningParametersKeys.POSITION_TOLERANCE:         self.position_tolerance,
            MotionPlanningParametersKeys.ORIENTATION_TOLERANCE:      self.orientation_tolerance,
            MotionPlanningParametersKeys.CARTESIAN_MAX_STEP:         self.cartesian_max_step,
            MotionPlanningParametersKeys.CARTESIAN_JUMP_THRESHOLD:   self.cartesian_jump_threshold,
            MotionPlanningParametersKeys.CARTESIAN_AVOID_COLLISIONS: self.cartesian_avoid_collisions,
            MotionPlanningParametersKeys.CARTESIAN_MIN_FRACTION:     self.cartesian_min_fraction,
        }

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> 'MotionPlanningParameters':
        """Create instance from flat dict keyed by MotionPlanningParametersKeys values."""
        return cls(
            num_planning_attempts=data[MotionPlanningParametersKeys.NUM_PLANNING_ATTEMPTS],
            allowed_planning_time=data[MotionPlanningParametersKeys.ALLOWED_PLANNING_TIME],
            planner_id=data[MotionPlanningParametersKeys.PLANNER_ID],
            velocity_scaling=data[MotionPlanningParametersKeys.VELOCITY_SCALING],
            acceleration_scaling=data[MotionPlanningParametersKeys.ACCELERATION_SCALING],
            position_tolerance=data[MotionPlanningParametersKeys.POSITION_TOLERANCE],
            orientation_tolerance=data[MotionPlanningParametersKeys.ORIENTATION_TOLERANCE],
            cartesian_max_step=data[MotionPlanningParametersKeys.CARTESIAN_MAX_STEP],
            cartesian_jump_threshold=data[MotionPlanningParametersKeys.CARTESIAN_JUMP_THRESHOLD],
            cartesian_avoid_collisions=data[MotionPlanningParametersKeys.CARTESIAN_AVOID_COLLISIONS],
            cartesian_min_fraction=data[MotionPlanningParametersKeys.CARTESIAN_MIN_FRACTION],
        )

    def save_yaml(self, path: str) -> None:
        """Save parameters to a YAML file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump({'motion_planning_parameters': self.to_flat_dict()}, f,
                      default_flow_style=False, sort_keys=False)

    @classmethod
    def load_yaml(cls, path: str) -> 'MotionPlanningParameters':
        """Load parameters from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_flat_dict(data.get('motion_planning_parameters', {}))
