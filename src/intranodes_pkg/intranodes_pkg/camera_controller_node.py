import os
import sys
import numpy as np
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, QoSPresetProfiles
from harvesters.core import Harvester
from sys import platform
import uuid
from datetime import datetime
import psutil
import struct
import open3d as o3d

from sensor_msgs.msg import PointCloud2, PointField, Image
from std_msgs.msg import Header


from core_pkg.nodes_core import INTRANode, handle_operation_errors
from core_pkg.systemconstants import CameraControllerConstants
from core_pkg.exceptions import NodeExceptionRecoverable, NodeExceptionNonRecoverable
from intranodes_pkg.parameters.camera_controller_parameters import CameraControllerParameters, CameraControllerParametersKeys
PUBLISH_FULL_IN_METRES = False  # Set to True to publish an additional full-resolution point cloud in metres for RViz visualization, False to only publish in mm
from interface_pkg.srv import ScanAcquisitionSrv, TriggerServiceSrv

class CameraControllerNode(INTRANode):

    def __init__(self):
        super().__init__(CameraControllerConstants.NODE_NAME)
        # Initialize default CameraController parameters
        self.default_ros_params = CameraControllerParameters().to_ros_params()
        self.harvester: Harvester = None
        self.ia = None 
        self.live_settings = None 


        # Declare ROS2 parameters
        declared_params = self.declare_parameters(
            namespace='',  # Empty because params already have dot notation
            parameters=self.default_ros_params
        )
        self.logger.info(f"Declared {len(declared_params)} parameters")
        
        # Create ROS2 publishers for scan data topics
        topic_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.SYSTEM_DEFAULT
        )

        # SensorDataQoS matches what MoveIt's PointCloudOctomapUpdater expects
        sensor_qos = QoSPresetProfiles.SENSOR_DATA.value

        # Re-publish state for point cloud (guards against MoveIt TF timing)
        self._cloud_republish_remaining = 0
        self._cloud_msg_cache = None
        self._cloud_republish_timer = None

        # Declare topics
        # BEST_EFFORT for MoveIt octomap updater
        self.cloud_pub = self.create_publisher(
            PointCloud2, f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.POINT_CLOUD_TOPIC}", sensor_qos)

        # RELIABLE for RViz visualization
        self.cloud_reliable_pub = self.create_publisher(
            PointCloud2, f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.POINT_CLOUD_FULL_TOPIC}", topic_qos)
        if PUBLISH_FULL_IN_METRES:
            self.cloud_reliable_metres_pub = self.create_publisher(
                PointCloud2, f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.POINT_CLOUD_FULL_TOPIC_ROS}", topic_qos)

        self.texture_pub = self.create_publisher(
            Image, f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.TEXTURE_TOPIC}", topic_qos)
        self.depth_map_pub = self.create_publisher(
            Image, f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.DEPTH_MAP_TOPIC}", topic_qos)
        self.normal_map_pub = self.create_publisher(
            Image, f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.NORMAL_MAP_TOPIC}", topic_qos)
        self.confidence_map_pub = self.create_publisher(
            Image, f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.CONFIDENCE_MAP_TOPIC}", topic_qos)
        

        # Declare services
        self.scan_execution_service = self.create_service(ScanAcquisitionSrv, 
        f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.ServiceNames.EXECUTE_SCAN}", 
        self.execute_scan_cb, callback_group=self.cb_group)


        
        with self.sm_lock:
            self.lifecycle_sm.boot_complete(message=f"Boot of {self.NODE_NAME} complete, waiting for initialization")

    


    def initialize_node(self):
        """Initialize CameraController node"""
        if self.ia is not None:
            raise NodeExceptionRecoverable("Node already initialized, cleanup before re-initialization")

        device_id =self.get_parameter(CameraControllerParametersKeys.DEVICE_ID).value

        # Setup CTI file path
        if platform == "win32":
            cti_file_path_suffix = "API/bin/photoneo.cti"
        else:
            cti_file_path_suffix = "API/lib/photoneo.cti"

        cti_file_prefix = os.getenv('PHOXI_CONTROL_PATH')

        if cti_file_prefix is None:
            raise NodeExceptionNonRecoverable("PHOXI_CONTROL_PATH environment variable is not set, is PhoxiControl control installed?")

        cti_file_path = os.path.join(cti_file_prefix, cti_file_path_suffix)

        self.logger.info(f"cti_file_path: {cti_file_path}")

        # Check if PhoxiControl is running
        is_phoxi_running, phoxi_pid = self._is_phoxi_control_running()
        if is_phoxi_running:
            self.logger.info(f"PhoxiControl is running with PID: {phoxi_pid}")
        else:
            raise NodeExceptionNonRecoverable("PhoxiControl process not found, ensure it is running")

        # Initialize harvester
        self.logger.info('Initializing Harvester')
        self.harvester = Harvester()
        try:
            self.harvester.add_file(cti_file_path, True, True)
            self.harvester.update()

        except FileNotFoundError as e:
            raise NodeExceptionNonRecoverable(f"CTI file not found or invalid path: {e}") from e
        
        except Exception as e:
            raise NodeExceptionNonRecoverable(f"Failed to initialize Harvester: {e}") from e
        
        device__id_list = [item.property_dict['id_'] for item in self.harvester.device_info_list]
        # Print available devices
        self.logger.info("Available devices:")
        for item in self.harvester.device_info_list:
            self.logger.info(f"Name: {item.property_dict['serial_number']} | ID: {item.property_dict['id_']}")
            
        self.logger.info('Initializing Image Acquirer')
        self.logger.info(f'Using device: {device_id}')
        
        try:
            self.ia = self.harvester.create({'id_': device_id})
            self.live_settings = self.ia.remote_device.node_map
        except Exception as e:
            raise NodeExceptionNonRecoverable(f"Failed to create Image Acquirer: {e}, available devices: {device__id_list}") from e

        self.logger.info("Applying parameters to CameraController...")
        try:
            self.apply_parameters()
            self.logger.info("Parameters applied successfully during initialization")

        except Exception as e:
            raise NodeExceptionRecoverable(f"Failed to apply parameters: {e}") from e
   
    def generate_scan_filename(self, pc_format: str) -> str:
        """Generate unique scan filename with timestamp and UUID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]  # First 8 characters of UUID

        return f"scan_{timestamp}_{short_uuid}.{pc_format}"

    @handle_operation_errors
    def execute_scan_cb(self, request: ScanAcquisitionSrv.Request, response: ScanAcquisitionSrv.Response):
        """Handle scan execution service call"""
        ia_started = False  # Track if ia.start() was successful
        scan_path = ''
        
        try:
            with self.sm_lock:
                self.lifecycle_sm.start_operation(message="Executing scan via service call")

            if self.ia is None:
                raise NodeExceptionNonRecoverable("Camera not initialized")
            
            transform = np.array(request.transform).reshape((4, 4))
            if np.allclose(transform, 0.0):
                try:
                    default_transform_list = self.get_parameter(CameraControllerParametersKeys.DEFAULT_TRANSFORM).value
                    transform = np.array(default_transform_list).reshape((4, 4))
                except Exception as e:
                    self.logger.error(f"Error retrieving default transform: {e}")
                    transform = np.eye(4)
                self.logger.info(f"Using default transform:\n{transform}")
            else:
                self.logger.info(f"Using request transform:\n{transform}")
            
            self.set_robot_transform(transform)

            self.ia.start()
            ia_started = True  # Mark that start was successful
            self.logger.info("Image Acquirer started")

            # Trigger frame by calling property's setter.
            # Must call TriggerFrame before every fetch.
            self.live_settings.TriggerFrame.execute()
            
            buffer = self.ia.fetch(timeout=10.0)
            self.logger.info("Image fetched successfully")

            # Publish scan data to ROS2 topics if enabled
            publish_topics = self.get_parameter(CameraControllerParametersKeys.PUBLISH_TOPICS).value
            if publish_topics:
                try:
                    self.publish_frame_data(buffer)
                except Exception as e:
                    self.logger.error(f"Error publishing frame data to topics: {e}")

            save_to_file = self.get_parameter(CameraControllerParametersKeys.SAVE_TO_FILE).value
            if save_to_file:

                scan_dir = self.get_parameter(CameraControllerParametersKeys.OUTPUT_DIRECTORY).value
                point_cloud_format: str = self.get_parameter(CameraControllerParametersKeys.POINT_CLOUD_FORMAT).value
                
                os.makedirs(scan_dir, exist_ok=True)
                scan_name = self.generate_scan_filename(point_cloud_format)
                scan_path = os.path.join(os.getcwd(), scan_dir, scan_name)  # Make path absolute

                self.live_settings.SaveLastScanFilePath.value = scan_path
                self.live_settings.SaveLastScanFrameId.value = -1

                json_options = '{"Mesh": true, "DepthMap": true, "PointCloud": true, "NormalMap": true}'
                self.live_settings.SaveLastScanJsonOptions.value = json_options
                self.live_settings.SaveLastScan.execute()

                self.logger.info(f"New scan saved to: {scan_path}")
            else:
                self.logger.info("File saving disabled (output.save_to_file=false)")

            # Release the buffer back to Harvesters
            buffer.queue()

            # Set response fields only on success
            response.status = True
            response.message = f"Scan execution completed successfully"
            response.file_path = scan_path
            with self.sm_lock:
                self.lifecycle_sm.complete(message=response.message)
        
        finally:
            # Always stop Image Acquirer if it was started
            if ia_started and self.ia:
                try:
                    self.ia.stop()
                    self.logger.info("Image Acquirer stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping Image Acquirer: {e}")
        
        # No return needed - decorator handles it


    def publish_frame_data(self, buffer):
        """Extract components from the Harvesters buffer and publish them on topics.

        Photoneo buffer component order:
            [0] Texture, [2] PointCloud, [3] NormalMap, [4] DepthMap, [5] ConfidenceMap.
        Empty/disabled components have width=0 and height=0.
        """
        payload = buffer.payload
        components = payload.components
        
        self.logger.info(f"Buffer has {len(components)} components")
        for i, comp in enumerate(components):
            has_data = comp.data is not None and comp.data.size > 0
            data_info = ""
            if has_data:
                data_info = (
                    f"dtype={comp.data.dtype}, size={comp.data.size}, "
                    f"min={comp.data.min():.6f}, max={comp.data.max():.6f}, "
                    f"nonzero={np.count_nonzero(comp.data)}"
                )
            self.logger.info(
                f"  Component[{i}]: {comp.width}x{comp.height}, "
                f"data_format={comp.data_format if hasattr(comp, 'data_format') else 'N/A'}, "
                f"has_data={has_data}, {data_info}"
            )
        
        stamp = self.get_clock().now().to_msg()
        frame_id =  self.get_parameter(CameraControllerParametersKeys.TF_FRAME_ID).value
        
        header = Header()
        header.stamp = stamp
        header.frame_id = frame_id


        # --- Texture mono (component[0]) ---
        if len(components) > 0:
            tex_comp = components[0]
            if tex_comp.width > 0 and tex_comp.height > 0:
                try:
                    self._publish_image(tex_comp, header, self.texture_pub,
                                        encoding='32FC1', channels=1, name='Texture')
                except Exception as e:
                    self.logger.error(f"Failed to publish texture: {e}")
            else:
                self.logger.warn("Texture component is empty, skipping publish")

        # --- DepthMap (component[4]) ---
        if len(components) > 4:
            depth_comp = components[4]
            if depth_comp.width > 0 and depth_comp.height > 0:
                try:
                    self._publish_image(depth_comp, header, self.depth_map_pub,
                                        encoding='32FC1', channels=1, name='DepthMap')
                except Exception as e:
                    self.logger.error(f"Failed to publish depth map: {e}")
            else:
                self.logger.warn("DepthMap component is empty, skipping publish")

        
        # --- PointCloud2 (component[2]) ---
        if len(components) > 2:
            pc_comp = components[2]
            if pc_comp.width > 0 and pc_comp.height > 0:
                try:
                    self._publish_point_cloud(pc_comp, header)
                except Exception as e:
                    self.logger.error(f"Failed to publish point cloud: {e}")
            else:
                self.logger.warn("PointCloud component is empty, skipping publish")
        
        
        
        # --- NormalMap (component[3]) ---
        if len(components) > 3:
            normal_comp = components[3]
            if normal_comp.width > 0 and normal_comp.height > 0:
                try:
                    self._publish_image(normal_comp, header, self.normal_map_pub,
                                        encoding='32FC3', channels=3, name='NormalMap')
                except Exception as e:
                    self.logger.error(f"Failed to publish normal map: {e}")
            else:
                self.logger.warn("NormalMap component is empty, skipping publish")
        
        # --- ConfidenceMap (component[5]) ---
        if len(components) > 5:
            conf_comp = components[5]
            if conf_comp.width > 0 and conf_comp.height > 0:
                try:
                    self._publish_image(conf_comp, header, self.confidence_map_pub,
                                        encoding='32FC1', channels=1, name='ConfidenceMap')
                except Exception as e:
                    self.logger.error(f"Failed to publish confidence map: {e}")
            else:
                self.logger.warn("ConfidenceMap component is empty, skipping publish")
        
        self.logger.info("Frame data published to topics")


    def _publish_point_cloud(self, pc_comp, header: Header):
        """
        Build and publish a sensor_msgs/PointCloud2 message from the point cloud component.
        Publishes an organized point cloud (preserving width x height grid).
        """
        height = pc_comp.height
        width = pc_comp.width
        raw = pc_comp.data
        if raw is None:
            self.logger.error("PointCloud component .data is None, skipping publish")
            return
    
        self.logger.info(
            f"PointCloud raw diag: dtype={raw.dtype}, shape={raw.shape}, "
            f"min={raw.min():.6f}, max={raw.max():.6f}, "
            f"nonzero={np.count_nonzero(raw)}/{raw.size}, "
            f"data_format={pc_comp.data_format if hasattr(pc_comp, 'data_format') else 'N/A'}"
        )
        
        # Reshape to (H*W, 3) and ensure C-contiguous float32 for .tobytes().
        # np.ascontiguousarray only copies when the source is non-contiguous.
        points = np.ascontiguousarray(raw.reshape(height * width, 3), dtype=np.float32)

        # Convert from mm to meters
        points_m = 0.001 * points

        # Voxel downsample for MoveIt octomap (reduces point significantly)
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points_m)
        downpcd = pcd.voxel_down_sample(voxel_size=0.005)
        points_ds = np.ascontiguousarray(np.asarray(downpcd.points), dtype=np.float32)
        num_points_ds = len(points_ds)

        # Diagnostic: check reshaped data
        self.logger.info(
            f"PointCloud reshaped diag: shape={points.shape}, "
            f"min={points.min():.6f}, max={points.max():.6f}, "
            f"sample[0]={points[0] if len(points) > 0 else 'empty'}, "
            f"downsampled: {height * width} → {num_points_ds} points"
        )
        
        # --- Full-resolution message (RELIABLE RViz) ---
        msg_full = PointCloud2()
        msg_full.header = header
        msg_full.height = height
        msg_full.width = width
        print(f"Publishing full point cloud with width={width}, height={height}")
        msg_full.is_dense = False
        msg_full.is_bigendian = False
        msg_full.fields = [
            PointField(name='x', offset=0,  datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4,  datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8,  datatype=PointField.FLOAT32, count=1),
        ]
        msg_full.point_step = 12
        msg_full.row_step = msg_full.point_step * width
        msg_full._data = np.ascontiguousarray(points).tobytes()

        if PUBLISH_FULL_IN_METRES:
            # --- Full-resolution message in metres (RELIABLE RViz) ---
            msg_full_ros = PointCloud2()
            msg_full_ros.header = header
            msg_full_ros.height = height
            msg_full_ros.width = width
            print(f"Publishing full point cloud with width={width}, height={height}")
            msg_full_ros.is_dense = False
            msg_full_ros.is_bigendian = False
            msg_full_ros.fields = [
                PointField(name='x', offset=0,  datatype=PointField.FLOAT32, count=1),
                PointField(name='y', offset=4,  datatype=PointField.FLOAT32, count=1),
                PointField(name='z', offset=8,  datatype=PointField.FLOAT32, count=1),
            ]
            msg_full_ros.point_step = 12
            msg_full_ros.row_step = msg_full_ros.point_step * width
            msg_full_ros._data = np.ascontiguousarray(points_m).tobytes()

        # --- Downsampled message (BEST_EFFORT MoveIt octomap) ---
        msg_ds = PointCloud2()
        msg_ds.header = header
        msg_ds.height = 1                    # unorganized after voxel downsample
        msg_ds.width = num_points_ds
        msg_ds.is_dense = False
        msg_ds.is_bigendian = False
        msg_ds.fields = msg_full.fields
        msg_ds.point_step = 12
        msg_ds.row_step = msg_ds.point_step * num_points_ds
        msg_ds._data = points_ds.tobytes()

        self.cloud_pub.publish(msg_ds)              # BEST_EFFORT MoveIt octomap
        self.cloud_reliable_pub.publish(msg_full)    # RELIABLE   RViz
        if PUBLISH_FULL_IN_METRES:
            self.cloud_reliable_metres_pub.publish(msg_full_ros)    # RELIABLE   RViz with metres
        self.logger.debug(f"Published PointCloud2: full={width}x{height}, ds={num_points_ds} points")


    def _publish_image(self, component, header: Header, publisher, 
                       encoding: str, channels: int, name: str):
        """
        Build and publish a sensor_msgs/Image message from a buffer component.
        
        Args:
            component: Harvesters payload component with .data, .width, .height
            header: ROS2 message header with stamp and frame_id
            publisher: ROS2 publisher to use
            encoding: Image encoding string (e.g. '32FC1', '32FC3')
            channels: Number of channels (1 or 3)
            name: Component name for logging
        """
        height = component.height
        width = component.width
        raw = component.data
        if raw is None:
            self.logger.error(f"{name} component .data is None, skipping publish")
            return
        
        msg = Image()
        msg.header = header
        msg.height = height
        msg.width = width
        msg.encoding = encoding
        msg.is_bigendian = False
        msg.step = width * channels * 4  # float32 = 4 bytes per element
        
        # Reshape and ensure C-contiguous float32 for .tobytes().
        # np.ascontiguousarray only copies when the source is non-contiguous.
        if channels == 1:
            data = np.ascontiguousarray(raw.reshape(height, width), dtype=np.float32)
        else:
            data = np.ascontiguousarray(raw.reshape(height, width, channels), dtype=np.float32)
        
        # Assign to _data directly — the .data setter validates every byte
        # individually in Python, which is extremely slow for large payloads.
        msg._data = data.tobytes()
        
        publisher.publish(msg)
        self.logger.debug(f"Published {name} Image: {width}x{height}, encoding={encoding}")


    def apply_parameters(self):
        """Apply parameters to the Photoneo camera"""
        
        if hasattr(self.live_settings, 'CameraControllerTriggerMode'):
            self.live_settings.CameraControllerTriggerMode.value = self.get_parameter(CameraControllerParametersKeys.TRIGGER_MODE).value
        else:
            self.logger.info('Feature CameraControllerTriggerMode not available on this device.')

        if hasattr(self.live_settings, 'AmbientLightSuppression'):
            self.live_settings.AmbientLightSuppression.value = self.get_parameter(CameraControllerParametersKeys.AMBIENT_LIGHT_SUPPRESSION).value
        else:
            self.logger.info('Feature AmbientLightSuppression not available on this device.')

        if hasattr(self.live_settings, 'CodingStrategy'):
            self.live_settings.CodingStrategy.value = self.get_parameter(CameraControllerParametersKeys.CODING_STRATEGY).value
        else:
            self.logger.info('Feature CodingStrategy not available on this device.')

        if hasattr(self.live_settings, 'SendTexture'):
            self.live_settings.SendTexture.value = self.get_parameter(CameraControllerParametersKeys.SEND_TEXTURE).value
        else:
            self.logger.info('Feature SendTexture not available on this device.')

        if hasattr(self.live_settings, 'SendPointCloud'):
            self.live_settings.SendPointCloud.value = self.get_parameter(CameraControllerParametersKeys.SEND_POINT_CLOUD).value
        else:
            self.logger.info('Feature SendPointCloud not available on this device.')

        if hasattr(self.live_settings, 'SendNormalMap'):
            self.live_settings.SendNormalMap.value = self.get_parameter(CameraControllerParametersKeys.SEND_NORMAL_MAP).value
        else:
            self.logger.info('Feature SendNormalMap not available on this device.')

        if hasattr(self.live_settings, 'SendDepthMap'):
            self.live_settings.SendDepthMap.value = self.get_parameter(CameraControllerParametersKeys.SEND_DEPTH_MAP).value
        else:
            self.logger.info('Feature SendDepthMap not available on this device.')

        if hasattr(self.live_settings, 'SendConfidenceMap'):
            self.live_settings.SendConfidenceMap.value = self.get_parameter(CameraControllerParametersKeys.SEND_CONFIDENCE_MAP).value
        else:
            self.logger.info('Feature SendConfidenceMap not available on this device.')

        if hasattr(self.live_settings, 'InterreflectionsFiltering'):
            self.live_settings.InterreflectionsFiltering.value = self.get_parameter(CameraControllerParametersKeys.INTERREFLECTIONS_FILTERING).value
        else:
            self.logger.info('Feature InterreflectionsFiltering not available on this device.')

        if hasattr(self.live_settings, 'InterreflectionFilterStrength'):
            self.live_settings.InterreflectionFilterStrength.value = self.get_parameter(CameraControllerParametersKeys.INTERREFLECTION_FILTER_STRENGTH).value
        else:
            self.logger.info('Feature InterreflectionFilterStrength not available on this device.')

        if hasattr(self.live_settings, 'MaxInaccuracy'):
            self.live_settings.MaxInaccuracy.value = self.get_parameter(CameraControllerParametersKeys.MAX_INACCURACY).value
        else:
            self.logger.info('Feature MaxInaccuracy not available on this device.')

        if hasattr(self.live_settings, 'CoordinateSpace'):
            self.live_settings.CoordinateSpace.value = self.get_parameter(CameraControllerParametersKeys.COORDINATE_SPACE).value
        else:
            self.logger.info('Feature CoordinateSpace not available on this device.')

        if hasattr(self.live_settings, 'TransformationSpaceSelector'):
            self.live_settings.TransformationSpaceSelector.value = self.get_parameter(CameraControllerParametersKeys.TRANSFORMATION_SPACE_SELECTOR).value
        else:
            self.logger.info('Feature TransformationSpaceSelector not available on this device.')

    def cleanup_resources(self):
        """Cleanup camera resources"""
        self.logger.info('Cleaning up CameraController resources...')
        
        # Stop and destroy image acquirer
        if self.ia:
            self.ia.stop()
            self.ia.destroy()
            self.logger.info('ImageAcquirer destroyed')

            self.ia = None
            self.live_settings = None
                
        # Reset harvester
        if self.harvester:
                self.harvester.reset()
                self.logger.info('Harvester reset')

                self.harvester = None
                
    def _is_phoxi_control_running(self):
        """Check if PhoxiControl is running by process name"""
        try:
            # Common PhoxiControl process names
            phoxi_processes = [
                'PhoxiControl',
                'PhoXiControl',
                'phoxicontrol', 
                'PhoXiControl.exe',
                'phoxicontrol.exe'
            ]
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    process_name = proc.info['name']
                    if process_name and any(phoxi_name.lower() in process_name.lower() 
                                        for phoxi_name in phoxi_processes):
                        return True, proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            return False, None
            
        except Exception as e:
            print(f"Error checking PhoxiControl processes: {e}")
            return False, None
        
    def set_robot_transform(self, transform: np.ndarray):
        """
        Sets the robot transformation matrix (4x4) ndarray to photoneo camera

        """
        rot_mat = transform[:3, :3]
        trans_vect = transform[:3, 3].tolist()
        rot_vect = rot_mat.reshape(1, 9).tolist()

        robot_transformation_rotation_matrix_new_values = rot_vect[0]
        robot_transformation_rotation_matrix_length = self.live_settings.RobotTransformationRotationMatrix.length
        robot_transformation_rotation_matrix_bytes = self.live_settings.RobotTransformationRotationMatrix.get(robot_transformation_rotation_matrix_length)
        robot_transformation_rotation_matrix = struct.unpack('9d', robot_transformation_rotation_matrix_bytes)
        robot_transformation_rotation_matrix_new_bytes = struct.pack('9d', *robot_transformation_rotation_matrix_new_values)

        robot_transformation_translation_vector_new_values = trans_vect
        robot_transformation_translation_vector_length = self.live_settings.RobotTransformationTranslationVector.length
        robot_transformation_translation_vector_bytes = self.live_settings.RobotTransformationTranslationVector.get(robot_transformation_translation_vector_length)
        robot_transformation_translation_vector = struct.unpack('3d', robot_transformation_translation_vector_bytes)
        robot_transformation_translation_vector_new_bytes = struct.pack('3d', *robot_transformation_translation_vector_new_values)
        
        self.live_settings.RobotTransformationTranslationVector.set(robot_transformation_translation_vector_new_bytes)
        self.live_settings.RobotTransformationRotationMatrix.set(robot_transformation_rotation_matrix_new_bytes)
        self.logger.info('Robot transformation matrices updated successfully')


def main(args=None):
    """Main entry point for Camera Controller node"""

    rclpy.init(args=args)
    camera_controller_node = None
    executor = None
    
    try:
        # Initialize the Camera Controller node
        camera_controller_node = CameraControllerNode()
        
        # Create multithreaded executor with 2 threads
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(camera_controller_node)
        
        # Spin the executor
        executor.spin()
        
    except KeyboardInterrupt:
        if camera_controller_node:
            camera_controller_node.logger.info("Keyboard interrupt received")
            
    except Exception as e:
        if camera_controller_node:
            camera_controller_node.logger.error(f"Unexpected error: {e}")
        else:
            print(f'Error during node initialization: {e}')
            
    finally:
        # Shutdown executor (stops spinning and waits for callbacks to finish)
        if executor:
            executor.shutdown(timeout_sec=5)
        
        # Update lifecycle state
        if camera_controller_node:
            with camera_controller_node.sm_lock:
                try:
                    camera_controller_node.lifecycle_sm.shutdown(
                        message="Node shutting down"
                    )
                except Exception as e:
                    camera_controller_node.logger.warning(
                        f"State transition failed during shutdown: {e}"
                    )
        
        # Cleanup node-specific resources
        if camera_controller_node:
            try:
                camera_controller_node.cleanup_resources()
            except Exception as e:
                camera_controller_node.logger.error(
                    f"Error during cleanup: {e}"
                )
        
        # Destroy the node
        if camera_controller_node:
            camera_controller_node.destroy_node()
        
        # Shutdown rclpy
        try:
            rclpy.shutdown()
        except Exception:
            pass  # rclpy may already be shut down


if __name__ == '__main__':
    main()