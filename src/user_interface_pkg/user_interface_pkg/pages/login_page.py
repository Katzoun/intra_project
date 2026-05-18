from typing import Optional
from fastapi.responses import RedirectResponse
from nicegui import ui, app
import asyncio
from core_pkg.nodes_async import AsyncINTRANode
from user_interface_pkg.utils.jwtutils import create_jwt, is_session_active
from user_interface_pkg.constants import DASHBOARD_PAGE
from core_pkg.settings import APP_TITLE
from core_pkg.exceptions import AuthenticationError
from user_interface_pkg.constants import StorageConstants
from core_pkg.dbmodels.schemas import AccessorDTO
from core_pkg.dbservices_async.accessor_async import authenticate_accessor_async
from sqlalchemy.exc import OperationalError

def login_page_factory(node: AsyncINTRANode):
    """
    Factory function to create login page view.
    Returns a function with access to ROS2 node via closure.
    
    Args:
        node: ROS2 AsyncINTRANode node instance
    
    Returns:
        async login page view function
    """
    async def create_login_page(redirect_to: str = DASHBOARD_PAGE.route) -> Optional[RedirectResponse]:
        """
        Login page with JWT authentication and database validation.
        Args:
            redirect_to: URL to redirect to after successful login
            
        Returns:
            RedirectResponse if user is already logged in, None otherwise
        """
        try:
            # If already logged in, redirect to dashboard
            if is_session_active():
                return RedirectResponse(DASHBOARD_PAGE.route)

            async def try_login() -> None:
                """Async handler for login attempt with database validation"""
                try:
                    login = login_input.value.strip()
                    password = password_input.value

                    # Validate inputs
                    if not login or not password:
                        ui.notify('Please enter both login and password', color='negative')
                        return
                    
                    # Show loading state
                    login_button.disable()
                    login_button.props('loading')

                    # Authenticate user asynchronously
                    try:
                        accessor_dto: AccessorDTO = await authenticate_accessor_async(login, password)
                    except AuthenticationError as e:
                        node.logger.info(f'Authentication error for user {login}: {e}')
                        ui.notify(f"{e}", color='negative')
                        password_input.value = ''  # Clear password
                        return
                    except OperationalError as e:
                        node.logger.error(f'Database connection error during login for user {login}: {e}')
                        ui.notify(f'Database connection error: {e}', color='negative')
                        return

                    # Create JWT token
                    token = create_jwt(accessor_dto.login)

                    # Store user data with permissions in storage
                    import time
                    app.storage.user.update({
                        StorageConstants.AUTH_TOKEN: token,
                        StorageConstants.LOGIN: accessor_dto.login,
                        StorageConstants.ACCESSOR_ID: accessor_dto.accessor_id,
                        StorageConstants.ROLE: accessor_dto.role_name,
                        StorageConstants.ROLE_ID: accessor_dto.role_id,
                        StorageConstants.LAST_ACTIVE: time.time(),
                    })

                    node.logger.info(
                        f'User {login} (ID: {accessor_dto.accessor_id}) logged in '
                        f'with role: {accessor_dto.role_name}, '
                    )
                    # Redirect to original destination or dashboard
                    dest = app.storage.user.get(StorageConstants.REFERRER_PATH, redirect_to)
                    ui.notify(f'Welcome back, {login}!', color='positive')
                    ui.navigate.to(dest)
                    
                except Exception as e:
                    node.logger.error(f'Login error: {e}')
                    ui.notify('Error during login. Please try again.', color='negative')
                finally:
                    # Always restore button state
                    login_button.enable()
                    login_button.props(remove='loading')
            
            with ui.column().classes('absolute-center items-center'):
                with ui.card().classes('w-96 p-8 shadow-lg'):
                    # Logo and title
                    ui.icon('precision_manufacturing').classes('text-6xl text-primary mx-auto mb-4')
                    ui.label(f'{APP_TITLE}').classes('text-h4 mb-2 mx-auto').style('text-align:center')
                    ui.label('Log in to continue').classes('text-subtitle1 text-center text-grey-7 mb-6')

                    # Input fields
                    login_input = ui.input(
                        'Login',
                        placeholder='Enter your login'
                    ).classes('w-full mb-4').props('outlined')
                    
                    password_input = ui.input(
                        'Password',
                        placeholder='Enter your password',
                        password=True,
                        password_toggle_button=True,
                    ).classes('w-full mb-6').props('outlined')

                    # Enter key support
                    login_input.on('keydown.enter', lambda: password_input.run_method('focus'))
                    password_input.on('keydown.enter', try_login)

                    # Login button
                    login_button = ui.button(
                        'Login',
                        on_click=try_login,
                        icon='login'
                    ).classes('w-full bg-primary text-lg')

                    # Footer
                    ui.separator().classes('my-4')
                    with ui.row().classes('w-full items-center justify-center gap-2'):
                        ui.icon('info').classes('text-sm text-grey-6')
                        ui.label('Powered by ROS2 & NiceGUI').classes('text-sm text-grey-6')

            return None
            
        except Exception as e:
            node.logger.error(f'Login page initialization error: {e}')
            ui.notify('Failed to load login page', color='negative')
            return None
    
    return create_login_page