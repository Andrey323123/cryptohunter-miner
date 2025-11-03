# lead_scanner.py — v2.6 — ФИКСИРОВАННЫЙ ИНТЕРВАЛ
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

# === Настройка логов ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scanner.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === Загрузка данных из .env ===
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PHONE = os.getenv("PHONE")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Не найдены ключи API_ID, API_HASH или BOT_TOKEN в .env")

bot = Bot(token=BOT_TOKEN)

# === Константы ===
PREDEFINED_CHANNELS = [
    "toncoin", "ton_russia", "whaleston", "toninvest", "ton_community",
    "cryptoru", "cryptodzen", "bitcoin", "blockchain", "mining",
    "investments", "crypto_news", "binance_russia", "coinspot",
    "tonapp", "tonstarter", "tonspace", "getgems", "tonkeeper",
    "tonwhales", "tonfoundation", "tondev", "tontech",
    "cryptohunter", "cryptosignal", "cryptoworld", "cryptolife"
]

# === РАСШИРЕННЫЕ КЛЮЧЕВЫЕ СЛОВА ===
CRYPTO_BASIC_KEYWORDS = ["КРИПТОВАЛЮТА", "CRYPTO", "CRYPTOCURRENCY", "БИТКОИН", "BITCOIN", "BTC", "АЛЬТКОИН", "ALTCOIN", "АЛЬТКОИНЫ", "ALTS", "БЛОКЧЕЙН", "BLOCKCHAIN", "NFT", "НФТ", "СТЕЙКИНГ", "STAKING", "СТЕЙБЛКОИН", "STABLECOIN", "ЭФИРИУМ", "ETHEREUM", "ETH", "SOLANA", "SOL", "CARDANO", "ADA", "POLKADOT", "DOT", "DOGECOIN", "DOGE", "LITECOIN", "LTC", "RIPPLE", "XRP"]
TON_ECOSYSTEM_KEYWORDS = ["TONCOIN", "TON", "ТОН", "THEOPENNETWORK", "TON WALLET", "TON КОШЕЛЕК", "TONKEEPER", "TON SPACE", "TON DEFI", "TON DNS", "TON APPS", "TON APPLICATIONS", "TON FOUNDATION", "TON EXPLORER", "TONSCAN", "TONVIEWER", "GETGEMS", "TON BRIDGE", "TON STAKING", "TON STAKING", "TON SWAP", "TON DEX"]
FINANCE_KEYWORDS = ["ИНВЕСТИЦИИ", "ВЛОЖЕНИЯ", "ДОХОД", "INVEST", "INVESTMENT", "INCOME", "ПРИБЫЛЬ", "ТРЕЙДИНГ", "TRADING", "ТРЕЙДЕР", "TRADER", "CEX", "DEX", "БИРЖА", "EXCHANGE", "КРИПТОБИРЖА", "BINANCE", "BYBIT", "KUCOIN", "OKX", "GATEIO", "HUOBI", "WHITEBIT", "MEXC", "BITGET", "ПОРТФЕЛЬ", "PORTFOLIO", "ДИВИДЕНДЫ", "DIVIDENDS"]
MINING_KEYWORDS = ["МАЙНИНГ", "ФЕРМА", "НАЧИСЛЕНИЯ", "MINING", "EARN", "ЗАРАБОТОК", "ДОБЫЧА", "HASH", "ХЭШ", "МАЙНИТЬ", "МАЙНЕР", "MINER", "МАЙНИНГ ФЕРМА", "MINING FARM", "ASIC", "АСИК", "VIDEOCARD", "ВИДЕОКАРТА", "GPU", "РИГ", "RIG", "ПУЛ", "POOL", "HASHRATE", "ХЭШРЕЙТ", "CLOUD MINING", "ОБЛАЧНЫЙ МАЙНИНГ"]
LOSS_KEYWORDS = ["ПОТЕРЯЛ", "СЛИЛ", "ОБМАН", "SCAM", "LOST", "ПРОИГРАЛ", "УБЫТОК", "МОШЕННИК", "FRAUD", "ОБМАНУЛИ", "УКРАЛИ", "STOLEN", "HACK", "ВЗЛОМ", "ПРОБЛЕМА", "ПРОБЛЕМЫ", "ISSUE", "ERROR", "ОШИБКА", "НЕ РАБОТАЕТ", "NOT WORKING", "КИДАНУЛИ", "ОБМАНУЛИ", "ВОРЫ", "THIEF", "УКРАЛИ ДЕНЬГИ", "НЕ ВЫВОДЯТ", "ЗАБЛОКИРОВАЛИ", "BLOCKED", "ЗАМОРОЗИЛИ", "FROZEN", "ПОДДЕЛЬНЫЙ", "FAKE", "ЛОХОТРОН", "ПИРАМИДА", "PYRAMID"]

# === Проверка базы ===
async def check_database_structure():
    from core.database import engine
    from core.models import Base
    logger.info("Проверка структуры БД...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ База данных готова.")
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке БД: {e}")

