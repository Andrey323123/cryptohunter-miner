# bot/handlers.py — v4.2: HTTPS + БЕРЁМ URL ИЗ .env (БЕЗ ДУБЛЕЙ)
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from core.models import User, Referral
from core.database import AsyncSessionLocal
from bot.keyboard import main_menu  # ← УБЕДИМСЯ, ЧТО main_menu() ИСПРАВЛЕН
from sqlalchemy import select
from decimal import Decimal
import asyncio
import re

# УДАЛЯЕМ ЭТУ СТРОКУ — URL БЕРЁМ ИЗ config.py
# WEBAPP_URL = "https://cryptohunter-miner-production.up.railway.app"

router = Router()

def extract_referrer_id(payload: str) -> int | None:
    """Извлекает ID реферера из payload"""
    if not payload:
        return None
   
    if payload.startswith('ref_'):
        ref_id = payload[4:]
    elif payload.startswith('ref'):
        ref_id = payload[3:]
    else:
        ref_id = payload
   
    if ref_id.isdigit():
        return int(ref_id)
    return None

# === /start + РЕФЕРАЛКА ===
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    args = message.text.split()
    payload = args[1] if len(args) > 1 else None
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.user_id == message.from_user.id))
        user = result.scalar_one_or_none()
        is_new = False
        if not user:
            is_new = True
            user = User(
                user_id=message.from_user.id,
                username=message.from_user.username,
                referrer_id=extract_referrer_id(payload)
            )
            db.add(user)
            await db.commit()

        if is_new and payload:
            referrer_id = extract_referrer_id(payload)
            if referrer_id and referrer_id != user.user_id:
                referrer_result = await db.execute(select(User).where(User.user_id == referrer_id))
                referrer = referrer_result.scalar_one_or_none()
                if referrer:
                    referral = Referral(
                        referrer_id=referrer_id,
                        referred_id=user.user_id,
                        level=1,
                        bonus_paid=Decimal('0')
                    )
                    db.add(referral)
                    referrer.referral_count += 1
                    await db.commit()
                    await message.answer("Вы зарегистрированы по реферальной ссылке!")

        await message.answer(
            "Добро пожаловать в *CryptoHunter Miner*!\n"
            "25%/мес + бесплатный майнинг\n\n"
            "Нажмите кнопку ниже, чтобы открыть майнер:",
            reply_markup=main_menu(),  # ← УБЕДИМСЯ, ЧТО main_menu() ВОЗВРАЩАЕТ HTTPS
            parse_mode="Markdown"
        )

        if is_new:
            asyncio.create_task(send_reminders(message))

async def send_reminders(message: Message):
    """Отправка напоминаний пользователю"""
    try:
        await asyncio.sleep(3600)
        await message.answer(
            "*Напомню о возможностях:*\n"
            "• Майнинг 25% в месяц\n"
            "• Рефералы: 5% с депозитов\n"
            "• Бесплатный доход каждый день\n\n"
            "Открыть майнер:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
       
        await asyncio.sleep(7200)
        await message.answer(
            "*Проверь свой баланс!*\n"
            "Ты уже мог заработать первые TON\n\n"
            "Открыть майнер и проверить:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
       
        await asyncio.sleep(75600)
        await message.answer(
            "*Ежедневный бонус ждет!*\n"
            "Заходи каждый день для бесплатного майнинга\n\n"
            "Забрать бонус:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
           
    except Exception as e:
        print(f"Ошибка в напоминаниях: {e}")
