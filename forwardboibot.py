import asyncio
from pyrogram import Client, filters
import re
import hashlib
import json
import os
import logging
import boto3

# === Налаштування ===
# Параметри вашого облікового запису
api_id = "23390151"
api_hash = "69d820891b50ddcdcb9abb473ecdfc32"
session_name = "my_account"

# S3
S3_BUCKET = "forwardboibot"
S3_FILE_KEY = "posted_hashes.json"
LOCAL_CACHE_FILE = "posted_hashes_cache.json"

# Список джерел і цільовий канал
source_channels = [
    "@forwardboibottestchannel",
    "@OnlyOffshore",
    "@roster_marine"
]
target_channel = "@thisisofshooore"

# Початкові налаштування
message_template = "Новий пост з каналу:\n\n{content}\n\n{hashtags}"
permanent_hashtags = ["#Новини", "#Telegram"]
dynamic_hashtags = {
    "Chief mate": "#Python",
    "dp2": "#DP2",
    "offshore": "#AI"
}
filters_list = ["general cargo"]

# Логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Унікальні хеші повідомлень
posted_hashes = set()

# Останні перевірені повідомлення
LAST_CHECKED_MESSAGES = {}

# === Функції роботи з S3 ===
def load_hashes_from_s3():
    """Завантаження хешів із S3 або локального кешу."""
    if os.path.exists(LOCAL_CACHE_FILE):
        with open(LOCAL_CACHE_FILE, "r") as f:
            return set(json.load(f))

    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_FILE_KEY)
        hashes = json.loads(response['Body'].read().decode())
        with open(LOCAL_CACHE_FILE, "w") as f:
            json.dump(hashes, f)  # Зберігаємо локальну копію
        return set(hashes)
    except s3.exceptions.NoSuchKey:
        return set()
    except Exception as e:
        logging.error(f"Помилка при завантаженні хешів із S3: {e}")
        return set()

def update_hashes_in_s3(posted_hashes):
    """Оновлення хешів у S3 із використанням тимчасового файлу."""
    temp_file = "temp_hashes.json"
    with open(temp_file, "w") as f:
        json.dump(list(posted_hashes), f)

    s3 = boto3.client("s3")
    try:
        s3.upload_file(temp_file, S3_BUCKET, S3_FILE_KEY)
        os.replace(temp_file, LOCAL_CACHE_FILE)  # Оновлюємо локальний кеш
    except Exception as e:
        logging.error(f"Помилка при оновленні хешів у S3: {e}")

# === Допоміжні функції ===
def generate_hash(text):
    """Генерує хеш для тексту."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def extract_existing_hashtags(text):
    """Витягує всі хештеги з тексту."""
    return re.findall(r"#\w+", text)

def remove_hashtags(text):
    """Видаляє всі хештеги з тексту."""
    return re.sub(r"#\w+", "", text)

def get_dynamic_hashtags(text):
    """Отримує динамічні хештеги на основі ключових слів."""
    return [hashtag for keyword, hashtag in dynamic_hashtags.items() if re.search(rf'\b{keyword}\b', text, re.IGNORECASE)]

# === Створення об'єкта Client ===
app = Client(session_name, api_id=api_id, api_hash=api_hash)

# Команда /help
@app.on_message(filters.private & filters.command("help"))
async def help_command(_, message):
    help_text = """
Доступні команди:
- /set_template {шаблон} — змінити шаблон для повідомлень.
- /add_hashtag слово:хештег — додати динамічний хештег.
- /remove_hashtag слово — видалити динамічний хештег.
- /list_hashtags — показати список динамічних хештегів.
- /show_template — показати поточний шаблон повідомлення.
- /check — запустити перевірку каналів вручну.
- /add_filter {фраза} — додати фразу для фільтрації.
- /remove_filter {фраза} — видалити фразу з фільтрації.
- /list_filters — показати список фраз для фільтрації.
"""
    await message.reply(help_text)

# Команда /add_filter
@app.on_message(filters.private & filters.command("add_filter"))
async def add_filter(_, message):
    global filters_list
    phrase = " ".join(message.text.split()[1:])  # Отримуємо фразу без команди
    if phrase and phrase not in filters_list:
        filters_list.append(phrase)
        await message.reply(f"Фразу '{phrase}' додано до фільтрів.")
    else:
        await message.reply(f"Фраза '{phrase}' вже є або не вказано тексту.")

# Команда /remove_filter
@app.on_message(filters.private & filters.command("remove_filter"))
async def remove_filter(_, message):
    global filters_list
    phrase = " ".join(message.text.split()[1:])
    if phrase in filters_list:
        filters_list.remove(phrase)
        await message.reply(f"Фразу '{phrase}' видалено з фільтрів.")
    else:
        await message.reply(f"Фраза '{phrase}' не знайдена у фільтрах.")

# Команда /check
@app.on_message(filters.private & filters.command("check"))
async def manual_trigger(_, message):
    await message.reply("Запускаємо перевірку каналів...")
    await check_channels()
    await message.reply("Перевірка завершена.")

# === Основна функція перевірки каналів ===
async def check_channels():
    global posted_hashes
    for channel in source_channels:
        async for message in app.get_chat_history(channel, limit=10):
            if channel not in LAST_CHECKED_MESSAGES or message.id > LAST_CHECKED_MESSAGES[channel]:
                # Ігноруємо повідомлення з медіа або посиланнями
                if message.text and not message.media and not re.search(r'http[s]?://', message.text):
                    # Генеруємо хеш поста для унікальності
                    post_hash = generate_hash(message.text)
                    if post_hash in posted_hashes:
                        logging.info(f"Цей пост із ID {message.id} вже оброблений.")
                        continue

                    # Перевірка на заборонені фрази
                    if any(phrase.lower() in message.text.lower() for phrase in filters_list):
                        logging.info(f"Пост із ID {message.id} містить заборонені фрази.")
                        continue

                    original_text = message.text

                    # Витягуємо існуючі хештеги та видаляємо їх з тексту
                    existing_hashtags = extract_existing_hashtags(original_text)
                    cleaned_text = remove_hashtags(original_text)

                    # Формуємо список унікальних хештегів
                    unique_hashtags = set(existing_hashtags + permanent_hashtags)
                    dynamic_tags = get_dynamic_hashtags(cleaned_text)
                    unique_hashtags.update(dynamic_tags)

                    # Формуємо кінцевий текст
                    formatted_message = message_template.format(
                        content=cleaned_text.strip(),
                        hashtags=" ".join(unique_hashtags)
                    )

                    # Надсилаємо повідомлення
                    await app.send_message(target_channel, formatted_message)

                    # Зберігаємо хеш поста, щоб уникнути дублювання
                    posted_hashes.add(post_hash)

                # Оновлюємо останнє перевірене повідомлення для каналу
                LAST_CHECKED_MESSAGES[channel] = message.id

    update_hashes_in_s3(posted_hashes)
    logging.info("Перевірка завершена. Засинаємо на 5 хвилин.")
    await asyncio.sleep(300)

# === Завантаження попередніх хешів ===
posted_hashes = load_hashes_from_s3()

# === Запуск бота ===
async def main():
    async with app:
        logging.info("Бот запущений.")
        await check_channels()

if __name__ == "__main__":
    app.run(main())