# === Получение каналов из списка ===
async def get_predefined_channels():
    channels_to_scan = []
    logger.info("Получаем каналы из списка для сканирования...")
    
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
                logger.info(f"✅ Добавлен канал из списка: {channel}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить {channel}: {e}")
        await asyncio.sleep(0.5)
    
    return channels_to_scan

# === Поиск новых каналов в диалогах ===
async def search_new_channels_in_dialogs(predefined_channels):
    found_channels = []
    predefined_usernames = {ch["username"].lower() for ch in predefined_channels if ch["username"]}
    predefined_titles = {ch["title"].lower() for ch in predefined_channels}
    
    try:
        logger.info("Ищем НОВЫЕ каналы среди диалогов...")
        async for dialog in client.iter_dialogs(limit=150):
            if dialog.is_channel:
                title = getattr(dialog.entity, "title", "").lower()
                username = getattr(dialog.entity, "username", "").lower()
                
                is_predefined = (username in predefined_usernames or 
                               title in predefined_titles or
                               any(predefined in title for predefined in [c.lower() for c in PREDEFINED_CHANNELS]))
                
                if not is_predefined:
                    keywords = [
                        'ton', 'crypto', 'крипт', 'майнинг', 'инвест', 'биткоин', 
                        'blockchain', 'btc', 'eth', 'bitcoin', 'ethereum', 'трейд',
                        'trade', 'coin', 'монета', 'финанс', 'finance', 'деньги', 
                        'money', 'доход', 'earn', 'профит', 'profit', 'mining',
                        'nft', 'defi', 'web3', 'трейдер', 'trader', 'бирж',
                        'staking', 'стейкинг', 'wallet', 'кошелек', 'altcoin', 'альткоин'
                    ]
                    title_lower = title.lower()
                    
                    if any(k in title_lower for k in keywords):
                        found_channels.append({
                            "id": dialog.entity.id,
                            "title": dialog.entity.title,
                            "username": getattr(dialog.entity, "username", ""),
                            "participants_count": getattr(dialog.entity, "participants_count", 0),
                            "source": "discovered"
                        })
                        logger.info(f"🎯 НАЙДЕН НОВЫЙ КАНАЛ: {dialog.entity.title}")
        logger.info(f"Найдено новых каналов из диалогов: {len(found_channels)}")
    except Exception as e:
        logger.error(f"❌ Ошибка при поиске новых каналов: {e}")
    return found_channels

# === Поиск каналов через глобальный поиск ===
async def search_channels_globally(predefined_channels):
    found_channels = []
    predefined_usernames = {ch["username"].lower() for ch in predefined_channels if ch["username"]}
    
    try:
        logger.info("Ищем каналы через глобальный поиск...")
        
        search_keywords = [
            'TON', 'Toncoin', 'TON Wallet', 'Tonkeeper', 'TON DeFi', 'TON DNS',
            'Биткоин', 'Bitcoin', 'BTC', 'Эфириум', 'Ethereum', 'ETH',
            'Криптовалюта', 'Cryptocurrency', 'Crypto', 'Крипта',
            'Blockchain', 'Блокчейн', 'Web3', 'DeFi', 'NFT', 'Майнинг', 'Mining',
            'Инвестиции', 'Investment', 'Трейдинг', 'Trading', 'Биржа', 'Binance',
            'The Open Network', 'TON Foundation', 'Getgems', 'TON Space',
            'Крипто', 'Криптомир', 'Аирдроп', 'Staking', 'Альткоин', 'CEX', 'DEX',
            'Stablecoin', 'Стейблкоин', 'Altcoin', 'Альткоины'
        ]
        
        for keyword in search_keywords:
            try:
                logger.info(f"Ищем по ключевому слову: '{keyword}'")
                result = await client(SearchRequest(q=keyword, limit=50))
                
                new_channels_count = 0
                for chat in result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        username = chat.username.lower()
                        if username not in predefined_usernames:
                            title_lower = chat.title.lower()
                            crypto_keywords = [
                                'ton', 'crypto', 'майнинг', 'инвест', 'биткоин', 'blockchain',
                                'btc', 'eth', 'nft', 'defi', 'web3', 'трейд', 'trade', 'бирж',
                                'wallet', 'кошелек', 'staking', 'стейкинг', 'mining', 'альткоин',
                                'altcoin', 'bitcoin', 'ethereum', 'финанс', 'finance'
                            ]
                            if any(k in title_lower for k in crypto_keywords):
                                channel_info = {
                                    "id": chat.id,
                                    "title": chat.title,
                                    "username": chat.username,
                                    "participants_count": getattr(chat, "participants_count", 0),
                                    "source": "global_search"
                                }
                                if not any(c["id"] == chat.id for c in found_channels):
                                    found_channels.append(channel_info)
                                    new_channels_count += 1
                                    logger.info(f"🔍 Найден через поиск: {chat.title} (@{chat.username})")
                
                if new_channels_count > 0:
                    logger.info(f"По ключу '{keyword}' найдено {new_channels_count} новых каналов")
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка поиска по ключу '{keyword}': {e}")
                continue
                
        logger.info(f"Глобальный поиск завершен. Всего найдено: {len(found_channels)}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка глобального поиска: {e}")
    
    return found_channels

