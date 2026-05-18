from typing import Optional
from fastapi.responses import RedirectResponse
from nicegui import ui, app
import asyncio
from core_pkg.nodes_async import AsyncINTRANode
from user_interface_pkg.pages.layout_page import create_main_layout
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from user_interface_pkg.constants import USER_MANAGEMENT_PAGE, SETTINGS_PAGE, SYSTEM_CONTROL_PAGE, OPERATIONS_PAGE, DASHBOARD_PAGE

def dashboard_page_factory(node: AsyncINTRANode):
    """
    Factory function to create dashboard page view.
    Returns a function with access to ROS2 node via closure.
    
    Args:
        node: ROS2 AsyncINTRANode node instance
    
    Returns:
        async dashboard page view function
    """

    async def create_dashboard_page() -> None:
        """
        Dashboard page with conditional content based on user permissions.
        User authentication is handled by middleware.
        """
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return

            # Create layout (header + sidebar) and get content area
            with create_main_layout(accessor=accessor_dto, active_page=DASHBOARD_PAGE.page):
                # Welcome message
                with ui.row().classes('w-full items-center mb-6'):
                    ui.icon(DASHBOARD_PAGE.icon).classes('text-4xl text-primary mr-3')
                    with ui.column().classes('gap-0'):
                        ui.label(f'Welcome back, {accessor_dto.login}!').classes('text-h4 mt-4')
                        ui.label('System Overview').classes('text-subtitle2 text-grey-7')

                # Status cards
                with ui.row().classes('w-full gap-4 mb-6'):
                    # ROS2 Status - visible to all
                    with ui.card().classes('flex-1 p-6 hover:shadow-lg transition-shadow'):
                        ui.icon('wifi').classes('text-5xl text-green mb-3')
                        ui.label('ROS2 Status').classes('text-h6 font-bold')
                        ui.label('Connected').classes('text-green font-semibold')
                        ui.separator().classes('my-3')
                        ui.label('All nodes active').classes('text-sm text-grey-6')

                    # Authentication - visible to all
                    with ui.card().classes('flex-1 p-6 hover:shadow-lg transition-shadow'):
                        ui.icon('security').classes('text-5xl text-blue mb-3')
                        ui.label('Authentication').classes('text-h6 font-bold')
                        ui.label('JWT Active').classes('text-blue font-semibold')
                        ui.separator().classes('my-3')
                        ui.label('Session valid').classes('text-sm text-grey-6')


                    if accessor_dto.permissions.allow_system_control:
                        with ui.card().classes('flex-1 p-6 hover:shadow-lg transition-shadow'):
                            ui.icon('precision_manufacturing').classes('text-5xl text-orange mb-3')
                            ui.label('System Status').classes('text-h6 font-bold')
                            ui.label('Ready').classes('text-orange font-semibold')
                            ui.separator().classes('my-3')
                            with ui.row().classes('gap-2'):
                                ui.button('Control', icon='settings_remote', 
                                        on_click=lambda: ui.navigate.to(SYSTEM_CONTROL_PAGE.route)).props('size=sm color=primary')

                # Quick Actions - conditional based on permissions
                with ui.card().classes('w-full p-6 mb-6'):
                    ui.label('Quick Actions').classes('text-h6 mb-4')
                    
                    with ui.row().classes('gap-3 flex-wrap'):
                        # View operations - if has permission
                        if accessor_dto.permissions.allow_manage_operations:
                            with ui.card().classes('p-4 cursor-pointer hover:bg-primary/10 transition-colors') as insp_card:
                                insp_card.on('click', lambda: ui.navigate.to(OPERATIONS_PAGE.route))
                                ui.icon(OPERATIONS_PAGE.icon).classes('text-3xl text-primary mb-2')
                                ui.label(OPERATIONS_PAGE.name).classes('font-bold')
                                ui.label('View operations').classes('text-sm text-grey-6')

                        # System Control - if has permission
                        if accessor_dto.permissions.allow_system_control:
                            with ui.card().classes('p-4 cursor-pointer hover:bg-primary/10 transition-colors') as system_card:
                                system_card.on('click', lambda: ui.navigate.to(SYSTEM_CONTROL_PAGE.route))
                                ui.icon(SYSTEM_CONTROL_PAGE.icon).classes('text-3xl text-orange mb-2')
                                ui.label(SYSTEM_CONTROL_PAGE.name).classes('font-bold')
                                ui.label('Manage system').classes('text-sm text-grey-6')
                        
                        # User Management - if has permission
                        if accessor_dto.permissions.allow_user_management:
                            with ui.card().classes('p-4 cursor-pointer hover:bg-primary/10 transition-colors') as users_card:
                                users_card.on('click', lambda: ui.navigate.to(USER_MANAGEMENT_PAGE.route))
                                ui.icon(USER_MANAGEMENT_PAGE.icon).classes('text-3xl text-blue mb-2')
                                ui.label(USER_MANAGEMENT_PAGE.name).classes('font-bold')
                                ui.label('Manage users').classes('text-sm text-grey-6')
                        
                        # Settings - always visible
                        with ui.card().classes('p-4 cursor-pointer hover:bg-primary/10 transition-colors') as settings_card:
                            settings_card.on('click', lambda: ui.navigate.to(SETTINGS_PAGE.route))
                            ui.icon(SETTINGS_PAGE.icon).classes('text-3xl text-grey-7 mb-2')
                            ui.label(SETTINGS_PAGE.name).classes('font-bold')
                            ui.label('User preferences').classes('text-sm text-grey-6')
    
        except Exception as e:
            node.logger.error(f'Dashboard page error: {e}')
            ui.notify('Failed to load dashboard', color='negative')
    
    return create_dashboard_page