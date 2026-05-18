from nicegui import ui
from core_pkg.dbmodels.schemas import AccessorDTO, AccessorDTOkeys, RoleDTO
from core_pkg.dbservices_async.accessor_async import (
    change_accessor_password_async, get_all_accessors_async, 
    reset_accessor_password_async, update_accessor_login_async, update_accessor_name_description_async, 
    get_role_by_name_async, update_accessor_role_async, get_all_roles_async, create_new_accessor_async, 
    update_role_permissions_async, create_role_async, delete_role_async, update_role_async)
import asyncio

from core_pkg.exceptions import AuthenticationError, NotFoundError, ValidationError
from core_pkg.dbservices import validate_login_format, validate_name_format, validate_description_format
from core_pkg.nodes_async import AsyncINTRANode
from typing import Optional, Dict
from core_pkg.systemconstants import DatabaseConstants
from core_pkg.dbmodels.schemas import PERM_META, PermMetaKeys, Permissions


def render_password_requirements() -> None:
    """Render password requirements info section."""
    with ui.row().classes('w-full gap-2 items-start mt-1 mb-4'):
        ui.icon('info').classes('text-blue text-sm')
        with ui.column().classes('gap-0'):
            ui.label('Password Requirements:').classes('text-caption text-grey-7')
            ui.label(f'• Minimum {DatabaseConstants.MIN_PASSWORD_LENGTH} characters').classes('text-caption text-grey-6')
            ui.label(f'• At least one uppercase letter').classes('text-caption text-grey-6')
            ui.label(f'• At least one lowercase letter').classes('text-caption text-grey-6')
            ui.label(f'• At least one number').classes('text-caption text-grey-6')

def render_login_requirements() -> None:
    """Render login requirements info section."""
    with ui.row().classes('w-full gap-2 items-start mt-1 mb-4'):
        ui.icon('info').classes('text-blue text-sm')
        with ui.column().classes('gap-0'):
            ui.label('Login Requirements:').classes('text-caption text-grey-7')
            ui.label(f'• Between {DatabaseConstants.MIN_LOGIN_LENGTH} and {DatabaseConstants.MAX_LOGIN_LENGTH} characters').classes('text-caption text-grey-6')
            ui.label(f'• Only lowercase letters (a-z) and digits (0-9)').classes('text-caption text-grey-6')
            ui.label(f'• No spaces or special characters').classes('text-caption text-grey-6')

def render_role_name_requirements() -> None:
    """Render role name requirements info section."""
    with ui.row().classes('w-full gap-2 items-start mt-1 mb-4'):
        ui.icon('info').classes('text-blue text-sm')
        with ui.column().classes('gap-0'):
            ui.label('Role Name Requirements:').classes('text-caption text-grey-7')
            ui.label(f'• Between {DatabaseConstants.MIN_LOGIN_LENGTH} and {DatabaseConstants.MAX_LOGIN_LENGTH} characters').classes('text-caption text-grey-6')
            ui.label(f'• No spaces, digits or special characters').classes('text-caption text-grey-6')


async def change_password_ui(node: AsyncINTRANode, accessor_dto: AccessorDTO, current_password_input: ui.input, new_password_input: ui.input, confirm_password_input: ui.input, pw_button: ui.button) -> None:
    """Change user password with validation"""
    try:
        # Get input values
        current_pw = current_password_input.value
        new_pw = new_password_input.value
        confirm_pw = confirm_password_input.value
        
        # Basic UI validation
        if not current_pw or not new_pw or not confirm_pw:
            ui.notify('All fields are required', color='warning')
            return
        
        if new_pw != confirm_pw:
            ui.notify('New passwords do not match', color='warning')
            confirm_password_input.value = ''
            return
        
        # Show loading state
        pw_button.disable()
        pw_button.props('loading')

        await change_accessor_password_async(
            accessor_id=accessor_dto.accessor_id,
            current_password=current_pw,
            new_password=new_pw
        )
        # Success
        ui.notify(f'Password for {accessor_dto.login} changed successfully', color='positive')
        node.logger.info(f'User {accessor_dto.login} (ID: {accessor_dto.accessor_id}) changed password')
        # Clear form ONLY on success
        current_password_input.value = ''
        new_password_input.value = ''
        confirm_password_input.value = ''
    
    except AuthenticationError as e:
        ui.notify(str(e), color='negative')
        current_password_input.value = ''
    
    except ValidationError as e:
        ui.notify(str(e), color='warning')
        new_password_input.value = ''
        confirm_password_input.value = ''
    
    except NotFoundError as e:
        ui.notify(str(e), color='negative')
        node.logger.error(f'User {accessor_dto.login} not found during password change')

    except Exception as e:
        node.logger.error(f'Unexpected error: {e}')
        ui.notify('Unexpected error changing password', color='negative')
    
    finally:
        # Always restore button state (NO form clear!)
        pw_button.enable()
        pw_button.props(remove='loading')