# === ОБНОВЛЕННАЯ ФУНКЦИЯ ОЦЕНКИ ИНТЕРЕСА ===
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
                
                if category == "крипто":
                    score += 15
                elif category == "TON":
                    score += 25
                elif category == "финансы":
                    score += 20
                elif category == "майнинг":
                    score += 30
                elif category == "жалобы":
                    score += 25
        
        if category_found:
            found_keywords.append(category)

    return score, found_keywords

# === Сканирование канала ===
async def scan_channel(channel_info):
    identifier = channel_info["username"] or channel_info["title"]
    source_type = channel_info.get("source", "unknown")
    
    if source_type == "predefined":
        logger.info(f"📖 Читаем канал из списка: {identifier}")
    else:
        logger.info(f"🔍 Сканируем НОВЫЙ канал: {identifier}")

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
                logger.info(f"🎯 Найден лид {message.sender_id} в {identifier} (score={score})")
                await process_lead(message.sender_id, identifier, score, keywords, source_type)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при сканировании {identifier}: {e}")
        return 0

    logger.info(f"📊 {identifier}: {messages_scanned} сообщений, {leads_found} лидов")
    return leads_found

# === Обработка лида ===
async def process_lead(user_id, source_channel, score, keywords, source_type):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Lead).where(Lead.user_id == user_id))
            existing = result.scalar_one_or_none()
            if existing:
                logger.info(f"ℹ️ Лид {user_id} уже существует в БД")
                return

            try:
                user = await client.get_entity(user_id)
                username = getattr(user, "username", None)
                first_name = getattr(user, "first_name", None)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить данные пользователя {user_id}: {e}")
                username = None
                first_name = None

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
                conversion_status="found",
                last_contact=None,
                notes=None
            )
            db.add(lead)
            await db.commit()

            logger.info(f"✅ ЛИД СОХРАНЁН: {user_id} | @{username or '—'} | {source_channel} | score: {score} | keywords: {keywords}")

    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении лида {user_id}: {e}")
        try:
            await db.rollback()
        except:
            pass

# === Фильтрация каналов ===
async def filter_channels(channels):
    filtered_channels = []
    
    for channel in channels:
        channel_id = channel.get("id")
        if channel_id is None:
            logger.debug(f"Пропускаем канал без ID: {channel.get('title', 'Unknown')}")
            continue
            
        if not isinstance(channel_id, int):
            logger.debug(f"Пропускаем канал с некорректным ID: {channel.get('title', 'Unknown')} (ID: {channel_id})")
            continue
            
        if channel_id < 0:
            logger.debug(f"Пропускаем канал с отрицательным ID: {channel.get('title', 'Unknown')} (ID: {channel_id})")
            continue
            
        participants_count = channel.get("participants_count")
        if participants_count is not None and participants_count > 100000:
            logger.debug(f"Пропускаем слишком большой канал: {channel.get('title', 'Unknown')} ({participants_count} участников)")
            continue
            
        filtered_channels.append(channel)
    
    logger.info(f"После фильтрации осталось {len(filtered_channels)} каналов")
    return filtered_channels

# === Основной процесс ===
async def run_scanner():
    await client.start(phone=PHONE)
    logger.info("🚀 Сканер лидов запущен")

    await check_database_structure()

    predefined_channels = await get_predefined_channels()
    new_channels = await search_new_channels_in_dialogs(predefined_channels)
    global_channels = await search_channels_globally(predefined_channels)

    all_channels = predefined_channels + new_channels + global_channels
    all_channels = await filter_channels(all_channels)

    logger.info(f"📊 Всего каналов к сканированию: {len(all_channels)}")

    total_leads = 0
    for channel in all_channels:
        leads = await scan_channel(channel)
        total_leads += leads
        await asyncio.sleep(2)

    logger.info(f"✅ Сканирование завершено. Всего найдено лидов: {total_leads}")

# === ГЛАВНЫЙ ЦИКЛ (для standalone запуска) ===
async def main():
    logger.info("🔍 LEAD SCANNER v2.6 — STARTED")
    while True:
        try:
            # Уникальная сессия для каждого запуска
            session_name = f"scanner_{int(asyncio.get_event_loop().time())}"
            client = TelegramClient(session_name, API_ID, API_HASH)
            
            await run_scanner()
            await client.disconnect()
            
            logger.info("⏰ Сканирование завершено. Ждём 4 часа...")
            await asyncio.sleep(4 * 3600)  # 4 часа
            
        except Exception as e:
            logger.error(f"❌ Ошибка в основном цикле: {e}")
            await asyncio.sleep(3600)  # 1 час при ошибке

# === ИСПРАВЛЕННЫЙ БЛОК ЗАПУСКА ===
if __name__ == "__main__":
    asyncio.run(main())
