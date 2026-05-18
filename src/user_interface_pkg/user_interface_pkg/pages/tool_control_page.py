"""
Tool Control Page - Swap collision grippers in RViz.
Buttons are only enabled when coordinator node is idle.
"""
from nicegui import ui
from functools import partial
from user_interface_pkg.constants import TOOL_CONTROLLER_PAGE, CALL_TIMEOUT_SEC
from user_interface_pkg.pages.layout_page import create_main_layout
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from core_pkg.nodes_async import AsyncINTRANode
from core_pkg.systemconstants import (
    StateKeys, NodeStates, CoordinatorConstants, ToolControllerConstants,
)
from interface_pkg.srv import RobotRequestSrv, NodeStateSrv

# Tool definitions: (tool_id, display_label, icon, color)
TOOLS = [
    (ToolControllerConstants.ToolNames.TOOL_1, "Tool 1", "build", "primary"),
    (ToolControllerConstants.ToolNames.TOOL_2, "Tool 2", "build", "secondary"),
    (ToolControllerConstants.ToolNames.TOOL_3, "Tool 3", "build", "accent"),
]


def tool_controller_page_factory(node: AsyncINTRANode):
    async def create_tool_controller_page() -> None:
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return

            coordinator_idle = False
            tool_buttons: list[ui.button] = []

            async def check_coordinator_state() -> bool:
                """Check whether coordinator is idle, update button states."""
                nonlocal coordinator_idle
                try:
                    response: NodeStateSrv.Response = await node.call_service_async(
                        node.coordinator_clients.get_state_cli,
                        NodeStateSrv.Request(),
                        timeout_sec=CALL_TIMEOUT_SEC,
                    )
                    coordinator_idle = response.state == NodeStates.IDLE.value
                    state_label.set_text(response.state)
                    state_desc_label.set_text(response.description)
                except Exception as e:
                    coordinator_idle = False
                    state_label.set_text("unreachable")
                    state_desc_label.set_text(str(e))
                    node.logger.error(f"Failed to check coordinator state: {e}")

                for btn in tool_buttons:
                    if coordinator_idle:
                        btn.enable()
                    else:
                        btn.disable()
                return coordinator_idle

            async def swap_tool(tool_id: str):
                """Call swap_tool service on tool controller node."""
                is_idle = await check_coordinator_state()
                if not is_idle:
                    ui.notify("Coordinator is not idle – cannot change tool", type="warning")
                    return
                try:
                    ui.notify(f"Swapping to {tool_id}…", type="info")
                    request = RobotRequestSrv.Request()
                    request.command = tool_id
                    response: RobotRequestSrv.Response = await node.call_service_async(
                        node.tool_clients.swap_tool_cli,
                        request,
                        timeout_sec=CALL_TIMEOUT_SEC,
                    )
                    if response.status:
                        ui.notify(f"Tool swap OK: {response.message}", type="positive")
                    else:
                        ui.notify(f"Tool swap failed: {response.message}", type="negative")
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")
                    node.logger.error(f"swap_tool error: {e}")

            async def detach_tool():
                """Detach current tool from RViz."""
                is_idle = await check_coordinator_state()
                if not is_idle:
                    ui.notify("Coordinator is not idle – cannot detach tool", type="warning")
                    return
                try:
                    ui.notify("Detaching current tool…", type="info")
                    request = RobotRequestSrv.Request()
                    request.command = ToolControllerConstants.ToolNames.DETACH
                    response: RobotRequestSrv.Response = await node.call_service_async(
                        node.tool_clients.swap_tool_cli,
                        request,
                        timeout_sec=CALL_TIMEOUT_SEC,
                    )
                    if response.status:
                        ui.notify(f"Detach OK: {response.message}", type="positive")
                    else:
                        ui.notify(f"Detach failed: {response.message}", type="negative")
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")
                    node.logger.error(f"detach_tool error: {e}")
            with create_main_layout(accessor=accessor_dto, active_page=TOOL_CONTROLLER_PAGE.page):
                with ui.row().classes('w-full items-center justify-between mb-6'):
                    with ui.row().classes('items-center'):
                        ui.icon(TOOL_CONTROLLER_PAGE.icon).classes('text-4xl text-primary mr-3')
                        with ui.column().classes('gap-0'):
                            ui.label(TOOL_CONTROLLER_PAGE.name).classes('text-h4 mt-4')
                            ui.label('Swap collision grippers in RViz (MoveIt planning scene)').classes('text-subtitle2 text-grey-7')

                # Coordinator state card
                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Coordinator State').classes('text-h6')
                        ui.button('Refresh', icon='refresh',
                                  on_click=check_coordinator_state
                        ).props('outline color=primary')
                    with ui.row().classes('w-full items-center gap-4'):
                        ui.label('State:').classes('text-subtitle2 text-grey-7')
                        state_label = ui.label('Unknown').classes('text-body2 text-primary')
                    with ui.row().classes('w-full items-center gap-4 mt-2'):
                        ui.label('Description:').classes('text-subtitle2 text-grey-7')
                        state_desc_label = ui.label('').classes('text-body2')

                # Tool buttons
                with ui.card().classes('w-full p-6 mb-4'):
                    ui.label('Tool Selection').classes('text-h6 mb-4')
                    ui.label(
                        'Attach a collision gripper to the robot flange in the MoveIt planning scene. '
                        'Buttons are enabled only when the coordinator node is idle.'
                    ).classes('text-body2 text-grey-7 mb-4')

                    with ui.grid(columns=3).classes('w-full gap-4'):
                        for tool_id, label, icon, color in TOOLS:
                            btn = ui.button(
                                f'Attach {label}', icon=icon,
                                on_click=partial(swap_tool, tool_id),
                            ).props(f'color={color}').classes('w-full')
                            btn.disable()
                            tool_buttons.append(btn)

                        for tool_id, label, icon, color in TOOLS:
                            btn = ui.button(
                                f'Detach {label}', icon='delete',
                                on_click=detach_tool,
                            ).props('color=warning').classes('w-full')
                            btn.disable()
                            tool_buttons.append(btn)

                # Help card
                with ui.card().classes('w-full p-6 bg-blue-1'):
                    with ui.row().classes('items-start gap-3'):
                        ui.icon('info').classes('text-primary text-2xl')
                        with ui.column().classes('gap-2'):
                            ui.label('Tool Controller Guide').classes('text-subtitle1 font-bold')
                            ui.label('1. Click "Refresh" to check coordinator state').classes('text-body2')
                            ui.label('2. Buttons become active when coordinator is idle').classes('text-body2')
                            ui.label('3. "Attach" swaps the collision model on the flange in RViz').classes('text-body2')
                            ui.label('4. "Detach" removes the current collision model from the flange').classes('text-body2')

                # Initial state check
                await check_coordinator_state()

        except Exception as e:
            node.logger.error(f'Tool controller page error: {e}')
            ui.notify('Failed to load tool controller page', color='negative')

    return create_tool_controller_page
