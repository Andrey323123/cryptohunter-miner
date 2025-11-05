# lead_scanner.py — v2.8 — ИЩЕТ ТОЛЬКО РЕАЛЬНЫХ ЛЮДЕЙ (username без "-")
import os
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from aiogram import Bot
from sqlalchemy import select
from dotenv import load_dotenv
from core.models import Lead
from core.database import AsyncSessionLocal

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scanner.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === Конфигурация ===
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PHONE = os.getenv("PHONE")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Не найдены ключи API_ID, API_HASH или BOT_TOKEN в .env")

bot = Bot(token=BOT_TOKEN)

# === Основные данные ===
PREDEFINED_CHANNELS = [
    "toncoin", "ton_russia", "whaleston", "toninvest", "ton_community",
    "cryptoru", "cryptodzen", "bitcoin", "blockchain", "mining",
    "investments", "crypto_news", "binance_russia", "coinspot",
    "tonapp", "tonstarter", "tonspace", "getgems", "tonkeeper",
    "tonwhales", "tonfoundation", "tondev", "tontech",
    "cryptohunter", "cryptosignal", "cryptoworld", "cryptolife"
]

# === Ключевые слова ===
CRYPTO_BASIC_KEYWORDS = [
    "КРИПТО", "CRYPTO", "BITCOIN", "BTC", "ETH", "SOL", "NFT", "DEFI",
    "WEB3", "БЛОКЧЕЙН", "ALTCOIN", "ETHEREUM", "TRADING", "КРИПТА", "TON"
]
TON_ECOSYSTEM_KEYWORDS = [
    "TONCOIN", "TON", "TON WALLET", "TONKEEPER", "TON SPACE", "TON DEFI",
    "TON DEX", "TON SWAP", "GETGEMS", "TON FOUNDATION", "TON DNS",
    "TON BRIDGE", "TON ECOSYSTEM", "TON APP", "TONSTARTER"
]
FINANCE_KEYWORDS = [
    "ИНВЕСТИЦИИ", "INVEST", "ПРИБЫЛЬ", "TRADING", "BINANCE", "BYBIT",
    "KUCOIN", "OKX", "MEXC", "BITGET", "INCOME", "PORTFOLIO", "EARN",
    "INVESTMENT", "CAPITAL", "FINANCE", "ФИНАНСЫ", "ПАССИВНЫЙ ДОХОД"
]
MINING_KEYWORDS = [
    "МАЙНИНГ", "MINING", "HASH", "GPU", "ASIC", "МАЙНЕР", "ФЕРМА",
    "OBLA", "EARN", "ЗАРАБОТОК", "РИГ", "RIG", "MINER", "ХЭШРЕЙТ"
]
LOSS_KEYWORDS = [
    "SCAM", "ОБМАН", "МОШЕННИК", "КИДАНУЛИ", "FRAUD", "ВОРЫ", "HACK",
    "STOLEN", "LOST", "ERROR", "BLOCKED", "FAKE", "ЛОХОТРОН", "ПИРАМИДА"
]

# === Проверка структуры БД ===
async def check_database_structure():
    from core.database import engine
    from core.models import Base
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ База данных готова.")
    except Exception as e:
        logger.error(f"Ошибка при проверке БД: {e}")

# === Получение каналов ===
async def get_predefined_channels(client):
    channels_to_scan = []
    for channel in PREDEFINED_CHANNELS:
        try:
            entity = await client.get_entity(channel)
            if entity:
                channels_to_scan.append({
                    "id": entity.id,
                    "title": getattr(entity, "title", channel),
                    "username": getattr(entity, "username", ""),
                    "participants_count": getattr(entity, "participants_count", 0),
                    "source": "predefined"
                })
                logger.info(f"Добавлен канал из списка: {channel}")
        except Exception as e:
            logger.warning(f"Не удалось получить {channel}: {e}")
        await asyncio.sleep(0.5)
    return channels_to_scan

# === Поиск новых каналов ===
async def search_new_channels_in_dialogs(client, predefined_channels):
    found_channels = []
    predefined_usernames = {ch["username"].lower() for ch in predefined_channels if ch["username"]}
    try:
        async for dialog in client.iter_dialogs(limit=150):
            if dialog.is_channel:
                username = getattr(dialog.entity, "username", "")
                title = getattr(dialog.entity, "title", "")
                if not username:
                    continue
                if username.lower() in predefined_usernames:
                    continue
                keywords = [
                    'ton', 'crypto', 'крипт', 'майнинг', 'биткоин',
                    'invest', 'blockchain', 'eth', 'nft', 'defi', 'wallet'
                ]
                if any(k in title.lower() for k in keywords):
                    found_channels.append({
                        "id": dialog.entity.id,
                        "title": title,
                        "username": username,
                        "participants_count": getattr(dialog.entity, "participants_count", 0),
                        "source": "discovered"
                    })
                    logger.info(f"🎯 Найден новый канал: {title}")
        logger.info(f"Найдено новых каналов: {len(found_channels)}")
    except Exception as e:
        logger.error(f"Ошибка при поиске новых каналов: {e}")
    return found_channels

