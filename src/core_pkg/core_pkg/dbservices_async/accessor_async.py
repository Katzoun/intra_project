
from core_pkg.dbservices import AuthDBService
from core_pkg.dbservices_async.async_utils import run_in_thread_with_session
from core_pkg.dbmodels.schemas import AccessorDTO, accessor_to_dto, RoleDTO, role_to_dto, Permissions
from typing import Optional


async def authenticate_accessor_async(login: str, password: str) -> AccessorDTO:
    """
    Async wrapper over authenticate_accessor.
    """
    def _work(db, login: str, password: str) -> AccessorDTO:
        service = AuthDBService(db)
        accessor = service.authenticate_accessor(login, password)
        dto = accessor_to_dto(accessor)
        return dto

    return await run_in_thread_with_session(_work, login, password)

async def get_accessor_by_id_async(accessor_id: int) -> AccessorDTO:
    """
    Async wrapper over get_accessor_by_id.
    """
    def _work(db, accessor_id: int) -> AccessorDTO:
        service = AuthDBService(db)
        accessor = service.accessor_repo.get_by_id(accessor_id)
        dto = accessor_to_dto(accessor)
        return dto

    return await run_in_thread_with_session(_work, accessor_id)


async def get_role_by_id_async(role_id: int) -> RoleDTO:
    """
    Async wrapper over get_role_by_id.
    """
    def _work(db, role_id: int) -> RoleDTO:
        service = AuthDBService(db)
        role = service.role_repo.get_by_id(role_id)
        dto = role_to_dto(role)
        return dto

    return await run_in_thread_with_session(_work, role_id)

async def get_role_by_name_async(role_name: str) -> RoleDTO:
    """
    Async wrapper over get_role_by_name.
    """
    def _work(db, role_name: str) -> RoleDTO:
        service = AuthDBService(db)
        role = service.role_repo.get_by_name(role_name)
        dto = role_to_dto(role)
        return dto

    return await run_in_thread_with_session(_work, role_name)


async def toggle_accessor_activation_async(accessor_id: int) -> None:
    """
    Async wrapper over toggle_accessor_activation.
    """
    def _work(db, accessor_id: int) -> None:
        service = AuthDBService(db)
        service.toggle_accessor_activation(accessor_id)

    return await run_in_thread_with_session(_work, accessor_id, auto_commit=True)


async def get_all_accessors_async(role: Optional[RoleDTO], searched_term: Optional[str]) -> list[AccessorDTO]:
    """
    Async wrapper to get all accessors as DTOs.
    """
    def _work(db) -> list[AccessorDTO]:
        service = AuthDBService(db)
        if isinstance(role, RoleDTO) and isinstance(searched_term, str):
            accessors = service.accessor_repo.get_by_role_id_with_search(role.role_id, searched_term)
        elif isinstance(role, RoleDTO):
            accessors = service.accessor_repo.get_by_role_id(role.role_id)
        elif isinstance(searched_term, str):
            accessors = service.accessor_repo.search_users(searched_term)
        else:
            accessors = service.accessor_repo.get_all()

        dtos = [accessor_to_dto(acc) for acc in accessors]
        return dtos

    return await run_in_thread_with_session(_work)

async def get_all_roles_async() -> list[RoleDTO]:
    """
    Async wrapper to get all roles as DTOs.
    """
    def _work(db) -> list[RoleDTO]:
        service = AuthDBService(db)
        roles = service.role_repo.get_all()
        dtos = [role_to_dto(role) for role in roles]
        return dtos

    return await run_in_thread_with_session(_work)

async def change_accessor_password_async(
    accessor_id: int,
    current_password: str,
    new_password: str,
    ) -> bool:
    """
    Async wrapper over change_accessor_password.
    """
    def _work(db, accessor_id: int, current_password: str, new_password: str) -> bool:
        service = AuthDBService(db)
        return service.change_accessor_password(
            accessor_id=accessor_id,
            current_password=current_password,
            new_password=new_password,
        )

    return await run_in_thread_with_session(
        _work,
        accessor_id,
        current_password,
        new_password,
        auto_commit=True,
    )

async def reset_accessor_password_async(
    accessor_id: int,
    new_password: str,
    ) -> bool:
    """
    Async wrapper over reset_accessor_password.
    """
    def _work(db, accessor_id: int, new_password: str) -> bool:
        service = AuthDBService(db)
        return service.reset_accessor_password(
            accessor_id=accessor_id,
            new_password=new_password,
        )

    return await run_in_thread_with_session(
        _work,
        accessor_id,
        new_password,
        auto_commit=True,
    )

