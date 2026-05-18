"""
Robot Shadow Page
"""
from nicegui import ui
from functools import partial
from typing import Optional
from core_pkg.nodes_async import AsyncINTRANode
from core_pkg.settings import ROBOT_SHADOW_PATH
from user_interface_pkg.pages.layout_page import create_main_layout
from user_interface_pkg.constants import ROBOT_PAGE
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from core_pkg.exceptions import ServiceCallException
from user_interface_pkg.utils.urdf_scene import UrdfScene
from ament_index_python.packages import get_package_prefix
from sensor_msgs.msg import JointState

def robot_shadow_page_factory(node: AsyncINTRANode):
    """
    Factory function to create robot shadow page view.
    Returns a function with access to ROS2 node via closure.
    
    Args:
        node: ROS2 AsyncINTRANode node instance
    
    Returns:
        async robot shadow page view function
    """

    async def create_robot_shadow_page() -> None:
        """
        Robot shadow page for robot and camera settings.
        Only accessible to users with 'allow_system_config' permission.
        """
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return
            
            # Create layout (header + sidebar) and get content area
            with create_main_layout(accessor=accessor_dto, active_page=ROBOT_PAGE.page):
                
                node.start_joint_state_subscription()

                client = ui.context.client
                client.on_disconnect(node.stop_joint_state_subscription)

                with ui.card().classes('w-full mt-4 mb-6'):
                    urdf_path = ROBOT_SHADOW_PATH
                    scene = UrdfScene(urdf_path)
                    scene.show(material="#B0CEEB", scale_stls=1, background_color="#ffffff")
                    node.logger.info(f"joints states: {node.latest_joint_state}")
                   
                    follow_robot = ui.switch('Follow robot joint_states', value=True)

                    # Periodically update the scene's joint values based on the latest JointState message
                    def apply_joint_states_to_scene() -> None:
                        if not follow_robot.value:
                            return
                        js: JointState = getattr(node, "latest_joint_state", None)
                        if js is None:
                            return

                        name_to_pos = dict(zip(js.name, js.position))
                        for joint in scene.get_joint_names():
                            if joint in name_to_pos:
                                scene.set_axis_value(joint, float(name_to_pos[joint]))

                    ui.timer(0.2, apply_joint_states_to_scene)  # ~5 Hz




                    with ui.row().classes("w-full"):
                        for joint in scene.get_joint_names():
                            with ui.row().classes("w-1/5"):
                                ui.label(joint + ":")
                                x_min = scene.joint_pos_limits[joint]["min"]
                                x_max = scene.joint_pos_limits[joint]["max"]
                                n_slider_steps = 100
                                ui.slider(
                                    min=x_min, max=x_max, step=(x_max-x_min)/n_slider_steps, value=(x_max+x_min)/2
                                ).on(
                                    "update:model-value",
                                    lambda e, scene=scene, joint=joint: scene.set_axis_value(joint, e.args),
                                    throttle=0.1,
                                ).props(
                                    "label-always"
                                )
                                
                    scene.scene.move_camera(x=0.0, y=-1.2, z=1.2, look_at_x=0.5, look_at_y=0.0, look_at_z=0.8)

        except Exception as e:
            node.logger.error(f'Robot shadow page error: {e}')
            ui.notify('Failed to load robot shadow page', color='negative')
    
    return create_robot_shadow_page