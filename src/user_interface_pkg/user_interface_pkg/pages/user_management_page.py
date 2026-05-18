from nicegui import ui, app
import asyncio
from typing import Optional
from core_pkg.nodes_async import AsyncINTRANode
from user_interface_pkg.pages.layout_page import create_main_layout
from core_pkg.exceptions import AuthenticationError, NotFoundError, ValidationError
from core_pkg.dbservices_async.accessor_async import get_accessor_by_id_async, get_all_roles_async, toggle_accessor_activation_async
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from core_pkg.dbmodels.schemas import AccessorDTO, RoleDTO, AccessorDTOkeys
from user_interface_pkg.constants import USER_MANAGEMENT_PAGE, ALL_ROLES_OPTION
from user_interface_pkg.utils.ui_helpers import (
    refresh_accessor_table, render_password_requirements, reset_password_ui, update_accessor_ui,
    show_add_user_dialog, show_toggle_activate_user_dialog, show_edit_user_dialog, show_reset_password_dialog,
    render_permissions_list, show_role_users_dialog, show_manage_permissions_dialog, show_create_role_dialog, show_edit_role_dialog)
from functools import partial

def user_management_page_factory(node: AsyncINTRANode):
    """
    Factory function to create user management page view.
    Returns a function with access to ROS2 node via closure.
    
    Args:
        node: ROS2 AsyncINTRANode node instance
    
    Returns:
        async user management page view function
    """

    async def create_user_management_page() -> None:
        """
        User Management page for managing users and roles.
        Restricted to admin users only (handled by middleware).
        """
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return

            async def get_current_roles() -> list[RoleDTO]:
                """Get current roles from database"""
                return await get_all_roles_async()

            def get_role_dto_by_name(role_name: str, role_dtos: list[RoleDTO]) -> Optional[RoleDTO]:
                """Get RoleDTO by name from a list of RoleDTOs"""
                if role_name == ALL_ROLES_OPTION:
                    return None
                for role in role_dtos:
                    if role.name == role_name:
                        return role
                return None
            
            role_dtos = await get_current_roles()

            async def on_roles_changed():
                """Called whenever roles are added/edited/deleted"""
                nonlocal role_dtos
                role_dtos = await get_all_roles_async()
                
                # Update all dependent UI
                role_filter_select.options = create_role_options(role_dtos)
                role_filter_select.update()
                
                await refresh_role_cards()
                await refresh_accessor_table_handler()

            async def refresh_accessor_table_handler():
                selected_role_name = role_filter_select.value
                role_dto = get_role_dto_by_name(selected_role_name, role_dtos)
                print(f"Selected role for filtering: {role_dto.name if role_dto else ALL_ROLES_OPTION}")
                search_input_value = search_input.value
                print("Accessor table refresh triggered.")
                await refresh_accessor_table(accessors_table, role_dto, search_input_value)

            def create_role_options(role_dtos: list[RoleDTO]) -> list[str]:
                """Create role options for the select input"""
                options = [role.name for role in role_dtos]
                options.insert(0, ALL_ROLES_OPTION)
                return options

            # Create layout (header + sidebar) and get content area
            with create_main_layout(accessor=accessor_dto, active_page=USER_MANAGEMENT_PAGE.page):
                # Page header
                with ui.row().classes('w-full items-center mb-6'):
                    ui.icon(USER_MANAGEMENT_PAGE.icon).classes('text-4xl text-primary mr-3')
                    with ui.column().classes('gap-0'):
                        ui.label(USER_MANAGEMENT_PAGE.name).classes('text-h4 mt-4')
                        ui.label('Manage users and roles').classes('text-subtitle2 text-grey-7')
                with ui.card().classes('w-full p-6 mb-4'):
                    ui.label('User Management').classes('text-h6 mb-4')
                    
                    # Action buttons
                    with ui.row().classes('w-full mb-4 gap-2'):
                        add_user_button = ui.button('Add User', icon='person_add', color='primary')
                        ui.button('Refresh', icon='refresh', color='secondary', on_click=refresh_accessor_table_handler)
                        

                        async def add_user_handler():
                            new_user = await show_add_user_dialog(node)
                            if not new_user:
                                return
                            await refresh_accessor_table_handler()

                        add_user_button.on_click(add_user_handler)
                    
                    # Search and filter
                    with ui.row().classes('w-full mb-4 gap-2 items-stretch'):
                        
                        
                        search_input = ui.input(placeholder='Search users...').props('outlined dense clearable').classes('flex-grow h-12')
                        search_input.on('keydown.enter', refresh_accessor_table_handler)

                        role_filter_select = ui.select(
                            options=create_role_options(role_dtos),
                            value=ALL_ROLES_OPTION,
                        ).props('outlined dense').classes('w-48 h-12')

                        role_filter_select.on('update:model-value', refresh_accessor_table_handler)
                    
                    # Users table definition
                    accessors_columns = [
                        {'name': 'id', 'label': 'ID', 'field': AccessorDTOkeys.ACCESSOR_ID, 'required': True, 'sortable': True, 'align': 'left'},
                        {'name': 'login', 'label': 'Login', 'field': AccessorDTOkeys.LOGIN, 'sortable': True, 'align': 'left'},
                        {'name': 'name', 'label': 'Name', 'field': AccessorDTOkeys.NAME, 'sortable': True, 'align': 'left'},
                        {'name': 'role', 'label': 'Role', 'field': AccessorDTOkeys.ROLE_NAME, 'sortable': True, 'align': 'left'},
                        {'name': 'created_at', 'label': 'Created', 'field': AccessorDTOkeys.CREATED_AT, 'sortable': True, 'align': 'center'},
                        {'name': 'active', 'label': 'Status', 'field': AccessorDTOkeys.ACTIVE, 'sortable': True, 'align': 'left'},
                        {'name': 'actions', 'label': 'Actions', 'field': 'actions', 'align': 'right'},
                    ]
                    
                    accessors_table = ui.table(
                        columns=accessors_columns,
                        rows=[],
                        pagination=5,
                        # selection='single'
                    ).classes('w-full')

                    await refresh_accessor_table_handler()

                    # Add actions slot with buttons
                    accessors_table.add_slot('body-cell-actions', '''
                        <q-td key="actions" :props="props" class="text-center">
                            <q-btn flat round color="primary" icon="edit" size="sm" class="q-mr-xs" @click="$parent.$emit('edit', props.row)">
                                <q-tooltip>Edit User</q-tooltip>
                            </q-btn>
                            <q-btn flat round color="warning" icon="lock_reset" size="sm" class="q-mr-xs" @click="$parent.$emit('reset_password', props.row)">
                                <q-tooltip>Reset Password</q-tooltip>
                            </q-btn>
                            <q-btn flat round color="negative" icon="person_off" size="sm" @click="$parent.$emit('deactivate', props.row)">
                                <q-tooltip>Deactivate (Activate) User</q-tooltip>
                            </q-btn>
                        </q-td>
                    ''')

                    async def reset_password_handler(editing_accessor_dto: AccessorDTO, e):
                        """Handle the Reset Password action."""
                        edited_accessor_dto: AccessorDTO = await get_accessor_by_id_async(e.args[AccessorDTOkeys.ACCESSOR_ID])
                        if not editing_accessor_dto.accessor_id == edited_accessor_dto.accessor_id:

                            await show_reset_password_dialog(node, editing_accessor_dto, edited_accessor_dto)

                        else:
                            ui.notify("You cannot reset your own password.", color='negative')
                            return

                    async def toggle_activate_user_handler(editing_accessor_dto: AccessorDTO, e):
                        """Handle the Deactivate User action."""
                        edited_accessor_dto: AccessorDTO = await get_accessor_by_id_async(e.args[AccessorDTOkeys.ACCESSOR_ID])
                        if not editing_accessor_dto.accessor_id == edited_accessor_dto.accessor_id:

                            success = await show_toggle_activate_user_dialog(edited_accessor_dto)
                            if success:
                                await toggle_accessor_activation_async(edited_accessor_dto.accessor_id)
                                await refresh_accessor_table_handler()

                        else:
                            ui.notify("You cannot deactivate/activate your own account.", color='negative')
                            return

                    async def edit_user_handler(editing_accessor_dto: AccessorDTO, e):
                        edited_accessor: AccessorDTO = await get_accessor_by_id_async(
                            e.args[AccessorDTOkeys.ACCESSOR_ID]
                        )

                        saved = await show_edit_user_dialog(node, editing_accessor_dto, edited_accessor)

                        if saved:
                            await refresh_accessor_table_handler()

                    # Attach event listeners to the table
                    accessors_table.on('edit', partial(edit_user_handler, accessor_dto))
                    accessors_table.on('reset_password', partial(reset_password_handler, accessor_dto))
                    accessors_table.on('deactivate', partial(toggle_activate_user_handler, accessor_dto))
                with ui.card().classes('w-full p-6 mb-4'):
                    ui.label('Role Management').classes('text-h6 mb-4')
                    
                    # Action buttons
                    with ui.row().classes('w-full mb-4 gap-2'):
                        add_role_button = ui.button('Add Role', icon='add_moderator', color='primary')
                        refresh_button_role_table = ui.button('Refresh', icon='refresh', color='secondary')

                        async def add_role_handler():
                            created = await show_create_role_dialog()
                            if created:
                                await on_roles_changed()

                        add_role_button.on_click(add_role_handler)

                    # Container for dynamic role cards
                    roles_container = ui.column().classes('w-full gap-3')

                    def render_role_card(role: RoleDTO):
                        """Render a single role card in the roles container."""
                        with ui.card().classes('flex-1 p-4 bg-grey-50 min-w-[260px]'):
                            with ui.row().classes('w-full items-center justify-between'):
                                with ui.column().classes('gap-0'):
                                    ui.label(role.name).classes('text-subtitle1 font-bold')
                                    ui.label(role.description).classes('text-caption text-grey-600')
                                users_chip = ui.chip(role.user_count, color='primary').props('outline')
                                with users_chip:
                                    ui.tooltip(f"{role.user_count} user{'s' if role.user_count != 1 else ''} in role")

                            # Permissions preview
                            with ui.column().classes('w-full mt-2 gap-1'):
                                ui.label('Permissions:').classes('text-caption font-bold')
                                render_permissions_list(role.permissions, show_badge=False)

                            with ui.row().classes('w-full mt-2 gap-1'):

                                async def on_permissions():
                                    saved = await show_manage_permissions_dialog(role)
                                    if saved:
                                        await refresh_role_cards()
                                async def on_edit_role():
                                    changed = await show_edit_role_dialog(role)
                                    if changed:
                                        await on_roles_changed()

      

                                ui.button('Edit', icon='edit', color='primary', on_click=on_edit_role).props('flat')
                                ui.button('Users', icon='group', color='primary', on_click=partial(show_role_users_dialog, role)).props('flat')
                                ui.button('Manage permissions', icon='security', color='primary', on_click=on_permissions).props('flat')

                    async def refresh_role_cards():
                        """Refresh the role cards in the roles container."""
                        roles_container.clear()
                        roles: list[RoleDTO] = await get_all_roles_async()
                        sorted_roles = sorted(roles, key=lambda r: r.name.lower())
                        n = len(sorted_roles)
                        if n == 0:
                            with roles_container:
                                ui.label('No roles defined yet.').classes('text-caption text-grey-7')
                            return
                        
                        rows = (n + 1) // 2  # ceil(n/2)

                        with roles_container:
                            for row_index in range(rows):
                                with ui.row().classes('w-full gap-4'):
                                    left_index = row_index
                                    right_index = row_index + rows

                                    if left_index < n:
                                        render_role_card(sorted_roles[left_index])

                                    if right_index < n:
                                        render_role_card(sorted_roles[right_index])

                    # Initial load of role cards
                    await refresh_role_cards()

                    # Refresh button
                    refresh_button_role_table.on_click(refresh_role_cards)
                    
        except Exception as e:
            node.logger.error(f'User management page error: {e}')
            ui.notify('Failed to load user management page', color='negative')
    
    return create_user_management_page
