from dataclasses import dataclass, field, fields, asdict
from typing import Dict, Any, List, Tuple
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.parameter import Parameter
from core_pkg.settings import VISION_PROCESSING_CONFIG_YAML
import yaml
import os

@dataclass(frozen=True)
class VisionParametersKeys:

    DEBUG_IMAGE_OUTPUT = 'general.debug_image_output'
    VIZUALIZE_O3D = 'general.vizualize_o3d'
    USE_SIM_HEIGHT = 'operation1.use_sim_height'
    CAD_MODEL_PATH = 'operation2.cad_model_path'
    POSE_ESTIMATION_VOXEL_SIZE = 'operation2.pose_estimation_voxel_size'
    POSE_ESTIMATION_NB_NEIGHBORS = 'operation2.pose_estimation_nb_neighbors'

def _load_vision_defaults() -> Dict[str, Any]:
    """Load defaults from YAML. Raises if file is missing."""
    try: 
        with open(VISION_PROCESSING_CONFIG_YAML, 'r') as f:
            data = yaml.safe_load(f)
        return data['vision_processing_parameters']
    except Exception as e:
        raise ValueError(e)


_DEFAULTS = _load_vision_defaults()


@dataclass
class VisionParameters:

    debug_image_output: bool = _DEFAULTS[VisionParametersKeys.DEBUG_IMAGE_OUTPUT]
    vizualize_o3d : bool = _DEFAULTS[VisionParametersKeys.VIZUALIZE_O3D]
    use_sim_height : bool = _DEFAULTS[VisionParametersKeys.USE_SIM_HEIGHT]
    cad_model_path : str = _DEFAULTS[VisionParametersKeys.CAD_MODEL_PATH]
    pose_estimation_voxel_size : float = _DEFAULTS[VisionParametersKeys.POSE_ESTIMATION_VOXEL_SIZE]
    pose_estimation_nb_neighbors : int = _DEFAULTS[VisionParametersKeys.POSE_ESTIMATION_NB_NEIGHBORS]


    def to_ros_params(self) -> List[Tuple[str, Any, ParameterDescriptor]]:
        """Convert to ROS2 parameter list with descriptors for declare_parameters"""
        return [
       
            
            # File saving
            (VisionParametersKeys.DEBUG_IMAGE_OUTPUT, self.debug_image_output, ParameterDescriptor(
                description='Save scan data to file on disk (ply, praw, etc.)',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (VisionParametersKeys.VIZUALIZE_O3D, self.vizualize_o3d, ParameterDescriptor(
                description='Whether to show open3d visualizer with point clouds and grasps',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (VisionParametersKeys.USE_SIM_HEIGHT, self.use_sim_height, ParameterDescriptor(
                description='Whether to use simulated height data',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (VisionParametersKeys.CAD_MODEL_PATH, self.cad_model_path, ParameterDescriptor(
                description='Default path to CAD model file (.stl/.obj) for pose estimation',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (VisionParametersKeys.POSE_ESTIMATION_VOXEL_SIZE, self.pose_estimation_voxel_size, ParameterDescriptor(
                description='Default voxel size in mm for pose estimation downsampling',
                type=Parameter.Type.DOUBLE.value,
                read_only=False
            )),
            (VisionParametersKeys.POSE_ESTIMATION_NB_NEIGHBORS, self.pose_estimation_nb_neighbors, ParameterDescriptor(
                description='Number of neighbors for outlier removal in pose estimation',
                type=Parameter.Type.INTEGER.value,
                read_only=False
            )),

        ]

    def to_ros_params_dict(self) -> Dict[str, Any]:
        """Convert to simple dictionary (for backward compatibility)"""
        param_tuples = self.to_ros_params()
        return {name: value for name, value, _ in param_tuples}

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to flat dict keyed by VisionParametersKeys values."""
        return {
    
            VisionParametersKeys.DEBUG_IMAGE_OUTPUT: self.debug_image_output,
            VisionParametersKeys.VIZUALIZE_O3D: self.vizualize_o3d,
            VisionParametersKeys.USE_SIM_HEIGHT: self.use_sim_height,
            VisionParametersKeys.CAD_MODEL_PATH: self.cad_model_path,
            VisionParametersKeys.POSE_ESTIMATION_VOXEL_SIZE: self.pose_estimation_voxel_size,
            VisionParametersKeys.POSE_ESTIMATION_NB_NEIGHBORS: self.pose_estimation_nb_neighbors,
        }

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> 'VisionParameters':
        """Create instance from flat dict keyed by VisionParametersKeys values."""
        return cls(
            debug_image_output=data[VisionParametersKeys.DEBUG_IMAGE_OUTPUT],
            vizualize_o3d=data[VisionParametersKeys.VIZUALIZE_O3D],
            use_sim_height=data[VisionParametersKeys.USE_SIM_HEIGHT],
            cad_model_path=data[VisionParametersKeys.CAD_MODEL_PATH],
            pose_estimation_voxel_size=data[VisionParametersKeys.POSE_ESTIMATION_VOXEL_SIZE],
            pose_estimation_nb_neighbors=data[VisionParametersKeys.POSE_ESTIMATION_NB_NEIGHBORS],
        )

    def save_yaml(self, path: str) -> None:
        """Save parameters to a YAML file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump({'vision_processing_parameters': self.to_flat_dict()}, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load_yaml(cls, path: str) -> 'VisionParameters':
        """Load parameters from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_flat_dict(data.get('vision_processing_parameters', {}))