async def reset_password_ui(node: AsyncINTRANode, editing_accessor_dto: AccessorDTO, edited_accessor_dto: AccessorDTO, new_password_input: ui.input, confirm_password_input: ui.input, pw_button: ui.button) -> None:
    """Change user password within dialog"""
    try:
        # Get input values
        new_pw = new_password_input.value
        confirm_pw = confirm_password_input.value
        
        # Basic UI validation
        if not new_pw or not confirm_pw:
            ui.notify('All fields are required', color='warning')
            return
        
        if new_pw != confirm_pw:
            ui.notify('New passwords do not match', color='warning')
            confirm_password_input.value = ''
            return
        
        # Show loading state
        pw_button.disable()
        pw_button.props('loading')

        await reset_accessor_password_async(
            accessor_id=edited_accessor_dto.accessor_id,
            new_password=new_pw
        )
        # Success
        ui.notify(f'Password for {edited_accessor_dto.login} changed successfully', color='positive')
        node.logger.info(f'Password for {edited_accessor_dto.login} (ID: {edited_accessor_dto.accessor_id}) changed successfully by {editing_accessor_dto.login} (ID: {editing_accessor_dto.accessor_id})')
        # Clear form ONLY on success
        new_password_input.value = ''
        confirm_password_input.value = ''
    
    
    except ValidationError as e:
        ui.notify(str(e), color='warning')
        new_password_input.value = ''
        confirm_password_input.value = ''
    
    except NotFoundError as e:
        ui.notify(str(e), color='negative')
        node.logger.error(f'User {edited_accessor_dto.login} not found during password change')

    except Exception as e:
        node.logger.error(f'Unexpected error: {e}')
        ui.notify('Unexpected error changing password', color='negative')
    
    finally:
        # Always restore button state (NO form clear!)
        pw_button.enable()
        pw_button.props(remove='loading')


async def refresh_accessor_table(accessor_table: ui.table, role_to_filter: Optional[RoleDTO], searched_term: Optional[str]) -> None:
    accessor_dtos = await get_all_accessors_async(role_to_filter, searched_term)
    accessor_table.rows = [
        {
            AccessorDTOkeys.ACCESSOR_ID: accessor.accessor_id,
            AccessorDTOkeys.LOGIN: accessor.login,
            AccessorDTOkeys.NAME: accessor.name,
            AccessorDTOkeys.ROLE_NAME: accessor.role_name,
            AccessorDTOkeys.CREATED_AT: accessor.created_at.strftime('%Y-%m-%d %H:%M') if accessor.created_at else 'N/A',
            AccessorDTOkeys.ACTIVE: 'Active' if accessor.active else 'Deactivated',
        }
        for accessor in accessor_dtos]
    

async def update_accessor_ui(node: AsyncINTRANode, dialog: ui.dialog, editing_accessor_dto: AccessorDTO, edited_accessor_dto: AccessorDTO, login_input: ui.input, name_input: ui.input, description_input: ui.input, role_select: ui.select, update_button: ui.button) -> None:
    with dialog:
        try:
            # Get input values
            new_login = login_input.value.strip()
            new_name = name_input.value.strip()
            new_description = description_input.value.strip()
            new_role_name = role_select.value
            
            
            # Show loading state
            update_button.disable()
            update_button.props('loading')

            if new_login != edited_accessor_dto.login:
                await update_accessor_login_async(
                    accessor_id=edited_accessor_dto.accessor_id,
                    new_login=new_login
                )
                node.logger.info(f'Login for {edited_accessor_dto.login} (ID: {edited_accessor_dto.accessor_id}) changed to {new_login} by {editing_accessor_dto.login} (ID: {editing_accessor_dto.accessor_id})')

            if new_name != edited_accessor_dto.name or new_description != edited_accessor_dto.description:
                await update_accessor_name_description_async(
                    accessor_id=edited_accessor_dto.accessor_id,
                    new_name=new_name,
                    new_description=new_description
                )

            if new_role_name != edited_accessor_dto.role_name:
                new_role_dto = await get_role_by_name_async(new_role_name)
                await update_accessor_role_async(
                    accessor_id=edited_accessor_dto.accessor_id,
                    new_role_id=new_role_dto.role_id
                )
                node.logger.info(f'Role for {edited_accessor_dto.login} (ID: {edited_accessor_dto.accessor_id}) changed to {new_role_name} by {editing_accessor_dto.login} (ID: {editing_accessor_dto.accessor_id})')
            # Success
            ui.notify(f'User {edited_accessor_dto.login} updated successfully', color='positive')
            node.logger.info(f'User {edited_accessor_dto.login} (ID: {edited_accessor_dto.accessor_id}) updated by {editing_accessor_dto.login} (ID: {editing_accessor_dto.accessor_id})')
        
        except ValidationError as e:
            ui.notify(str(e), color='warning')
        
        except NotFoundError as e:
            ui.notify(str(e), color='negative')

        except Exception as e:
            node.logger.error(f'Unexpected error: {e}')
            ui.notify('Unexpected error updating user', color='negative')
        
        finally:
            # Always restore button state
            update_button.enable()
            update_button.props(remove='loading')

