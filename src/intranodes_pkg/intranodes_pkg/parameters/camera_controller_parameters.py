from dataclasses import dataclass, field, fields, asdict
from typing import Dict, Any, List, Tuple
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.parameter import Parameter
from core_pkg.settings import CAMERA_CONFIG_YAML
import yaml
import os

@dataclass(frozen=True)
class CameraControllerParametersKeys:
    DEVICE_ID = 'connection.device_id'
    OUTPUT_DIRECTORY = 'output.directory'
    IMAGE_FORMAT = 'output.image_format'
    POINT_CLOUD_FORMAT = 'output.point_cloud_format'
    SAVE_MESH = 'output.save_mesh'
    SAVE_DEPTH_MAP = 'output.save_depth_map'
    SAVE_POINT_CLOUD = 'output.save_point_cloud'
    SAVE_NORMAL_MAP = 'output.save_normal_map'
    TRIGGER_MODE = 'capture.trigger_mode'
    AMBIENT_LIGHT_SUPPRESSION = 'capture.ambient_light_suppression'
    CODING_STRATEGY = 'capture.coding_strategy'
    SEND_TEXTURE = 'point_cloud.send_texture'
    SEND_POINT_CLOUD = 'point_cloud.send_point_cloud'
    SEND_NORMAL_MAP = 'point_cloud.send_normal_map'
    SEND_DEPTH_MAP = 'point_cloud.send_depth_map'
    SEND_CONFIDENCE_MAP = 'point_cloud.send_confidence_map'
    INTERREFLECTIONS_FILTERING = 'processing.interreflections_filtering'
    INTERREFLECTION_FILTER_STRENGTH = 'processing.interreflection_filter_strength'
    MAX_INACCURACY = 'processing.max_inaccuracy'
    COORDINATE_SPACE = 'coordinate_space.coordinate_space'
    TRANSFORMATION_SPACE_SELECTOR = 'coordinate_space.transformation_space_selector'

    PUBLISH_TOPICS = 'output.publish_topics'
    SAVE_TO_FILE = 'output.save_to_file'
    TF_FRAME_ID = 'tf.frame_id'
    USE_TRANSFORM = 'tf.use_transform'
    DEFAULT_TRANSFORM = 'tf.default_transform'

def _load_camera_defaults() -> Dict[str, Any]:
    """Load camera defaults from YAML. Raises if file is missing."""
    try: 
        with open(CAMERA_CONFIG_YAML, 'r') as f:
            data = yaml.safe_load(f)
        return data['camera_controller_parameters']
    except Exception as e:
        raise ValueError(e)


_DEFAULTS = _load_camera_defaults()