# === Глобальный поиск каналов ===
async def search_channels_globally(client, predefined_channels):
    found_channels = []
    predefined_usernames = {ch["username"].lower() for ch in predefined_channels if ch["username"]}
    try:
        search_keywords = [
            'TON', 'Toncoin', 'TON Wallet', 'Tonkeeper', 'TON Space', 'TON DeFi',
            'TON DEX', 'TON Bridge', 'Getgems', 'TON Staking', 'TON Airdrop',
            'Bitcoin', 'BTC', 'Ethereum', 'ETH', 'Solana', 'SOL', 'Crypto',
            'Cryptocurrency', 'Крипта', 'Криптовалюта', 'Altcoin', 'DeFi', 'Web3',
            'NFT', 'Binance', 'Bybit', 'OKX', 'Kucoin', 'MEXC', 'Bitget',
            'Trading', 'Investment', 'Invest', 'Blockchain', 'Блокчейн',
            'Пассивный доход', 'Mining', 'Hashrate', 'Farm', 'TON Invest'
        ]
        for keyword in search_keywords:
            logger.info(f"🔎 Поиск по ключевому слову: {keyword}")
            try:
                result = await client(SearchRequest(q=keyword, limit=60))
                for chat in result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        username = chat.username.lower()
                        if username not in predefined_usernames:
                            title_lower = chat.title.lower()
                            if any(k in title_lower for k in ['ton', 'crypto', 'биткоин', 'крипт', 'eth', 'blockchain', 'nft', 'defi']):
                                found_channels.append({
                                    "id": chat.id,
                                    "title": chat.title,
                                    "username": chat.username,
                                    "participants_count": getattr(chat, "participants_count", 0),
                                    "source": "global_search"
                                })
                                logger.info(f"✅ Найден канал: {chat.title} (@{chat.username})")
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"Ошибка поиска '{keyword}': {e}")
        logger.info(f"Глобальный поиск завершен. Всего найдено: {len(found_channels)}")
    except Exception as e:
        logger.error(f"Ошибка глобального поиска: {e}")
    return found_channels

# === Подсчет интереса ===
async def calculate_interest_score(text: str):
    score = 0
    found_keywords = []
    upper = text.upper()
    category_keywords = {
        "крипто": CRYPTO_BASIC_KEYWORDS,
        "TON": TON_ECOSYSTEM_KEYWORDS,
        "финансы": FINANCE_KEYWORDS,
        "майнинг": MINING_KEYWORDS,
        "жалобы": LOSS_KEYWORDS
    }
    for category, keywords_list in category_keywords.items():
        category_found = False
        for keyword in keywords_list:
            if keyword in upper:
                found_keywords.append(keyword)
                category_found = True
                if category == "крипто": score += 15
                elif category == "TON": score += 25
                elif category == "финансы": score += 20
                elif category == "майнинг": score += 30
                elif category == "жалобы": score += 25
        if category_found:
            found_keywords.append(category)
    return score, found_keywords

# === Сканирование канала ===
async def scan_channel(client, channel_info):
    identifier = channel_info["username"] or channel_info["title"]
    logger.info(f"📡 Сканируем канал: {identifier}")
    messages_scanned = 0
    leads_found = 0
    try:
        async for message in client.iter_messages(identifier, limit=50):
            if not message.text or not message.sender_id:
                continue
            messages_scanned += 1
            score, keywords = await calculate_interest_score(message.text)
            if score >= 50:
                leads_found += 1
                await process_lead(client, message.sender_id, identifier, score, keywords, channel_info.get("source", "unknown"))
        logger.info(f"📊 {identifier}: {messages_scanned} сообщений, {leads_found} лидов")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при сканировании {identifier}: {e}")
    return leads_found

# === Обработка лида ===
async def process_lead(client, user_id, source_channel, score, keywords, source_type):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Lead).where(Lead.user_id == user_id))
            if result.scalar_one_or_none():
                return

            try:
                user = await client.get_entity(user_id)
                username = getattr(user, "username", None)
                first_name = getattr(user, "first_name", None)
                # ✅ Фильтр username без дефиса, без "bot/news/channel"
                if not username or "-" in username or username.lower().endswith("bot") or username.lower() in ["news", "channel"]:
                    logger.info(f"⛔ Пропущен пользователь @{username} — неподходит (бот, дефис или без username)")
                    return
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить данные пользователя {user_id}: {e}")
                return

            lead = Lead(
                user_id=user_id,
                username=username,
                first_name=first_name,
                source_channel=source_channel,
                source_type=source_type,
                found_at=datetime.utcnow(),
                interest_score=score,
                keywords_list=keywords,
                contact_attempts=0,
                conversion_status="found"
            )
            db.add(lead)
            await db.commit()
            logger.info(f"✅ ЛИД СОХРАНЁН: @{username} | {source_channel} | score={score}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении лида {user_id}: {e}")

# === Фильтр каналов ===
async def filter_channels(channels):
    filtered = []
    for ch in channels:
        if not ch.get("id") or ch.get("id") < 0:
            continue
        participants = ch.get("participants_count", 0)
        if participants and participants > 100000:
            continue
        filtered.append(ch)
    logger.info(f"После фильтрации осталось {len(filtered)} каналов")
    return filtered

# === Основной процесс ===
async def run_scanner(client):
    logger.info("🚀 Lead Scanner запущен")
    await check_database_structure()
    predefined = await get_predefined_channels(client)
    new = await search_new_channels_in_dialogs(client, predefined)
    global_found = await search_channels_globally(client, predefined)
    all_channels = await filter_channels(predefined + new + global_found)
    total_leads = 0
    for channel in all_channels:
        total_leads += await scan_channel(client, channel)
        await asyncio.sleep(2)
    logger.info(f"✅ Завершено. Найдено лидов: {total_leads}")

# === Главный цикл ===
async def main():
    logger.info("🔍 LEAD SCANNER v2.8 — STARTED")
    while True:
        try:
            client = TelegramClient("scanner_session", API_ID, API_HASH)
            await client.start(phone=PHONE)
            await run_scanner(client)
            await client.disconnect()
            logger.info("⏰ Сканирование завершено. Ожидание 4 часа...")
            await asyncio.sleep(4 * 3600)
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
