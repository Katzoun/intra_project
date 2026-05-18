import asyncio
from typing import Callable, TypeVar
from sqlalchemy.orm import Session
from core_pkg.dbservices import db_session

T = TypeVar("T")

async def run_in_thread_with_session(
    func: Callable[[Session], T],     
    *args,
    auto_commit: bool = False, 
    **kwargs
) -> T:
    """
    Runs a DB operation in a thread so the UI doesn't block the event loop.
    The auto_commit parameter controls commit behavior the same way as db_session().
    """

    def _work() -> T:
        with db_session(auto_commit=auto_commit) as db: 
            return func(db, *args, **kwargs)

    return await asyncio.to_thread(_work)

