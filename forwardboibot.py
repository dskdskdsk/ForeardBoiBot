import asyncio
from pyrogram import Client, filters
import re
import hashlib
import json
import os
import logging
import boto3
import datetime

# Параметри вашого облікового запису Telegram
api_id = "23390151"
api_hash = "69d820891b50ddcdcb9abb473ecdfc32"
session_name = "my_account"

# Ініціалізація клієнта Telegram
app = Client(session_name, api_id=api_id, api_hash=api_hash)

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

# Останні перевірені повідомлення
LAST_CHECKED_MESSAGES = {}

# Список фільтрів
filters_list = ["general cargo"]

# Унікальні хеші повідомлень (в межах однієї сесії)
posted_hashes = set()

# Логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Параметри Amazon S3
S3_BUCKET_NAME = "forwardboibot"
LOCAL_CACHE_DIR = "/tmp/cache"  # Локальна директорія для збереження файлів

# Підключення до S3
s3_client = boto3.client('s3')

def get_monthly_file_name():
    now = datetime.datetime.now()
    return f"hashes_{now.year}_{now.month:02d}.json"

def download_file_from_s3(file_name):
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)
    try:
        s3_client.download_file(S3_BUCKET_NAME, file_name, local_path)
        print(f"Файл {file_name} завантажено з S3.")
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            with open(local_path, 'w') as f:
                json.dump([], f)
            print(f"Файл {file_name} не знайдено на S3. Створено новий локальний файл.")
        else:
            raise
    return local_path

def upload_file_to_s3(file_name):
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    s3_client.upload_file(local_path, S3_BUCKET_NAME, file_name)
    print(f"Файл {file_name} завантажено на S3.")

def read_hashes(file_name):
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    with open(local_path, 'r') as f:
        return json.load(f)

def write_hashes(file_name, hashes):
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    with open(local_path, 'w') as f:
        json.dump(hashes, f)

def add_hashes(new_hashes):
    if not new_hashes:
        logging.info("Немає нових хешів для додавання.")
        return
    file_name = get_monthly_file_name()
    download_file_from_s3(file_name)
    existing_hashes = read_hashes(file_name)
    updated_hashes = list(set(existing_hashes + new_hashes))
    write_hashes(file_name, updated_hashes)
    upload_file_to_s3(file_name)
    print(f"Додано {len(new_hashes)} нових хешів. Загальна кількість: {len(updated_hashes)}")

def load_hashes_from_s3():
    file_name = get_monthly_file_name()
    try:
        download_file_from_s3(file_name)
        return read_hashes(file_name)
    except Exception as e:
        logging.error(f"Помилка завантаження хешів з S3: {e}")
        return []

# Функція створення хешу
def generate_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# Функція отримання динамічних хештегів
def get_dynamic_hashtags(text):
    hashtags = []
    for keyword, hashtag in dynamic_hashtags.items():
        if re.search(rf'\b{keyword}\b', text, re.IGNORECASE):
            hashtags.append(hashtag)
    return hashtags

# Функція отримання існуючих хештегів
def extract_existing_hashtags(text):
    return re.findall(r"#\w+", text)

# Функція видалення хештегів
def remove_hashtags(text):
    return re.sub(r'#\w+', '', text)

# Функція отримання історії з повторними спробами
async def get_chat_history_with_retries(client, channel, retries=5, delay=5):
    for attempt in range(retries):
        try:
            return await client.get_chat_history(channel, limit=10)
        except Exception as e:
            if attempt < retries - 1:
                logging.warning(f"Помилка отримання історії {channel}. Спроба {attempt + 1} з {retries}. Причина: {e}")
                await asyncio.sleep(delay)
            else:
                logging.error(f"Не вдалося отримати історію {channel} після {retries} спроб. Причина: {e}")
                raise

# Основна функція перевірки каналів
async def periodic_channel_check():
    global posted_hashes
    problematic_channels = set()

    while True:
        logging.info("Починається перевірка каналів...")
        for channel in source_channels:
            if channel in problematic_channels:
                logging.warning(f"Пропущено канал {channel} через попередні помилки.")
                continue
            try:
                async for message in await get_chat_history_with_retries(app, channel):
                    if channel not in LAST_CHECKED_MESSAGES or message.id > LAST_CHECKED_MESSAGES[channel]:
                        if message.text and not message.media and not re.search(r'http[s]?://', message.text):
                            post_hash = generate_hash(message.text)
                            if post_hash in posted_hashes:
                                continue

                            if any(phrase.lower() in message.text.lower() for phrase in filters_list):
                                continue

                            original_text = message.text
                            existing_hashtags = extract_existing_hashtags(original_text)
                            cleaned_text = remove_hashtags(original_text)
                            unique_hashtags = set(existing_hashtags + permanent_hashtags)
                            unique_hashtags.update(get_dynamic_hashtags(cleaned_text))
                            formatted_message = message_template.format(
                                content=cleaned_text.strip(),
                                hashtags=" ".join(unique_hashtags)
                            )
                            await app.send_message(target_channel, formatted_message)
                            posted_hashes.add(post_hash)

                        LAST_CHECKED_MESSAGES[channel] = message.id
            except Exception as e:
                logging.error(f"Помилка з каналом {channel}: {e}")
                problematic_channels.add(channel)

        logging.info("Перевірка завершена. Очікування 5 хвилин...")
        await asyncio.sleep(300)

# Завантаження попередніх хешів
posted_hashes.update(load_hashes_from_s3())

# Запуск бота
async def main():
    async with app:
        logging.info("Бот запущений.")
        check_channels_task = asyncio.create_task(periodic_channel_check())
        await app.start()
        await app.idle()
        check_channels_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
