from nicegui import ui, app
from core_pkg.settings import APP_TITLE, APP_SUBTITLE
from core_pkg.dbmodels.schemas import AccessorDTO
from user_interface_pkg.constants import NAV_ITEMS, NavSections, DASHBOARD_PAGE, LOGIN_PAGE
from user_interface_pkg.utils.ui_helpers import render_permissions_list

def create_header(accessor: AccessorDTO) -> None:
    """Create a modern, clean header."""

    def logout() -> None:
        app.storage.user.clear()
        ui.notify('Logged out successfully', color='info')
        ui.navigate.to(LOGIN_PAGE.route)

    def show_user_info() -> None:
        with ui.dialog() as dialog, ui.card().classes('w-96'):
            with ui.row().classes('w-full items-center mb-4'):
                ui.icon('account_circle').classes('text-6xl text-primary')
                with ui.column().classes('ml-4'):
                    ui.label(accessor.login).classes('text-h6')
                    ui.label(f'ID: {accessor.accessor_id}').classes('text-caption text-grey-7')
                    ui.badge(accessor.role_name.upper()).classes(f'{accessor.role_color} text-xs').props('rounded')
            ui.separator()
            ui.label('Permissions').classes('text-subtitle1 font-bold mt-4 mb-2')
            with ui.column().classes('w-full gap-1'):
                render_permissions_list(accessor.permissions)
            ui.separator().classes('mt-4')
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Close', on_click=dialog.close).props('flat')
        dialog.open()

    with ui.header().classes('items-center px-6 py-0 shadow-sm border-b').style(
        'background: rgba(255,255,255,0.85); backdrop-filter: blur(12px); '
        '-webkit-backdrop-filter: blur(12px); height: 68px; min-height: 56px;'
    ):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-2 cursor-pointer').on(
                'click', lambda: ui.navigate.to(DASHBOARD_PAGE.route)
            ):
                ui.icon('precision_manufacturing').classes('text-2xl text-primary')
                ui.label(APP_TITLE).classes(
                    'text-sm font-bold tracking-wide text-grey-9'
                ).style('letter-spacing: 0.08em;')
            with ui.row().classes('items-center gap-2'):
                with ui.element('div').classes(
                    'flex items-center gap-2 cursor-pointer rounded-full '
                    'pl-1 pr-3 py-1 hover:bg-grey-2 transition-colors'
                ).on('click', show_user_info).style('min-height:36px;'):
                    # avatar
                    with ui.element('div').classes(
                        'w-7 h-7 rounded-full flex items-center justify-center'
                    ).style('background: var(--q-primary); color: white;'):
                        ui.label(accessor.login[0].upper()).classes('text-xs font-bold')
                    ui.label(accessor.login).classes('text-sm text-grey-8')
                    ui.tooltip('Account details')

                ui.button(icon='logout', on_click=logout).props(
                    'flat round dense size=sm'
                ).classes('text-grey-6 hover:text-grey-9').tooltip('Logout')


def create_sidebar(accessor: AccessorDTO, active_page: str = DASHBOARD_PAGE.page) -> None:
    """
    Create universal sidebar navigation with permission-based conditional rendering.
    Only shows menu items that user has permission to access.
    
    Args:
        active_page: Name of currently active page for highlighting
    """

    with ui.column().classes(
        'w-64 bg-grey-1 p-4 '
        'overflow-y-auto rounded-lg'
    ).style('position: sticky; top: 72px; align-self: flex-start;'):
        ui.label('Navigation').classes('text-h6 mb-4 text-grey-8')

        # Group items by section
        sections = {
            NavSections.MAIN: [],
            NavSections.ADMIN: [],
            NavSections.SYSTEM: []
        }

        perms = accessor.permissions.model_dump()
        
        for item in NAV_ITEMS:
            # Check permission - skip if accessor doesn't have required permission
            if item.permission and not perms.get(item.permission, False):
                continue
            sections[item.section].append(item)

        # Render main section
        if sections[NavSections.MAIN]:
            for item in sections[NavSections.MAIN]:
                _render_nav_button(item.__dict__, active_page)

        # Render admin section if any items available
        if sections[NavSections.ADMIN]:
            ui.separator().classes('my-4')
            ui.label('Administration').classes('text-caption text-grey-6 mb-2 px-2')
            for item in sections[NavSections.ADMIN]:
                _render_nav_button(item.__dict__, active_page)

        # Render system section
        if sections[NavSections.SYSTEM]:
            ui.separator().classes('my-4')
            for item in sections[NavSections.SYSTEM]:
                _render_nav_button(item.__dict__, active_page)
        

def _render_nav_button(item: dict, active_page: str) -> None:
    """
    Helper function to render navigation button with consistent styling.
    
    Args:
        item: Navigation item dict with name, icon, route, page
        active_page: Currently active page name
    """
    is_active = active_page == item['page']
    classes = 'w-full mb-2 justify-start'
    props = 'flat align=left'
    
    if is_active:
        classes += ' bg-primary text-white'
    else:
        classes += ' text-grey-8 hover:bg-grey-3'
    
    def navigate_to(target_route=item['route']):
        ui.navigate.to(target_route)
    
    ui.button(
        item['name'],
        icon=item['icon'],
        on_click=navigate_to
    ).classes(classes).props(props)


def create_main_layout(accessor: AccessorDTO, active_page: str = DASHBOARD_PAGE.page):
    """
    Create main layout with modern header and sidebar.
    Returns content column where page content should be placed.
    
    Args:
        active_page: Name of currently active page
        
    Returns:
        ui.column context manager for main content
    """
    create_header(accessor)

    with ui.row().classes('w-full no-wrap items-start pt-4 px-4 gap-4'):
        create_sidebar(accessor, active_page)
        return ui.column().classes('flex-1 px-6 pb-6 bg-grey-2 overflow-y-auto rounded-lg')