async def show_add_user_dialog(node: AsyncINTRANode) -> Optional[AccessorDTO]:
    loop = asyncio.get_event_loop()
    role_dtos = await get_all_roles_async()
    fut: asyncio.Future[Optional[AccessorDTO]] = loop.create_future()

    def resolve(result: Optional[AccessorDTO]):
        if not fut.done():
            fut.set_result(result)
        dialog.close()

    with ui.dialog() as dialog, ui.card().classes('w-120 p-4'):
        ui.label('Create New User').classes('text-h6 mb-4')

        login_input       = ui.input('Login').props('outlined dense').classes('w-full')
        render_login_requirements()
        
        name_input        = ui.input('Full Name').props('outlined dense').classes('w-full mb-2')
        description_input = ui.textarea('Description').props('outlined dense').classes('w-full mb-4')

        password_input        = ui.input('Password', password=True, password_toggle_button=True).props('outlined dense').classes('w-full mb-2')
        confirm_password_input = ui.input('Confirm Password', password=True, password_toggle_button=True).props('outlined dense').classes('w-full')

        render_password_requirements()

        active_switch = ui.switch('Active', value=True).classes('mb-3')

        role_select = ui.select(
            options=[role.name for role in role_dtos],
            label="Role"
        ).props('outlined dense').classes('w-full mb-4')

        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=lambda: resolve(None)).props('flat')

            async def on_create():
                if not login_input.value or not name_input.value:
                    ui.notify('Login and Name are required', color='negative')
                    return
                
                if not password_input.value:
                    ui.notify('Password is required', color='negative')
                    return

                if password_input.value != confirm_password_input.value:
                    ui.notify('Passwords do not match', color='negative')
                    return
                
                if role_select.value is None:
                    ui.notify('Role selection is required', color='negative')
                    return
                
                try:
                    new_accessor_dto = await create_new_accessor_async(
                        login=login_input.value,
                        name=name_input.value,
                        description=description_input.value,
                        active=bool(active_switch.value),
                        role_name=role_select.value,
                        password=password_input.value
                    )
                except ValidationError as e:
                    ui.notify(f"{e}", color="negative")
                    return
                except Exception as e:
                    node.logger.error(f"Failed to create accessor: {e}")
                    ui.notify("Failed to create user", color="negative")
                    return

                resolve(new_accessor_dto)

            ui.button('Create', on_click=on_create).props('color=primary')

    dialog.open()
    return await fut


async def show_toggle_activate_user_dialog(edited_accessor: AccessorDTO) -> bool:
    """Show a mini dialog to confirm deactivation or activation of a user and return True/False."""
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    action = "Deactivate" if edited_accessor.active else "Activate"

    def confirm():
        if not fut.done():
            fut.set_result(True)
        dialog.close()

    def cancel():
        if not fut.done():
            fut.set_result(False)
        dialog.close()

    with ui.dialog() as dialog, ui.card().classes('w-80 p-4'):
        ui.label(f"{action} User").classes('text-h6 mb-4')
        ui.label(f"Are you sure you want to {action.lower()} the user '{edited_accessor.login}'?").classes('text-body2 mb-4')

        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=cancel).props('flat')
            ui.button(action, on_click=confirm).props('color=negative' if action == "Deactivate" else 'color=positive')
    dialog.open()

    return await fut