@dataclass
class CameraControllerParameters:
    # Connection
    device_id: str = _DEFAULTS[CameraControllerParametersKeys.DEVICE_ID]

    # Output
    output_directory: str = _DEFAULTS[CameraControllerParametersKeys.OUTPUT_DIRECTORY]
    image_format: str = _DEFAULTS[CameraControllerParametersKeys.IMAGE_FORMAT]
    point_cloud_format: str = _DEFAULTS[CameraControllerParametersKeys.POINT_CLOUD_FORMAT]
    save_mesh: bool = _DEFAULTS[CameraControllerParametersKeys.SAVE_MESH]
    save_depth_map: bool = _DEFAULTS[CameraControllerParametersKeys.SAVE_DEPTH_MAP]
    save_point_cloud: bool = _DEFAULTS[CameraControllerParametersKeys.SAVE_POINT_CLOUD]
    save_normal_map: bool = _DEFAULTS[CameraControllerParametersKeys.SAVE_NORMAL_MAP]

    # Capture
    trigger_mode: str = _DEFAULTS[CameraControllerParametersKeys.TRIGGER_MODE]
    ambient_light_suppression: bool = _DEFAULTS[CameraControllerParametersKeys.AMBIENT_LIGHT_SUPPRESSION]
    coding_strategy: str = _DEFAULTS[CameraControllerParametersKeys.CODING_STRATEGY]

    # Point Cloud Settings
    send_texture: bool = _DEFAULTS[CameraControllerParametersKeys.SEND_TEXTURE]
    send_point_cloud: bool = _DEFAULTS[CameraControllerParametersKeys.SEND_POINT_CLOUD]
    send_normal_map: bool = _DEFAULTS[CameraControllerParametersKeys.SEND_NORMAL_MAP]
    send_depth_map: bool = _DEFAULTS[CameraControllerParametersKeys.SEND_DEPTH_MAP]
    send_confidence_map: bool = _DEFAULTS[CameraControllerParametersKeys.SEND_CONFIDENCE_MAP]

    # Processing
    interreflections_filtering: bool = _DEFAULTS[CameraControllerParametersKeys.INTERREFLECTIONS_FILTERING]
    interreflection_filter_strength: float = _DEFAULTS[CameraControllerParametersKeys.INTERREFLECTION_FILTER_STRENGTH]
    max_inaccuracy: float = _DEFAULTS[CameraControllerParametersKeys.MAX_INACCURACY]

    # Coordinate Space
    coordinate_space: str = _DEFAULTS[CameraControllerParametersKeys.COORDINATE_SPACE]
    transformation_space_selector: str = _DEFAULTS[CameraControllerParametersKeys.TRANSFORMATION_SPACE_SELECTOR]

    # transforms
    use_transform: bool = _DEFAULTS[CameraControllerParametersKeys.USE_TRANSFORM]
    tf_frame_id  : str = _DEFAULTS[CameraControllerParametersKeys.TF_FRAME_ID]
    default_transform: List[float] = field(default_factory=lambda: list(_DEFAULTS[CameraControllerParametersKeys.DEFAULT_TRANSFORM]))
    # Topic publishing
    publish_topics: bool = _DEFAULTS[CameraControllerParametersKeys.PUBLISH_TOPICS]
    # File saving
    save_to_file: bool = _DEFAULTS[CameraControllerParametersKeys.SAVE_TO_FILE]

    def to_ros_params(self) -> List[Tuple[str, Any, ParameterDescriptor]]:
        """Convert to ROS2 parameter list with descriptors for declare_parameters"""
        return [
            
            # Connection parameters
            (CameraControllerParametersKeys.DEVICE_ID, self.device_id, ParameterDescriptor(
                description='Photoneo camera device ID',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            
            # Output parameters
            (CameraControllerParametersKeys.OUTPUT_DIRECTORY, self.output_directory, ParameterDescriptor(
                description='Output directory for saved files',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.IMAGE_FORMAT, self.image_format, ParameterDescriptor(
                description='Image format for output (png, jpg, tiff)',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.POINT_CLOUD_FORMAT, self.point_cloud_format, ParameterDescriptor(
                description='Point cloud format for output (ply, pcd)',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SAVE_MESH, self.save_mesh, ParameterDescriptor(
                description='Save mesh data to output',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SAVE_DEPTH_MAP, self.save_depth_map, ParameterDescriptor(
                description='Save depth map to output',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SAVE_POINT_CLOUD, self.save_point_cloud, ParameterDescriptor(
                description='Save point cloud to output',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SAVE_NORMAL_MAP, self.save_normal_map, ParameterDescriptor(
                description='Save normal map to output',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            
            # Capture parameters
            (CameraControllerParametersKeys.TRIGGER_MODE, self.trigger_mode, ParameterDescriptor(
                description='Camera trigger mode (Software, Hardware, Freerun)',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.AMBIENT_LIGHT_SUPPRESSION, self.ambient_light_suppression, ParameterDescriptor(
                description='Enable ambient light suppression',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.CODING_STRATEGY, self.coding_strategy, ParameterDescriptor(
                description='Coding strategy (Interreflections, Normal)',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            
            # Point Cloud Settings
            (CameraControllerParametersKeys.SEND_TEXTURE, self.send_texture, ParameterDescriptor(
                description='Include texture data in point cloud',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SEND_POINT_CLOUD, self.send_point_cloud, ParameterDescriptor(
                description='Send point cloud data',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SEND_NORMAL_MAP, self.send_normal_map, ParameterDescriptor(
                description='Include normal map in output',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SEND_DEPTH_MAP, self.send_depth_map, ParameterDescriptor(
                description='Include depth map in output',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.SEND_CONFIDENCE_MAP, self.send_confidence_map, ParameterDescriptor(
                description='Include confidence map in output',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),

            # Processing parameters
            (CameraControllerParametersKeys.INTERREFLECTIONS_FILTERING, self.interreflections_filtering, ParameterDescriptor(
                description='Enable interreflections filtering',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.INTERREFLECTION_FILTER_STRENGTH, self.interreflection_filter_strength, ParameterDescriptor(
                description='Interreflection filter strength (0.0-1.0)',
                type=Parameter.Type.DOUBLE.value,
                read_only=False,
            )),
            (CameraControllerParametersKeys.MAX_INACCURACY, self.max_inaccuracy, ParameterDescriptor(
                description='Maximum inaccuracy threshold (mm)',
                type=Parameter.Type.DOUBLE.value,
                read_only=False,
            )),
            
            # Coordinate Space parameters
            (CameraControllerParametersKeys.COORDINATE_SPACE, self.coordinate_space, ParameterDescriptor(
                description='Coordinate space (CameraSpace, RobotSpace)',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.TRANSFORMATION_SPACE_SELECTOR, self.transformation_space_selector, ParameterDescriptor(
                description='Transformation space selector',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),
            
            # Debug parameters
            (CameraControllerParametersKeys.USE_TRANSFORM, self.use_transform, ParameterDescriptor(
                description='Enable coordinate transformation',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            
            # Topic publishing
            (CameraControllerParametersKeys.PUBLISH_TOPICS, self.publish_topics, ParameterDescriptor(
                description='Publish scan data on ROS2 topics (PointCloud2, Image)',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            
            # File saving
            (CameraControllerParametersKeys.SAVE_TO_FILE, self.save_to_file, ParameterDescriptor(
                description='Save scan data to file on disk (ply, praw, etc.)',
                type=Parameter.Type.BOOL.value,
                read_only=False
            )),
            (CameraControllerParametersKeys.TF_FRAME_ID, self.tf_frame_id, ParameterDescriptor(
                description='TF frame ID for published data',
                type=Parameter.Type.STRING.value,
                read_only=False
            )),

            (CameraControllerParametersKeys.DEFAULT_TRANSFORM, self.default_transform, ParameterDescriptor(
                description='Default transformation matrix (16 values) for coordinate transformation',
                type=Parameter.Type.DOUBLE_ARRAY.value,
                read_only=False
            )),
        ]

    def to_ros_params_dict(self) -> Dict[str, Any]:
        """Convert to simple dictionary (for backward compatibility)"""
        param_tuples = self.to_ros_params()
        return {name: value for name, value, _ in param_tuples}

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to flat dict keyed by CameraControllerParametersKeys values."""
        return {
            CameraControllerParametersKeys.DEVICE_ID: self.device_id,
            CameraControllerParametersKeys.OUTPUT_DIRECTORY: self.output_directory,
            CameraControllerParametersKeys.IMAGE_FORMAT: self.image_format,
            CameraControllerParametersKeys.POINT_CLOUD_FORMAT: self.point_cloud_format,
            CameraControllerParametersKeys.SAVE_MESH: self.save_mesh,
            CameraControllerParametersKeys.SAVE_DEPTH_MAP: self.save_depth_map,
            CameraControllerParametersKeys.SAVE_POINT_CLOUD: self.save_point_cloud,
            CameraControllerParametersKeys.SAVE_NORMAL_MAP: self.save_normal_map,
            CameraControllerParametersKeys.TRIGGER_MODE: self.trigger_mode,
            CameraControllerParametersKeys.AMBIENT_LIGHT_SUPPRESSION: self.ambient_light_suppression,
            CameraControllerParametersKeys.CODING_STRATEGY: self.coding_strategy,
            CameraControllerParametersKeys.SEND_TEXTURE: self.send_texture,
            CameraControllerParametersKeys.SEND_POINT_CLOUD: self.send_point_cloud,
            CameraControllerParametersKeys.SEND_NORMAL_MAP: self.send_normal_map,
            CameraControllerParametersKeys.SEND_DEPTH_MAP: self.send_depth_map,
            CameraControllerParametersKeys.SEND_CONFIDENCE_MAP: self.send_confidence_map,
            CameraControllerParametersKeys.INTERREFLECTIONS_FILTERING: self.interreflections_filtering,
            CameraControllerParametersKeys.INTERREFLECTION_FILTER_STRENGTH: self.interreflection_filter_strength,
            CameraControllerParametersKeys.MAX_INACCURACY: self.max_inaccuracy,
            CameraControllerParametersKeys.COORDINATE_SPACE: self.coordinate_space,
            CameraControllerParametersKeys.TRANSFORMATION_SPACE_SELECTOR: self.transformation_space_selector,
            CameraControllerParametersKeys.USE_TRANSFORM: self.use_transform,
            CameraControllerParametersKeys.PUBLISH_TOPICS: self.publish_topics,
            CameraControllerParametersKeys.SAVE_TO_FILE: self.save_to_file,
            CameraControllerParametersKeys.TF_FRAME_ID: self.tf_frame_id,
            CameraControllerParametersKeys.DEFAULT_TRANSFORM: self.default_transform,
        }

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> 'CameraControllerParameters':
        """Create instance from flat dict keyed by CameraControllerParametersKeys values."""
        return cls(
            device_id=data[CameraControllerParametersKeys.DEVICE_ID],
            output_directory=data[CameraControllerParametersKeys.OUTPUT_DIRECTORY],
            image_format=data[CameraControllerParametersKeys.IMAGE_FORMAT],
            point_cloud_format=data[CameraControllerParametersKeys.POINT_CLOUD_FORMAT],
            save_mesh=data[CameraControllerParametersKeys.SAVE_MESH],
            save_depth_map=data[CameraControllerParametersKeys.SAVE_DEPTH_MAP],
            save_point_cloud=data[CameraControllerParametersKeys.SAVE_POINT_CLOUD],
            save_normal_map=data[CameraControllerParametersKeys.SAVE_NORMAL_MAP],
            trigger_mode=data[CameraControllerParametersKeys.TRIGGER_MODE],
            ambient_light_suppression=data[CameraControllerParametersKeys.AMBIENT_LIGHT_SUPPRESSION],
            coding_strategy=data[CameraControllerParametersKeys.CODING_STRATEGY],
            send_texture=data[CameraControllerParametersKeys.SEND_TEXTURE],
            send_point_cloud=data[CameraControllerParametersKeys.SEND_POINT_CLOUD],
            send_normal_map=data[CameraControllerParametersKeys.SEND_NORMAL_MAP],
            send_depth_map=data[CameraControllerParametersKeys.SEND_DEPTH_MAP],
            send_confidence_map=data[CameraControllerParametersKeys.SEND_CONFIDENCE_MAP],
            interreflections_filtering=data[CameraControllerParametersKeys.INTERREFLECTIONS_FILTERING],
            interreflection_filter_strength=data[CameraControllerParametersKeys.INTERREFLECTION_FILTER_STRENGTH],
            max_inaccuracy=data[CameraControllerParametersKeys.MAX_INACCURACY],
            coordinate_space=data[CameraControllerParametersKeys.COORDINATE_SPACE],
            transformation_space_selector=data[CameraControllerParametersKeys.TRANSFORMATION_SPACE_SELECTOR],
            use_transform=data[CameraControllerParametersKeys.USE_TRANSFORM],
            tf_frame_id=data[CameraControllerParametersKeys.TF_FRAME_ID],
            default_transform=data[CameraControllerParametersKeys.DEFAULT_TRANSFORM],
            publish_topics=data[CameraControllerParametersKeys.PUBLISH_TOPICS],
            save_to_file=data[CameraControllerParametersKeys.SAVE_TO_FILE],
        )

    def save_yaml(self, path: str) -> None:
        """Save parameters to a YAML file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump({'camera_controller_parameters': self.to_flat_dict()}, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load_yaml(cls, path: str) -> 'CameraControllerParameters':
        """Load parameters from a YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_flat_dict(data.get('camera_controller_parameters', {}))