async def update_accessor_login_async(
    accessor_id: int,
    new_login: str,
    ) -> None:
    """
    Async wrapper over update_accessor_login.
    """
    def _work(db, accessor_id: int, new_login: str) -> None:
        service = AuthDBService(db)
        service.update_accessor_login(
            accessor_id=accessor_id,
            new_login=new_login,
        )

    return await run_in_thread_with_session(
        _work,
        accessor_id,
        new_login,
        auto_commit=True,
    )

async def update_accessor_role_async(
    accessor_id: int,
    new_role_id: int,
    ) -> None:
    """
    Async wrapper over update_accessor_role.
    """
    def _work(db, accessor_id: int, new_role_id: int) -> None:
        service = AuthDBService(db)
        service.update_accessor_role(
            accessor_id=accessor_id,
            new_role_id=new_role_id,
        )

    return await run_in_thread_with_session(
        _work,
        accessor_id,
        new_role_id,
        auto_commit=True,
    )

async def update_accessor_name_description_async(
    accessor_id: int,
    new_name: str,
    new_description: Optional[str] = None,
    ) -> None:
    """
    Async wrapper over update_accessor_name_description.
    """
    def _work(db, accessor_id: int, new_name: str, new_description: Optional[str]) -> None:
        service = AuthDBService(db)
        service.update_accessor_name_description(
            accessor_id=accessor_id,
            new_name=new_name,
            new_description=new_description,
        )

    return await run_in_thread_with_session(
        _work,
        accessor_id,
        new_name,
        new_description,
        auto_commit=True,
    )


async def create_new_accessor_async( 
    login: str,
    name: str,
    description: Optional[str],
    active: bool,
    role_name: str,
    password: str,
    ) -> AccessorDTO:
    """
    Async wrapper over create_accessor.
    """
    def _work(db, login: str, name: str, description: Optional[str], active: bool, role_name: str, password: str) -> AccessorDTO:
        service = AuthDBService(db)
        accessor = service.create_new_accessor(
            login=login,
            name=name,
            description=description,
            active=active,
            role_name=role_name,
            password=password,
        )
        dto = accessor_to_dto(accessor)
        return dto

    return await run_in_thread_with_session(
        _work,
        login,
        name,
        description,
        active,
        role_name,
        password,
        auto_commit=True,
    )

async def update_role_permissions_async(
    role_id: int,
    new_permissions: Permissions,
    ) -> None:
    """
    Async wrapper over update_role_permissions.
    """
    def _work(db, role_id: int, new_permissions) -> None:
        service = AuthDBService(db)
        service.update_role_permissions(
            role_id=role_id,
            new_permissions=new_permissions,
        )

    return await run_in_thread_with_session(
        _work,
        role_id,
        new_permissions,
        auto_commit=True,
    )

async def create_role_async(
    name: str,
    permissions: Permissions,
    description: Optional[str],
    ) -> RoleDTO:
    """
    Async wrapper over create_role.
    """
    def _work(db, name: str, permissions: Permissions, description: Optional[str]) -> RoleDTO:
        service = AuthDBService(db)
        role = service.create_role(
            name=name,
            permissions=permissions,
            description=description
        )
        dto = role_to_dto(role)
        return dto

    return await run_in_thread_with_session(
        _work,
        name,
        permissions,
        description,
        auto_commit=True,
    )

async def delete_role_async(role_id: int) -> None:
    """
    Async wrapper over delete_role.
    """
    def _work(db, role_id: int) -> None:
        service = AuthDBService(db)
        service.delete_role(
            role_id=role_id,
        )

    return await run_in_thread_with_session(
        _work,
        role_id,
        auto_commit=True,
    )

async def update_role_async(
    role_id: int,
    new_name: str,
    new_description: Optional[str],
    ) -> None:
    """
    Async wrapper over update_role.
    """
    def _work(db, role_id: int, new_name: str, new_description: Optional[str]) -> None:
        service = AuthDBService(db)
        service.update_role_name_description(
            role_id=role_id,
            new_name=new_name,
            new_description=new_description,
        )

    return await run_in_thread_with_session(
        _work,
        role_id,
        new_name,
        new_description,
        auto_commit=True,
    )