async def show_edit_user_dialog(
    node: AsyncINTRANode,
    editing_accessor_dto: AccessorDTO,
    edited_accessor_dto: AccessorDTO,
) -> bool:
    """Show a dialog to edit the details of a user and return True if saved, False if canceled."""
    loop = asyncio.get_event_loop()
    fut: asyncio.Future[bool] = loop.create_future()
    
    role_dtos = await get_all_roles_async()

    def resolve(result: bool):
        if not fut.done():
            fut.set_result(result)
        dialog.close()

    with ui.dialog() as dialog, ui.card().classes('w-96 p-4'):
        ui.label(f'Edit User: {edited_accessor_dto.login}').classes('text-h6 mb-4')

        login_input = ui.input('Login', value=edited_accessor_dto.login).props('outlined dense').classes('w-full')
        render_login_requirements()

        name_input = ui.input('Full Name', value=edited_accessor_dto.name).props('outlined dense').classes('w-full mb-2')

        role_select = ui.select(
            options=[role.name for role in role_dtos],
            value=edited_accessor_dto.role_name,
            label="Role"
        ).props('outlined dense').classes('w-full mb-4')


        description_input = ui.textarea(
            'Description',
            value=edited_accessor_dto.description or '',
        ).props('outlined dense').classes('w-full mb-4')

        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=lambda: resolve(False)).props('flat')

            async def on_save():
                await update_accessor_ui(
                    node,
                    dialog,
                    editing_accessor_dto,
                    edited_accessor_dto,
                    login_input,
                    name_input,
                    description_input,
                    role_select,
                    update_button,
                )
                resolve(True)

            update_button = ui.button('Save').props('color=primary')
            update_button.on_click(on_save)

    dialog.open()

    return await fut

async def show_reset_password_dialog(node: AsyncINTRANode, editing_accessor_dto: AccessorDTO, edited_accessor_dto: AccessorDTO) -> None:
    """Show a dialog to reset the password for a user."""
    with ui.dialog() as dialog, ui.card().classes('w-96 p-4'):
        ui.label(f'Reset Password for {edited_accessor_dto.login}').classes('text-h6 mb-4')
        ui.label('Enter new password for this user:').classes('text-body2 mb-4 text-grey-7')

        # Input fields for new password and confirmation
        new_password_input = ui.input('New Password', password=True, password_toggle_button=True).props('outlined dense').classes('w-full mb-2')
        confirm_password_input = ui.input('Confirm Password', password=True, password_toggle_button=True).props('outlined dense').classes('w-full')

        # Password requirements
        render_password_requirements()

        # Dialog buttons
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            reset_button = ui.button('Reset Password').props('color=primary')
            reset_button.on_click(lambda: reset_password_ui(
                node,
                editing_accessor_dto,
                edited_accessor_dto,
                new_password_input,
                confirm_password_input,
                reset_button
            ))

    dialog.open()


def render_permissions_list(permissions: Permissions, show_badge: bool = True) -> None:
    """
    Render a list of permissions with icons and badges.
    
    Args:
        permissions: Permissions object containing permission flags.
    """
    permissions = permissions.model_dump()

    for perm_key, perm_value in sorted(permissions.items()):
        perm_meta = PERM_META.get(perm_key, {PermMetaKeys.LABEL: perm_key})
        perm_label = perm_meta[PermMetaKeys.LABEL]

        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-2'):
                icon = 'check_circle' if perm_value else 'cancel'
                color = 'text-green' if perm_value else 'text-grey-5'
                ui.icon(icon).classes(f'{color} text-sm')
                ui.label(perm_label).classes(f'{color} text-sm')
            if perm_value and show_badge:
                ui.badge('✓').classes('bg-green text-white text-xs')

