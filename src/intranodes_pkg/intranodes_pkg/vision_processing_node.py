import os
import sys
from time import time
import numpy as np
import intranodes_pkg.vision_helpers as vh
import intranodes_pkg.vision_helpers2 as vh2
import rclpy
from rclpy.executors import MultiThreadedExecutor
from copy import deepcopy

from core_pkg.nodes_core import handle_operation_errors, INTRANode
from core_pkg.systemconstants import VisionProcessingConstants, CameraControllerConstants, TOPIC_QOS
from core_pkg.exceptions import NodeExceptionRecoverable, NodeExceptionNonRecoverable

from transformers import Sam3Processor, Sam3Model
import torch
from PIL import Image as PILImage
import requests 
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from huggingface_hub import login
import cv2
import os
import open3d as o3d
from cv_bridge import CvBridge
from typing import Optional

from rclpy.parameter import Parameter
from intranodes_pkg.parameters.vision_parameters import VisionParameters, VisionParametersKeys
from interface_pkg.srv import Project2DServiceSrv, TriggerServiceSrv, ProcessVisionSrv, ProcessVisionSrv2
from interface_pkg.msg import GraspResult
from sensor_msgs.msg import PointCloud2, Image
from geometry_msgs.msg import Point, Pose

from core_pkg.settings import HUGGINGFACE_API_KEY


