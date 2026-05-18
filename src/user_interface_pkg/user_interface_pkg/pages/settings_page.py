from nicegui import ui, app
import asyncio
from typing import Optional
from core_pkg.nodes_async import AsyncINTRANode
from user_interface_pkg.pages.layout_page import create_main_layout
from core_pkg.exceptions import AuthenticationError, NotFoundError, ValidationError
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from core_pkg.dbmodels.schemas import AccessorDTO
from user_interface_pkg.constants import SETTINGS_PAGE
from user_interface_pkg.utils.ui_helpers import render_password_requirements
from user_interface_pkg.utils.ui_helpers import change_password_ui

def settings_page_factory(node: AsyncINTRANode):
    """
    Factory function to create settings page view.
    Returns a function with access to ROS2 node via closure.
    
    Args:
        node: ROS2 AsyncINTRANode node instance
    
    Returns:
        async settings page view function
    """

    async def create_settings_page() -> None:
        """
        Settings page with conditional sections based on user permissions.
        User authentication is handled by middleware.
        """
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return

            # Create layout (header + sidebar) and get content area
            with create_main_layout(accessor=accessor_dto, active_page=SETTINGS_PAGE.page):
                # Page-specific content
                with ui.row().classes('w-full items-center mb-6'):
                    ui.icon(SETTINGS_PAGE.icon).classes('text-4xl text-primary mr-3')
                    with ui.column().classes('gap-0'):
                        ui.label(SETTINGS_PAGE.name).classes('text-h4 mt-4')
                        ui.label('Configure user settings and preferences').classes('text-subtitle2 text-grey-7')
                
                with ui.card().classes('w-full p-6 mb-4'):
                    ui.label('User Settings').classes('text-h6 mb-4')
                    
                    # Display current user info
                    with ui.row().classes('w-full mb-4 items-center'):
                        ui.icon('account_circle').classes('text-4xl text-primary mr-2')
                        with ui.column().classes('gap-0'):
                            ui.label(f'Logged in as: {accessor_dto.login}').classes('text-subtitle1 font-bold')
                            ui.label(f'User ID: {accessor_dto.accessor_id}').classes('text-caption text-grey-6')
                    
                    ui.separator().classes('my-4')
                    
                    # Change Password Section
                    with ui.expansion('Change Password', icon='lock').classes('w-full'):
                        with ui.column().classes('gap-4 p-4'):
                            # Password inputs
                            current_password_input = ui.input(
                                'Current Password', 
                                password=True,
                                password_toggle_button=True
                            ).props('outlined').classes('w-full')
                            
                            new_password_input = ui.input(
                                'New Password', 
                                password=True,
                                password_toggle_button=True
                            ).props('outlined').classes('w-full')
                            
                            confirm_password_input = ui.input(
                                'Confirm New Password', 
                                password=True,
                                password_toggle_button=True
                            ).props('outlined').classes('w-full')
                            
                            # Password requirements info
                            render_password_requirements()

                            async def change_password_handler():
                                await change_password_ui(
                                    node,
                                    accessor_dto,
                                    current_password_input,
                                    new_password_input,
                                    confirm_password_input,
                                    change_pw_button
                                )
                            
                            # Change password button
                            with ui.row().classes('w-full justify-end'):
                                change_pw_button = ui.button(
                                    'Change Password',
                                    icon='lock_reset',
                                    on_click=change_password_handler
                                ).props('color=primary')

        except Exception as e:
            node.logger.error(f'Settings page error: {e}')
            ui.notify('Failed to load settings', color='negative')
    
    return create_settings_page