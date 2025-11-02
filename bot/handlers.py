# bot/handlers.py — v4.0: ТОЛЬКО /start + УМНЫЕ НАПОМИНАНИЯ
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from core.models import User, Referral
from core.database import AsyncSessionLocal
from bot.keyboard import main_menu
from sqlalchemy import select
from decimal import Decimal
import asyncio
import re

router = Router()

def extract_referrer_id(payload: str) -> int | None:
    """Извлекает ID реферера из payload"""
    if not payload:
        return None
    
    # Обрабатываем форматы: ref_12345, 12345, ref12345
    if payload.startswith('ref_'):
        ref_id = payload[4:]
    elif payload.startswith('ref'):
        ref_id = payload[3:]
    else:
        ref_id = payload
    
    # Проверяем, что это число
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
            await db.commit()  # Сначала сохраняем пользователя

        # Обработка рефералки только для новых пользователей
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
                    await message.answer("🎉 Вы зарегистрированы по реферальной ссылке!")

        await message.answer(
            "Добро пожаловать в *CryptoHunter Miner*!\n"
            "25%/мес + бесплатный майнинг\n\n"
            "Нажмите кнопку ниже, чтобы открыть майнер:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

        # === УМНЫЕ НАПОМИНАНИЯ ===
        if is_new:  # Напоминания только для новых пользователей
            asyncio.create_task(send_reminders(message))

async def send_reminders(message: Message):
    """Отправка напоминаний пользователю"""
    try:
        # Первое напоминание через 1 час
        await asyncio.sleep(3600)  # 1 час
        await message.answer(
            "💎 *Напомню о возможностях:*\n"
            "• Майнинг 25% в месяц\n" 
            "• Рефералы: 5% с депозитов\n"
            "• Бесплатный доход каждый день\n\n"
            "Открыть майнер:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        
        # Второе напоминание через 3 часа
        await asyncio.sleep(7200)  # +2 часа = 3 часа от старта
        await message.answer(
            "🚀 *Проверь свой баланс!*\n"
            "Ты уже мог заработать первые TON\n\n"
            "Открыть майнер и проверить:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        
        # Третье напоминание через 24 часа
        await asyncio.sleep(75600)  # +21 час = 24 часа от старта
        await message.answer(
            "⏰ *Ежедневный бонус ждет!*\n"
            "Заходи каждый день для бесплатного майнинга\n\n"
            "Забрать бонус:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
            
    except Exception as e:
        print(f"Ошибка в напоминаниях: {e}")