class VisionNode(INTRANode):

    def __init__(self):
        super().__init__(VisionProcessingConstants.NODE_NAME)
        self.mask_processor = None
        self.model = None
        self.bridge = CvBridge()
        self.current_texture: Optional[PILImage.Image] = None
        self.current_pcd: Optional[np.ndarray] = None
        self.is_new_pcd_received = False
        self.is_new_txt_received = False

        # Initialize default vision parameters
        self.default_ros_params = VisionParameters().to_ros_params()
        # Declare ROS2 parameters
        declared_params = self.declare_parameters(
            namespace='',  # Empty because params already have dot notation
            parameters=self.default_ros_params
        )
        self.logger.info(f"Declared {len(declared_params)} parameters")
        
        # Services

        self.vision_processing_op1_srv = self.create_service(ProcessVisionSrv,
        f"{VisionProcessingConstants.NODE_NAME}/{VisionProcessingConstants.ServiceNames.PROCESS_VISION_OP1}",
        self.vision_processing_op1_cb, callback_group=self.cb_group)

        self.vision_processing_op2_srv = self.create_service(ProcessVisionSrv2,
        f"{VisionProcessingConstants.NODE_NAME}/{VisionProcessingConstants.ServiceNames.PROCESS_VISION_OP2}",
        self.vision_processing_op2_cb, callback_group=self.cb_group)

        # Topic subscriptions
        self.point_cloud_sub = self.create_subscription(
            PointCloud2,
            f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.POINT_CLOUD_FULL_TOPIC}",
            self.point_cloud_cb,
            callback_group=self.cb_group,
            qos_profile=TOPIC_QOS
        )

        self.texture_sub = self.create_subscription(
            Image,
            f"{CameraControllerConstants.NODE_NAME}/{CameraControllerConstants.TopicNames.TEXTURE_TOPIC}",
            self.texture_cb,
            callback_group=self.cb_group,
            qos_profile=TOPIC_QOS
        )

        with self.sm_lock:
            self.lifecycle_sm.boot_complete(message=f"Boot of {self.NODE_NAME} complete, waiting for initialization")

    def point_cloud_cb(self, msg: PointCloud2):
        self.logger.info(f"Received point cloud with {msg.width}x{msg.height} points")
        self.current_pcd = vh.ros_to_ndarray(msg)
        self.current_pcd = np.reshape(self.current_pcd, (msg.height, msg.width, -1))
        self.logger.info(f"Converted point cloud to NDArray format with {self.current_pcd.shape}   points")
        self.is_new_pcd_received = True


    def texture_cb(self, msg: Image):
        self.logger.info(f"Received texture image with dimensions {msg.width}x{msg.height}")
        self.current_texture = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        self.current_texture = vh.gamma_correct_texture_new(self.current_texture, gamma=0.5)
        self.is_new_txt_received = True
        # self.current_texture.save("test.png") #debug



    @handle_operation_errors
    def vision_processing_op1_cb(self, request: ProcessVisionSrv.Request, response: ProcessVisionSrv.Response):

    
        with self.sm_lock:
            self.lifecycle_sm.start_operation(message="Received request to process pointcloud")


        if not self.is_new_pcd_received or not self.is_new_txt_received:
            response.status = False
            response.message = "Waiting for both point cloud and texture data to be received"
            self.lifecycle_sm.complete(message=response.message)
            return response
        
        
        _cur_pcd = self.current_pcd
        _cur_texture = self.current_texture
        H = _cur_texture.height
        W = _cur_texture.width
        
        img_input = [_cur_texture, _cur_texture, _cur_texture, _cur_texture]
        text_input = ["hexagon object", "background", "circle object", "small drawn rectangle"]

        # Segment using text prompt
        inputs = self.mask_processor(images=img_input, text=text_input, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        # Post-process results
        results = self.mask_processor.post_process_instance_segmentation(
            outputs,
            threshold=0.5,
            mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist()
        )

        #extract masks and convert to binary format
        if len(results[0]["masks"]) != 1:
            raise NodeExceptionRecoverable(f"Expected exactly 1 hexagon mask, but found {len(results[0]['masks'])}")
        else:
            mask_hex = results[0]["masks"][0].detach().cpu().numpy().astype(np.uint8)
            mask_hex = (mask_hex > 0).astype(np.uint8) * 255

        if len(results[1]["masks"]) != 1:
            raise NodeExceptionRecoverable(f"Expected exactly 1 background mask, but found {len(results[1]['masks'])}")
        else:
            mask_bg = results[1]["masks"][0].detach().cpu().numpy().astype(np.uint8)
            mask_bg = (mask_bg > 0).astype(np.uint8) * 255

        circle_masks = []
        for circle_mask_tensor in results[2]["masks"]:
            candidate_mask = circle_mask_tensor.detach().cpu().numpy().astype(np.uint8)
            candidate_mask = (candidate_mask > 0).astype(np.uint8) * 255
            circle_masks.append(candidate_mask)

        if not circle_masks:
            raise NodeExceptionRecoverable(f"Expected at least 1 circle mask, but found {len(results[2]['masks'])}")

        # Sort circle masks by area
        circle_masks.sort(key=np.count_nonzero, reverse=True)
        mask_circle = circle_masks[0]

        DUPLICATE_THRESHOLD_PX = 50
        hex_centroid = self._mask_centroid(mask_hex)
        circle_centroid = self._mask_centroid(mask_circle)

        if hex_centroid is not None and circle_centroid is not None:
            dist = np.linalg.norm(np.array(hex_centroid) - np.array(circle_centroid))
            self.logger.info(f"Hex-Circle centroid distance: {dist:.1f} px (threshold={DUPLICATE_THRESHOLD_PX})")
            if dist < DUPLICATE_THRESHOLD_PX:
                self.logger.warning("Circle mask centroid is too close to hexagon – likely a duplicate segmentation.")
                if len(circle_masks) >= 2:
                    mask_circle = circle_masks[1]
                    self.logger.info("Switched to the second largest circle mask.")
                else:
                    raise NodeExceptionRecoverable(
                        "Circle mask overlaps hexagon and no alternative circle mask is available."
                    )

        if len(results[3]["masks"]) != 1:
            raise NodeExceptionRecoverable(f"Expected exactly 1 small drawn rectangle mask, but found {len(results[3]['masks'])}")
        else:            
            mask_drawn = results[3]["masks"][0].detach().cpu().numpy().astype(np.uint8)
            mask_drawn = (mask_drawn > 0).astype(np.uint8) * 255


        img = vh.overlay_masks(_cur_texture, results[0]["masks"])
        img_bg = vh.overlay_masks(_cur_texture, results[1]["masks"])
        img = vh.overlay_masks(img, results[2]["masks"])
        img = vh.overlay_masks(img, results[3]["masks"])

        
        hexagon_box = vh.largest_contour_from_mask(mask_hex, "Hexagon")
        circle_box = vh.largest_contour_from_mask(mask_circle, "Circle")
        rect_box = vh.largest_contour_from_mask(mask_drawn, "Small Drawn Rectangle")

        img_np = np.array(img.convert("RGB"))


        cv2.drawContours(img_np, [hexagon_box], 0, (0, 255, 0), 2)
        cv2.drawContours(img_np, [circle_box], 0, (255, 0, 0), 2)
        cv2.drawContours(img_np, [rect_box], 0, (0, 0, 255), 2)


        masked_hex_pcd    = vh.masked_pointcloud(_cur_pcd, mask_hex)
        masked_bg_pcd = vh.masked_pointcloud(_cur_pcd, mask_bg)
        masked_circle_pcd = vh.masked_pointcloud(_cur_pcd, mask_circle)
        masked_drawn_pcd = vh.masked_pointcloud(_cur_pcd, mask_drawn)

        cleaned_pcd_hex, plane_model_hex, normal_vector_hex, plane_pcd_hex, inlier_pcd_hex = vh.fit_plane(masked_hex_pcd, "Hexagon")
        [a_hex, b_hex, c_hex, d_hex] = plane_model_hex

        cleaned_pcd_bg, plane_model_bg, normal_vector_bg, plane_pcd_bg, inlier_pcd_bg = vh.fit_plane(masked_bg_pcd, "Background")
        [a_bg, b_bg, c_bg, d_bg] = plane_model_bg

        cleaned_pcd_circle, plane_model_circle, normal_vector_circle, plane_pcd_circle, inlier_pcd_circle = vh.fit_plane(masked_circle_pcd, "Circle")
        [a_circle, b_circle, c_circle, d_circle] = plane_model_circle

        cleaned_pcd_drawn, plane_model_drawn, normal_vector_drawn, plane_pcd_drawn, inlier_pcd_drawn = vh.fit_plane(masked_drawn_pcd, "Drawn Rectangle")
        [a_drawn, b_drawn, c_drawn, d_drawn] = plane_model_drawn

        viz = self.get_parameter(VisionParametersKeys.VIZUALIZE_O3D).value

        grasp_hex = vh.estimate_grasp_pose_v2(cleaned_pcd_hex, plane_model_hex, plane_model_bg, normal_vector_hex, hexagon_box, _cur_pcd, masked_bg_pcd, H, W, plane_pcd_bg, label="Hexagon", visualize=viz)
        grasp_circle = vh.estimate_grasp_pose_v2(cleaned_pcd_circle, plane_model_circle, plane_model_bg, normal_vector_circle, circle_box, _cur_pcd, masked_bg_pcd, H, W, plane_pcd_bg, label="Circle", visualize=viz)
        pose_drawn = vh.estimate_grasp_pose_v2(cleaned_pcd_drawn, plane_model_drawn, plane_model_bg, normal_vector_drawn, rect_box, _cur_pcd, masked_bg_pcd, H, W, plane_pcd_bg, label="Drawn Rectangle", visualize=viz)

        if self.get_parameter(VisionParametersKeys.USE_SIM_HEIGHT).value:
            grasp_hex["obj_height"] = 30.0
            grasp_circle["obj_height"] = 20.0


        self.logger.info(f"Estimated grasp pose for hexagon: {grasp_hex['grasp_pose']}")
        self.logger.info(f"Estimated grasp pose for circle: {grasp_circle['grasp_pose']}")
        self.logger.info(f"Estimated pose for drawn rectangle: {pose_drawn['grasp_pose']}")

        # ── Zigzag pattern inside the drawn rectangle ──
        zigzag_pose_array, zigzag_path3d = vh.generate_zigzag_pose_array(
            box_2d=rect_box,
            cloud=_cur_pcd,
            normal_vector=normal_vector_bg,
            z_offset=-5.0,
            spacing=10.0,
        )


        self.logger.info(f"Generated zigzag pattern with {len(zigzag_pose_array.poses)} poses")

        cone_ref_pose: Pose = deepcopy(pose_drawn["grasp_pose"])
        cone_ref_pose.position.z += 40.0  # Offset the reference pose upwards by 40 mm in Z

        cone_poses: list[Pose] = vh.generate_cone_poses(
            cone_ref_pose,
            radius=35.0,
            n_poses=4,
            cone_apex_z=35.0,
        )

        self.logger.info(f"Generated {len(cone_poses)} cone poses around drawn rectangle offset by 35 mm in Z")



        if self.get_parameter(VisionParametersKeys.DEBUG_IMAGE_OUTPUT).value:
            debug_dir = "debug_outputs"
            os.makedirs(debug_dir, exist_ok=True)
            PILImage.fromarray(img_np).save(os.path.join(debug_dir, "segmentation_overlay.png"))
            PILImage.fromarray(mask_hex).save(os.path.join(debug_dir, "mask_hexagon.png"))
            PILImage.fromarray(mask_circle).save(os.path.join(debug_dir, "mask_circle.png"))
            PILImage.fromarray(mask_drawn).save(os.path.join(debug_dir, "mask_drawn.png"))

        # Build response
        response.img_masks_all = self.bridge.cv2_to_imgmsg(img_np, encoding="rgb8")
        response.img_background = self.bridge.cv2_to_imgmsg(np.array(img_bg.convert("RGB")), encoding="rgb8")
        response.img_hexagon = self.bridge.cv2_to_imgmsg(mask_hex, encoding="mono8")
        response.img_circle = self.bridge.cv2_to_imgmsg(mask_circle, encoding="mono8")
        response.img_drawn_rectangle = self.bridge.cv2_to_imgmsg(mask_drawn, encoding="mono8")
        response.cone_poses = cone_poses
        response.grasp_hexagon = self._grasp_dict_to_msg(grasp_hex, "hexagon")
        response.grasp_circle = self._grasp_dict_to_msg(grasp_circle, "circle")
        response.pose_rectangle = self._grasp_dict_to_msg(pose_drawn, "drawn_rectangle")

        response.zigzag_poses = zigzag_pose_array

        clean_path = zigzag_path3d[np.isfinite(zigzag_path3d).all(axis=1)]
        response.zigzag_path3d = [
            Point(x=float(p[0]), y=float(p[1]), z=float(p[2])) for p in clean_path
        ]

        # Inlier point clouds
        response.inlier_pcd_hexagon = vh.o3d_to_pointcloud2(inlier_pcd_hex)
        response.inlier_pcd_background = vh.o3d_to_pointcloud2(inlier_pcd_bg)
        response.inlier_pcd_circle = vh.o3d_to_pointcloud2(inlier_pcd_circle)
        response.inlier_pcd_drawn = vh.o3d_to_pointcloud2(inlier_pcd_drawn)

        # Plane models [a, b, c, d]
        response.plane_model_hexagon = list(plane_model_hex)
        response.plane_model_background = list(plane_model_bg)
        response.plane_model_circle = list(plane_model_circle)
        response.plane_model_drawn = list(plane_model_drawn)

        response.status = True
        response.message = "Vision processing completed successfully"

        self.current_pcd = None
        self.current_texture = None

        with self.sm_lock:
            self.lifecycle_sm.complete(message=response.message)
        


            



    @staticmethod
    def _mask_centroid(mask: np.ndarray):
        """Return (cx, cy) centroid of largest contour in a binary mask, or None."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        cnt = max(contours, key=cv2.contourArea)
        M = cv2.moments(cnt)
        if M['m00'] == 0:
            return None
        return (M['m10'] / M['m00'], M['m01'] / M['m00'])

    @staticmethod
    def _grasp_dict_to_msg(d: dict, label: str) -> GraspResult:
        """Convert estimate_grasp_pose_v2 result dict to a GraspResult message."""
        msg = GraspResult()
        msg.label = label
        msg.grasp_pose = d["grasp_pose"]
        msg.center_3d = d["center_3d"].tolist()
        msg.quaternion = d["quat"].tolist()
        msg.obj_height = float(d["obj_height"])
        msg.grasp_x = d["grasp_x"].tolist()
        msg.grasp_y = d["grasp_y"].tolist()
        msg.grasp_z = d["grasp_z"].tolist()
        msg.rot_matrix = d["rot_matrix"].flatten().tolist()
        msg.edge0 = float(d["edge0"])
        msg.edge1 = float(d["edge1"])
        return msg

    @handle_operation_errors
    def vision_processing_op2_cb(self, request: ProcessVisionSrv2.Request, response: ProcessVisionSrv2.Response):
        """Service callback for 6DoF pose estimation using CAD model matching.
        Pipeline is SAM3 background removal -> FPFH -> RANSAC -> ICP -> Pose
        """

        with self.sm_lock:
            self.lifecycle_sm.start_operation(message="Received request to process pointcloud op2")

        if not self.is_new_pcd_received or not self.is_new_txt_received:
            response.status = False
            response.message = "Waiting for both point cloud and texture data to be received"
            self.lifecycle_sm.complete(message=response.message)
            return response

        _cur_pcd = self.current_pcd          # organized (H, W, N)
        _cur_texture = self.current_texture   # PIL Image (gamma-corrected)
        H = _cur_texture.height
        W = _cur_texture.width

        # ── Resolve parameters (request overrides node params) ──
        cad_path = request.cad_model_path if request.cad_model_path else self.get_parameter(VisionParametersKeys.CAD_MODEL_PATH).value
        voxel_size = request.voxel_size if request.voxel_size > 0 else self.get_parameter(VisionParametersKeys.POSE_ESTIMATION_VOXEL_SIZE).value

        if not cad_path or not os.path.isfile(cad_path):
            response.status = False
            response.message = f"CAD model file not found: {cad_path}"
            with self.sm_lock:
                self.lifecycle_sm.complete(message=response.message)
            return response

        self.logger.info(f"Running pose estimation: cad={cad_path}, voxel_size={voxel_size}")

        # ── SAM3 background removal ──
        self.logger.info("Running SAM3 background removal...")

        inputs = self.mask_processor(
            images=[_cur_texture], text=["background"], return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        results = self.mask_processor.post_process_instance_segmentation(
            outputs,
            threshold=0.5,
            mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist(),
        )

        if len(results[0]["masks"]) < 1:
            raise NodeExceptionRecoverable("SAM3 found no background mask")

        bg_mask_2d = results[0]["masks"][0].detach().cpu().numpy().astype(bool)

        bg_mask_uint8 = (bg_mask_2d.astype(np.uint8) * 255)
        response.bg_mask_image = self.bridge.cv2_to_imgmsg(bg_mask_uint8, encoding="mono8")

        #Apply mask to organized point cloud
        pts_xyz = _cur_pcd[:, :, :3].astype(np.float64)
        zero_mask_2d = (pts_xyz == 0).all(axis=2)
        fg_mask_2d = ~(bg_mask_2d | zero_mask_2d)

        fg_pts = pts_xyz[fg_mask_2d]
        self.logger.info(f"SAM3: {H * W} -> {fg_pts.shape[0]} foreground points")

        scene_o3d = o3d.geometry.PointCloud()
        scene_o3d.points = o3d.utility.Vector3dVector(fg_pts)

        self.logger.info(f"Scene point cloud: {len(scene_o3d.points)} valid points")

        #Run pose estimation pipeline
        viz = self.get_parameter(VisionParametersKeys.VIZUALIZE_O3D).value
        nb_neighbors = self.get_parameter(VisionParametersKeys.POSE_ESTIMATION_NB_NEIGHBORS).value
        pose, icp_T, ransac_T, info = vh2.estimate_pose(
            cad_path, scene_o3d, voxel_size, nb_neighbors=nb_neighbors, visualize=viz,
        )

        # Build aligned CAD point cloud -source transformed by ICP result
        aligned_src = o3d.geometry.PointCloud(info["src"])
        aligned_src.transform(icp_T)

        #Build response
        response.estimated_pose = pose
        response.fitness = float(info["fitness"])
        response.rmse = float(info["rmse"])
        response.icp_transform = icp_T.flatten().tolist()
        response.ransac_transform = ransac_T.flatten().tolist()
        response.scene_pcd = vh.o3d_to_pointcloud2(info["tgt"])
        response.cad_pcd = vh.o3d_to_pointcloud2(info["src"])
        response.aligned_cad_pcd = vh.o3d_to_pointcloud2(aligned_src)

        self.logger.info(f"Pose estimation elapsed: {info['elapsed']:.2f}s")

        response.status = True
        response.message = (
            f"Pose estimation complete: fitness={info['fitness']:.4f}, "
            f"RMSE={info['rmse']:.4f} mm"
        )

        self.current_pcd = None
        self.current_texture = None

        with self.sm_lock:
            self.lifecycle_sm.complete(message=response.message)




    def initialize_node(self):
        try:
            login(HUGGINGFACE_API_KEY)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = Sam3Model.from_pretrained("facebook/sam3").to(self.device)
            self.mask_processor = Sam3Processor.from_pretrained("facebook/sam3")

        except Exception as e:
            raise NodeExceptionNonRecoverable(f"Error initializing node: {e}")


    
    def apply_parameters(self):
        pass

    def cleanup_resources(self):
        if self.mask_processor is not None:
            del self.mask_processor
        self.mask_processor = None
        if self.model is not None:
            del self.model
        self.model = None
        

def main(args=None):

    """Main entry point for this node"""

    rclpy.init(args=args)
    node = None
    executor = None
    
    try:
        # Initialize the node
        node = VisionNode()
        
        # Create multithreaded executor with 2 threads
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(node)
        
        # Spin the executor
        executor.spin()
        
    except KeyboardInterrupt:
        if node:
            node.logger.info("Keyboard interrupt received")
            
    except Exception as e:
        if node:
            node.logger.error(f"Unexpected error: {e}")
        else:
            print(f'Error during node initialization: {e}')
            
    finally:
        # Shutdown executor (stops spinning and waits for callbacks to finish)
        if executor:
            executor.shutdown(timeout_sec=5)
        
        # Update lifecycle state
        if node:
            with node.sm_lock:
                try:
                    node.lifecycle_sm.shutdown(
                        message="Node shutting down"
                    )
                except Exception as e:
                    node.logger.warning(
                        f"State transition failed during shutdown: {e}"
                    )
        
        # Cleanup node-specific resources
        if node:
            try:
                node.cleanup_resources()
            except Exception as e:
                node.logger.error(
                    f"Error during cleanup: {e}"
                )
        
        # Destroy the node
        if node:
            node.destroy_node()
        
        # Shutdown rclpy
        try:
            rclpy.shutdown()
        except Exception:
            pass  # rclpy may already be shut down


if __name__ == '__main__':
    main()