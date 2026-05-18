#!/usr/bin/env python3
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose
from shape_msgs.msg import SolidPrimitive
from moveit_msgs.msg import CollisionObject, PlanningScene


class SpawnCollisionObjects(Node):
    def __init__(self):
        super().__init__('spawn_collision_objects')

        self.scene_pub = self.create_publisher(PlanningScene, '/planning_scene', 10)

        self.declare_parameter('wait_timeout_sec', 15.0)
        self._wait_timeout_sec = float(self.get_parameter('wait_timeout_sec').value)

        # Number of times to re-publish the scene to guard against race conditions
        # where move_group's PlanningSceneMonitor isn't fully ready yet.
        self.declare_parameter('publish_count', 3)
        self._publish_count = int(self.get_parameter('publish_count').value)
        self._publishes_remaining = self._publish_count

        self._start_monotonic = time.monotonic()
        self._waiting_logged = False
        self._scene_msg = None  # built lazily on first publish

        # Periodic check until move_group is ready, then publish multiple times.
        self.timer = self.create_timer(1.0, self._timer_callback)
        self.published = False

    def _timer_callback(self):
        if self.published:
            return

        # While still waiting for first subscriber, don't publish yet
        if self._publishes_remaining == self._publish_count:
            subs = 0
            try:
                subs = self.scene_pub.get_subscription_count()
            except Exception:
                subs = 0

            if subs == 0:
                elapsed = time.monotonic() - self._start_monotonic
                if not self._waiting_logged and self._wait_timeout_sec > 0.0:
                    self.get_logger().info('Waiting for move_group to subscribe to /planning_scene …')
                    self._waiting_logged = True

                if elapsed < self._wait_timeout_sec:
                    return

                if self._wait_timeout_sec > 0.0:
                    self.get_logger().warn(
                        f'Timeout ({self._wait_timeout_sec:.1f}s) waiting for /planning_scene subscriber; publishing anyway.'
                    )

        # Build scene message once, then re-publish it
        if self._scene_msg is None:
            self._scene_msg = self._build_scene()

        self.scene_pub.publish(self._scene_msg)
        self._publishes_remaining -= 1

        if self._publishes_remaining <= 0:
            self.get_logger().info(
                f'Published {len(self._scene_msg.world.collision_objects)} collision object(s) '
                f'to Planning Scene ({self._publish_count}x to ensure delivery).'
            )
            self.published = True
            try:
                self.timer.cancel()
            except Exception:
                pass
        elif self._publishes_remaining == self._publish_count - 1:
            self.get_logger().info(
                f'Publishing {len(self._scene_msg.world.collision_objects)} collision object(s) '
                f'to Planning Scene (will repeat {self._publishes_remaining} more time(s))…'
            )

    def _build_scene(self):

        scene_msg = PlanningScene()
        scene_msg.is_diff = True

        # --- gofa Table ---
        gofa_table = self._make_box(
            obj_id='gofa_table',
            frame_id='world',
            dimensions=[1.15, 0.80, 0.599], 
            position=[-0.225, -0.8/2, 0.0],
            anchor=('min', 'min', 'min'),
        )
        scene_msg.world.collision_objects.append(gofa_table)

        # --- Table ---
        table = self._make_box(
            obj_id='table_top',
            frame_id='table',
            dimensions=[1.0, 1.0, 0.15], 
            position=[0.0, 0.0, -0.15],
            anchor=('min', 'min', 'min'),
        )

        # --- Table legs (4x) ---

        leg_w = 0.1
        leg_floor_z = -0.83


        leg_corners_xy = [
            (0.0, 0.0),
            (1 - leg_w, 0.0),
            (0.0, 1 - leg_w),
            (1 - leg_w, 1 - leg_w),
        ]
        table_legs = [
            self._make_box(
                obj_id=f'table_leg_{i}',
                frame_id='table',
                dimensions=[leg_w, leg_w, 0.83 - 0.15],
                position=[x, y, leg_floor_z],
                anchor=('min', 'min', 'min'),
            )
            for i, (x, y) in enumerate(leg_corners_xy)
        ]

        scene_msg.world.collision_objects.append(table)
        for leg in table_legs:
            scene_msg.world.collision_objects.append(leg)


        #frame pillars
        pillar_w = 0.05
        pillar_floor_z = -0.2-0.11
        pillar_height = 1.25
        pillar_corners_xy = [
            (-0.05, 0.75),
            (1 , 0.75)]
        
        frame_pillars = [
            self._make_box(
                obj_id=f'frame_pillar_{i}',
                frame_id='table',
                dimensions=[pillar_w, pillar_w, pillar_height],
                position=[x, y, pillar_floor_z],
                anchor=('min', 'min', 'min'),
            )
            for i, (x, y) in enumerate(pillar_corners_xy)
        ]
        for pillar in frame_pillars:
            scene_msg.world.collision_objects.append(pillar)


        #top frame box
        frame_box = self._make_box(
            obj_id='frame_top_box',
            frame_id='table',
            dimensions=[1.1, 0.60, 0.1],
            position=[-0.05, 0.85, 0.98-0.11],
            anchor=('min', 'max', 'min'),
        )
        scene_msg.world.collision_objects.append(frame_box)

        #tabule box
        tabule_box = self._make_box(
            obj_id='tabule_box',
            frame_id='table',
            dimensions=[0.1, 3.0, 2.2], 
            position=[1.34, -1.0, -0.8],
            anchor=('min', 'min', 'min'),
        )
        scene_msg.world.collision_objects.append(tabule_box)

        #left box
        left_box = self._make_box(
            obj_id='left_box',
            frame_id='table',
            dimensions=[0.1, 2.0, 2.2], 
            position=[-0.46, -0.35, -0.8],
            anchor=('min', 'min', 'min'),
        )
        scene_msg.world.collision_objects.append(left_box)

        #top box
        top_box = self._make_box(
            obj_id='top_box',
            frame_id='table',
            dimensions=[1.7, 2.0, 0.10],
            position=[-0.36, -0.35, 1.4],
            anchor=('min', 'min', 'min'),
        )
        scene_msg.world.collision_objects.append(top_box)

        #back box
        back_box = self._make_box(
            obj_id='back_box',
            frame_id='table',
            dimensions=[1.7, 0.1, 2.2],
            position=[-0.36, 0.75, -0.8],
            anchor=('min', 'min', 'min'),
        )
        scene_msg.world.collision_objects.append(back_box)



        #top frame box
        camera_box = self._make_box(
            obj_id='camera_box',
            frame_id='table',
            dimensions=[0.45, 0.20, 0.2],
            position=[0.28, 0.2, 0.8-0.11],
            anchor=('min', 'min', 'min'),
        )
        scene_msg.world.collision_objects.append(camera_box)


        #top yumi box
        yumi_box = self._make_box(
            obj_id='yumi_box',
            frame_id='table',
            dimensions=[0.5, 0.50, 0.8],
            position=[0.25, 0.55, 0.0],
            anchor=('min', 'min', 'min'),
        )
        scene_msg.world.collision_objects.append(yumi_box)

        #3 dock boxes
        dock_box_dims = [0.2, 0.12, 0.04]
        
        dock_box1 = self._make_box(
            obj_id='dock_box_1',
            frame_id='stationdock1',
            dimensions=dock_box_dims,
            position=[0.0, 0.0, 0.0],
            anchor=('center', 'center', 'center'),
        )
        scene_msg.world.collision_objects.append(dock_box1)


        dock_box2 = self._make_box(
            obj_id='dock_box_2',
            frame_id='stationdock2',
            dimensions=dock_box_dims,
            position=[0.0, 0.0, 0.0],
            anchor=('center', 'center', 'center'),
        )

        scene_msg.world.collision_objects.append(dock_box2)

        dock_box3 = self._make_box(
            obj_id='dock_box_3',
            frame_id='stationdock3',
            dimensions=dock_box_dims,
            position=[0.0, 0.0, 0.0],
            anchor=('center', 'center', 'center'),
        )
        scene_msg.world.collision_objects.append(dock_box3)

        return scene_msg

    # ------------------------------------------------------------------
    @staticmethod
    def _anchored(value: float, dimension: float, anchor: str) -> float:
        if anchor == 'center':
            return value
        half = dimension / 2.0
        if anchor == 'min':
            return value + half
        if anchor == 'max':
            return value - half
        raise ValueError("anchor must be one of: 'min', 'center', 'max'")

    @staticmethod
    def _make_box(obj_id: str, frame_id: str,
                  dimensions: list[float], position: list[float],
                  orientation: list[float] | None = None,
                  anchor: tuple[str, str, str] = ('center', 'center', 'center')) -> CollisionObject:
        """Helper to create a BOX CollisionObject.

        `position` is interpreted according to `anchor` per axis:
        - 'center': position is the box center (MoveIt default)
        - 'min':    position is the minimum corner on that axis
        - 'max':    position is the maximum corner on that axis

        Example: bottom-left corner (ROS: x forward, y left, z up) often maps to
        `anchor=('min','max','min')` depending on how you define "left" in your scene.
        """
        co = CollisionObject()
        co.header.frame_id = frame_id
        co.id = obj_id

        prim = SolidPrimitive()
        prim.type = SolidPrimitive.BOX
        prim.dimensions = dimensions

        pose = Pose()
        pose.position.x = SpawnCollisionObjects._anchored(position[0], dimensions[0], anchor[0])
        pose.position.y = SpawnCollisionObjects._anchored(position[1], dimensions[1], anchor[1])
        pose.position.z = SpawnCollisionObjects._anchored(position[2], dimensions[2], anchor[2])
        if orientation:
            pose.orientation.x = orientation[0]
            pose.orientation.y = orientation[1]
            pose.orientation.z = orientation[2]
            pose.orientation.w = orientation[3]
        else:
            pose.orientation.w = 1.0

        co.primitives.append(prim)
        co.primitive_poses.append(pose)
        co.operation = CollisionObject.ADD
        return co


def main():
    rclpy.init()
    node = SpawnCollisionObjects()
    while rclpy.ok() and not node.published:
        rclpy.spin_once(node, timeout_sec=0.2)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