async def show_role_users_dialog(role: RoleDTO) -> None:
    """Show a dialog listing all users assigned to a specific role."""
    try:
        accessors: list[AccessorDTO] = await get_all_accessors_async(role=role, searched_term=None)
    except Exception as e:
        ui.notify(f'Failed to load users for role {role.name}: {e}', color='negative')
        return

    # column definitions
    columns = [
        {'name': 'id', 'label': 'ID', 'field': AccessorDTOkeys.ACCESSOR_ID, 'align': 'left'},
        {'name': 'login', 'label': 'Login', 'field': AccessorDTOkeys.LOGIN, 'align': 'left', 'sortable': True},
        {'name': 'name', 'label': 'Name', 'field': AccessorDTOkeys.NAME, 'align': 'left', 'sortable': True},
        {'name': 'active', 'label': 'Status', 'field': AccessorDTOkeys.ACTIVE, 'align': 'left', 'sortable': True},
    ]

    # row construction
    rows = []
    for acc in accessors:
        rows.append({
            AccessorDTOkeys.ACCESSOR_ID: acc.accessor_id,
            AccessorDTOkeys.LOGIN: acc.login,
            AccessorDTOkeys.NAME: acc.name,
            AccessorDTOkeys.ACTIVE: 'Active' if acc.active else 'Inactive',
        })

    with ui.dialog() as dialog, ui.card().classes('w-[900px] max-w-full p-4'):
        # Dialog header
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label(f'Users with role "{role.name}"').classes('text-h6')
            ui.button(icon='close', on_click=dialog.close).props('flat round dense')

        # Users table
        ui.table(
            columns=columns,
            rows=rows,
            pagination=10,
        ).classes('w-full')

    dialog.open()


async def show_manage_permissions_dialog(role: RoleDTO) -> bool:
    """
    Dialog to manage permissions for a given role.
    Args:
        role: RoleDTO object representing the role to manage.
    Returns:
        bool: True if permissions were updated, False if canceled.
    """
    loop = asyncio.get_event_loop()
    fut: asyncio.Future[bool] = loop.create_future()

    def resolve(result: bool):
        if not fut.done():
            fut.set_result(result)
        dialog.close()

    perm_values = role.permissions.model_dump()

    switches: Dict[str, ui.switch] = {}

    with ui.dialog() as dialog, ui.card().classes('w-[600px] max-w-full p-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label(f'Manage permissions: {role.name}').classes('text-h6')
            ui.button(icon='close', on_click=lambda: resolve(False)).props('flat round dense')

        ui.separator().classes('mb-3')

        # Permissions list
        with ui.column().classes('w-full gap-2'):
            for key, value in perm_values.items():
                meta = PERM_META.get(key, {PermMetaKeys.LABEL: key, PermMetaKeys.DESCRIPTION: ''})
                with ui.row().classes('w-full items-center justify-between'):
                    with ui.column().classes('gap-0'):
                        ui.label(meta[PermMetaKeys.LABEL]).classes('text-subtitle2')
                        if meta[PermMetaKeys.DESCRIPTION]:
                            ui.label(meta[PermMetaKeys.DESCRIPTION]).classes('text-caption text-grey-6')
                    sw = ui.switch(value=value)
                    switches[key] = sw

        ui.separator().classes('mt-3 mb-3')

        # Buttons
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=lambda: resolve(False)).props('flat')

            async def on_save():
                # Collect new permission values
                new_perm_dict = {name: sw.value for name, sw in switches.items()}
                new_permissions = Permissions(**new_perm_dict)

                try:
                    # TODO: tady zavolej svoji DB funkci, např.:
                    await update_role_permissions_async(role.role_id, new_permissions)

                    ui.notify(f'Permissions for role {role.name} saved', color='positive')
                    resolve(True)
                except Exception as e:
                    ui.notify(f'Failed to save permissions: {e}', color='negative')

            ui.button('Save', on_click=on_save).props('color=primary')

    dialog.open()
    return await fut


