"""Aggregator module that preserves the historical single-router import path
(`from src.bot.handlers import router`).

Handler registration order matters (the manual-post catch-all must be last),
so sub-routers are included in the same order handlers used to be declared:
moderation flow -> setup/admin commands -> dashboard shortcuts -> manual posts.
"""
from aiogram import Router

from src.bot.routers import moderation, setup_admin, dashboard, manual


router = Router()
router.include_router(moderation.router)
router.include_router(setup_admin.router)
router.include_router(dashboard.router)
router.include_router(manual.router)
