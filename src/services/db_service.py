from sqlalchemy import select

from src.database.base import async_session
from src.database.models import User, Task, UserRole


async def get_user_by_telegram_id(telegram_id: int):
    async with async_session() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return res.scalar_one_or_none()


async def get_first_user_by_role(role: UserRole):
    async with async_session() as session:
        res = await session.execute(select(User).where(User.role == role))
        return res.scalars().first()


async def get_task(task_id: int):
    async with async_session() as session:
        return await session.get(Task, task_id)