async def show_create_role_dialog() -> bool:
    """
    Dialog to create a new role including its permissions.
    Returns:
        bool: True if role was created, False if canceled or failed.
    """
    loop = asyncio.get_event_loop()
    fut: asyncio.Future[bool] = loop.create_future()

    def resolve(result: bool):
        if not fut.done():
            fut.set_result(result)
        dialog.close()

    # switches storage
    switches: Dict[str, ui.switch] = {}

    with ui.dialog() as dialog, ui.card().classes('w-120 max-w-full p-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label('Create new role').classes('text-h6')
            ui.button(icon='close', on_click=lambda: resolve(False)).props('flat round dense')

        ui.separator().classes('mb-3')
        with ui.column().classes('w-full gap-2 mb-2'):
            name_input = ui.input('Name').props('outlined dense').classes('w-full')
            render_role_name_requirements()
            description_input = ui.textarea('Description').props('outlined dense').classes('w-full')


        ui.separator().classes('my-3')
        ui.label('Permissions').classes('text-subtitle1 mb-2')

        with ui.column().classes('w-full gap-2'):
            for key, meta in PERM_META.items():
                with ui.row().classes('w-full items-center justify-between'):
                    with ui.column().classes('gap-0'):
                        ui.label(meta[PermMetaKeys.LABEL]).classes('text-subtitle2')
                        if meta[PermMetaKeys.DESCRIPTION]:
                            ui.label(meta[PermMetaKeys.DESCRIPTION]).classes('text-caption text-grey-6')
                    sw = ui.switch(value=False)
                    switches[key] = sw

        ui.separator().classes('mt-3 mb-3')

        # Buttons
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=lambda: resolve(False)).props('flat')

            async def on_create():
                # basic validation
                if not name_input.value:
                    ui.notify('Name is required', color='negative')
                    return

                # Collect permission values from switches
                new_perm_dict = {name: sw.value for name, sw in switches.items()}
                new_permissions = Permissions(**new_perm_dict)

                try:
                    await create_role_async(
                        name=name_input.value,
                        permissions=new_permissions,
                        description=description_input.value
                    )
                    ui.notify(f'Role "{name_input.value}" created', color='positive')
                    resolve(True)
                except Exception as e:
                    ui.notify(f'{e}', color='negative')

            ui.button('Create', on_click=on_create).props('color=primary')

    dialog.open()
    return await fut


async def show_edit_role_dialog(role: RoleDTO) -> bool:
    """
    Dialog to edit an existing role's details.
    Args:
        role: RoleDTO object representing the role to edit.
    Returns:
        bool: True if role was updated or deleted, False if canceled.
    """ 

    loop = asyncio.get_event_loop()
    fut: asyncio.Future[bool] = loop.create_future()

    def resolve(result: bool):
        if not fut.done():
            fut.set_result(result)
        dialog.close()

    with ui.dialog() as dialog, ui.card().classes('w-120 max-w-full p-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label(f'Edit role: {role.name}').classes('text-h6')
            ui.button(icon='close', on_click=lambda: resolve(False)).props('flat round dense')

        ui.separator().classes('mb-3')
        with ui.column().classes('w-full gap-2 mb-2'):
            name_input = ui.input('Name', value=role.name).props('outlined dense').classes('w-full')
            description_input = ui.textarea(
                'Description',
                value=role.description or '',
            ).props('outlined dense').classes('w-full')

        ui.separator().classes('mt-3 mb-3')
        with ui.row().classes('w-full justify-between gap-2'):
            # LEFT side: Delete
            async def on_delete():
                # simple confirm dialog
                confirm_loop = asyncio.get_event_loop()
                confirm_fut: asyncio.Future[bool] = confirm_loop.create_future()

                def confirm_resolve(value: bool):
                    if not confirm_fut.done():
                        confirm_fut.set_result(value)
                    confirm_dialog.close()

                with ui.dialog() as confirm_dialog, ui.card().classes('w-[400px] max-w-full p-4'):
                    ui.label(f'Delete role "{role.name}"?').classes('text-h6 mb-3')
                    ui.label(
                        'This action cannot be undone. Users assigned to this role might lose access.'
                    ).classes('text-body2 text-grey-7 mb-3')

                    with ui.row().classes('w-full justify-end gap-2'):
                        ui.button('Cancel', on_click=lambda: confirm_resolve(False)).props('flat')
                        ui.button('Delete', on_click=lambda: confirm_resolve(True)).props('color=negative')

                confirm_dialog.open()
                confirmed = await confirm_fut
                if not confirmed:
                    return

                try:
                    await delete_role_async(role.role_id)
                    ui.notify(f'Role "{role.name}" deleted', color='positive')
                    resolve(True)
                except Exception as e:
                    ui.notify(f'{e}', color='negative')

            ui.button('Delete role', icon='delete', on_click=on_delete).props('color=negative flat')

            # RIGHT side: Save / Cancel
            with ui.row().classes('gap-2'):
                ui.button('Cancel', on_click=lambda: resolve(False)).props('flat')

                async def on_save():
                    if not name_input.value:
                        ui.notify('Name is required', color='negative')
                        return

                    updated_name = name_input.value
                    updated_description = description_input.value or None

                    try:
                        await update_role_async(
                            role_id=role.role_id,
                            new_name=updated_name,
                            new_description=updated_description,
                        )

                        ui.notify(f'Role "{updated_name}" saved', color='positive')
                        resolve(True)
                    except Exception as e:
                        ui.notify(f'{e}', color='negative')

                ui.button('Save', on_click=on_save).props('color=primary')

    dialog.open()
    return await fut