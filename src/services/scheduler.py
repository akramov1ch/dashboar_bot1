import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from src.config import settings
from src.database.base import async_session
from src.database.models import User, Task
from src.services.sheets_service import sheets_service

logger = logging.getLogger(__name__)


def _get_timezone():
    return getattr(settings, "TIMEZONE", "Asia/Tashkent")


async def job_deadline_reminders(bot):
    now = datetime.now()
    target_start = now + timedelta(hours=23)
    target_end = now + timedelta(hours=25)

    async with async_session() as session:
        res = await session.execute(select(Task).where(Task.status.in_(["Yangi topshiriq", "Jarayonda"])))
        tasks = res.scalars().all()

    for task in tasks:
        if not task.deadline or not (target_start <= task.deadline <= target_end):
            continue
        text = (
            "⏰ <b>Eslatma!</b>\n"
            f"📌 <b>{task.task_name}</b>\n"
            "Deadline 1 kun qoldi."
        )
        for uid in [task.mobilographer_id, task.copywriter_id, task.marketer_id]:
            if not uid:
                continue
            try:
                await bot.send_message(uid, text, parse_mode="HTML")
            except Exception as e:
                logger.error("Reminder send failed user_id=%s: %s", uid, e)


async def job_mark_overdue_tasks():
    now = datetime.now()
    async with async_session() as session:
        res = await session.execute(select(Task).where(Task.status.in_(["Yangi topshiriq", "Jarayonda"])))
        tasks = res.scalars().all()

        for task in tasks:
            if not task.deadline or task.deadline >= now:
                continue
            owner_res = await session.execute(select(User).where(User.telegram_id == task.mobilographer_id))
            owner = owner_res.scalar_one_or_none()
            if not owner or not owner.personal_sheet_id or not owner.worksheet_name:
                continue
            try:
                await sheets_service.update_progress_status(
                    owner.personal_sheet_id,
                    owner.worksheet_name,
                    task.row_index,
                    "Jarayonda",
                    "Kechikmoqda 🟠",
                )
            except Exception as e:
                logger.error("Overdue sheet update failed task_id=%s: %s", task.id, e)


async def job_auto_open_new_month(bot):
    sheet_id = settings.DEFAULT_SPREADSHEET_ID
    now = datetime.now()
    new_month = sheets_service.get_next_month_name(now)

    async with async_session() as session:
        users = (await session.execute(select(User).order_by(User.full_name))).scalars().all()
        employee_full_names = [u.full_name for u in users if u.full_name]

    if not employee_full_names:
        return

    try:
        await sheets_service.create_month_and_employee_tabs(
            sheet_id=sheet_id,
            new_month=new_month,
            employee_full_names=employee_full_names,
        )
    except Exception as e:
        logger.error("Auto month open error: %s", e)
        return

    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            if u.full_name:
                u.personal_sheet_id = sheet_id
                u.worksheet_name = f"{u.full_name} {new_month}"
        await session.commit()

    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"📅 <b>Yangi oy avtomatik ochildi:</b> <b>{new_month}</b>", parse_mode="HTML")
        except Exception as e:
            logger.error("Admin notify failed admin_id=%s: %s", admin_id, e)


def setup_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone=_get_timezone())
    scheduler.add_job(
        job_deadline_reminders,
        trigger=CronTrigger(minute="*/10"),
        args=[bot],
        id="deadline_reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        job_mark_overdue_tasks,
        trigger=CronTrigger(minute="*/10"),
        id="overdue_status_update",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    auto_rollover = str(getattr(settings, "AUTO_MONTH_ROLLOVER", "true")).lower() in ("1", "true", "yes", "on")
    if auto_rollover:
        scheduler.add_job(
            job_auto_open_new_month,
            trigger=CronTrigger(
                day=int(getattr(settings, "AUTO_MONTH_DAY", 25)),
                hour=int(getattr(settings, "AUTO_MONTH_HOUR", 9)),
                minute=int(getattr(settings, "AUTO_MONTH_MINUTE", 0)),
            ),
            args=[bot],
            id="auto_month_rollover",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
