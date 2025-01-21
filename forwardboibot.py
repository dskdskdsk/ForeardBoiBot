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
    "@forwardboibottestchannel",  # Юзернейм або ID джерела
    "@OnlyOffshore",
    "@roster_marine"
]
target_channel = "@thisisofshooore"  # Юзернейм або ID цільового каналу

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

# Зберігаємо фрази для фільтрації
filters_list = ["general cargo"]

# Унікальні хеші повідомлень (в межах однієї сесії)
posted_hashes = set()

# Логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# S3 _____________________________________________________________________________________

S3_BUCKET_NAME = "forwardboibot"
LOCAL_CACHE_DIR = "/tmp/cache"  # Локальна директорія для збереження файлів

# Підключення до S3
s3_client = boto3.client('s3')

def get_monthly_file_name():
    """Отримує назву файлу для поточного місяця."""
    now = datetime.datetime.now()
    return f"hashes_{now.year}_{now.month:02d}.json"

def download_file_from_s3(file_name):
    """Завантажує файл з S3, якщо він існує."""
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)
    
    try:
        s3_client.download_file(S3_BUCKET_NAME, file_name, local_path)
        print(f"Файл {file_name} завантажено з S3.")
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            # Файл не знайдено, створюємо порожній локальний файл
            with open(local_path, 'w') as f:
                json.dump([], f)
            print(f"Файл {file_name} не знайдено на S3. Створено новий локальний файл.")
        else:
            raise
    return local_path

def upload_file_to_s3(file_name):
    """Завантажує файл на S3."""
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    s3_client.upload_file(local_path, S3_BUCKET_NAME, file_name)
    print(f"Файл {file_name} завантажено на S3.")

def read_hashes(file_name):
    """Читає список хешів з локального файлу."""
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    with open(local_path, 'r') as f:
        return json.load(f)

def write_hashes(file_name, hashes):
    """Записує список хешів у локальний файл."""
    local_path = os.path.join(LOCAL_CACHE_DIR, file_name)
    with open(local_path, 'w') as f:
        json.dump(hashes, f)

def add_hashes(new_hashes):
    """Додає нові хеші до файлу за поточний місяць."""
    if not new_hashes:
        logging.info("Немає нових хешів для додавання.")
        return
    file_name = get_monthly_file_name()

    # Завантажуємо файл з S3
    local_file_path = download_file_from_s3(file_name)

    # Читаємо існуючі хеші
    existing_hashes = read_hashes(file_name)

    # Додаємо тільки унікальні хеші
    updated_hashes = list(set(existing_hashes + new_hashes))

    # Записуємо оновлений список хешів
    write_hashes(file_name, updated_hashes)

    # Завантажуємо файл назад на S3
    upload_file_to_s3(file_name)

    print(f"Додано {len(new_hashes)} нових хешів. Загальна кількість: {len(updated_hashes)}")

def load_hashes_from_s3():
    """Завантажує попередні хеші з S3."""
    file_name = get_monthly_file_name()
    try:
        local_file_path = download_file_from_s3(file_name)
        return read_hashes(file_name)
    except Exception as e:
        logging.error(f"Помилка завантаження хешів з S3: {e}")
        return []


# === Приклад використання ===
 
# Нові хеші для додавання
new_hashes_to_add = ["hash1", "hash2", "hash3"]

# Додаємо нові хеші в файл поточного місяця
add_hashes(new_hashes_to_add)


#Хеші ____________________________________________________________________________________
# Функція створення хешу для тексту
def generate_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# Функція перевірки тексту на динамічні хештеги
def get_dynamic_hashtags(text):
    hashtags = []
    for keyword, hashtag in dynamic_hashtags.items():
        if re.search(rf'\b{keyword}\b', text, re.IGNORECASE):
            hashtags.append(hashtag)
    return hashtags

# Функція для отримання хештегів із тексту
def extract_existing_hashtags(text):
    return re.findall(r"#\w+", text)

# Функція для видалення хештегів з тексту
def remove_hashtags(text):
    return re.sub(r'#\w+', '', text)

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

def update_hashes_in_s3(posted_hashes):
    """Оновлює хеші в S3."""
    if posted_hashes:
        logging.info(f"Оновлюємо {len(posted_hashes)} хешів на S3.")
        add_hashes(list(posted_hashes))
    else:
        logging.info("Немає нових хешів для оновлення на S3.")

# Команди для бота в Telegram _____________________________________________________________
 
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

# Команда /set_template
@app.on_message(filters.private & filters.command("set_template"))
async def set_template(_, message):
    global message_template
    new_template = message.text.split(" ", 1)[1] if len(message.text.split(" ", 1)) > 1 else None
    if new_template:
        message_template = new_template
        await message.reply("Шаблон успішно оновлено.")
    else:
        await message.reply("Будь ласка, введіть новий шаблон після команди.")

# Команда /add_hashtag
@app.on_message(filters.private & filters.command("add_hashtag"))
async def add_hashtag(_, message):
    global dynamic_hashtags
    data = message.text.split(" ", 1)[1] if len(message.text.split(" ", 1)) > 1 else None
    if data and ":" in data:
        keyword, hashtag = map(str.strip, data.split(":", 1))
        dynamic_hashtags[keyword.lower()] = hashtag
        await message.reply(f"Додано хештег: {keyword} → {hashtag}")
    else:
        await message.reply("Невірний формат. Використовуйте: /add_hashtag слово:хештег")

# Команда /remove_hashtag
@app.on_message(filters.private & filters.command("remove_hashtag"))
async def remove_hashtag(_, message):
    global dynamic_hashtags
    keyword = message.text.split(" ", 1)[1].strip() if len(message.text.split(" ", 1)) > 1 else None
    if keyword and keyword.lower() in dynamic_hashtags:
        del dynamic_hashtags[keyword.lower()]
        await message.reply(f"Хештег для '{keyword}' видалено.")
    else:
        await message.reply("Такого слова немає в списку динамічних хештегів.")

# Команда /list_hashtags
@app.on_message(filters.private & filters.command("list_hashtags"))
async def list_hashtags(_, message):
    if dynamic_hashtags:
        hashtags_list = "\n".join([f"{k}: {v}" for k, v in dynamic_hashtags.items()])
        await message.reply(f"Список динамічних хештегів:\n{hashtags_list}")
    else:
        await message.reply("Список динамічних хештегів порожній.")

# Команда /show_template
@app.on_message(filters.private & filters.command("show_template"))
async def show_template(_, message):
    await message.reply(f"Поточний шаблон повідомлення:\n{message_template}")

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

# Команда /list_filters
@app.on_message(filters.private & filters.command("list_filters"))
async def list_filters(_, message):
    if filters_list:
        await message.reply(f"Ключові фрази для фільтрації:\n" + "\n".join(filters_list))
    else:
        await message.reply("Немає фраз для фільтрації.")
 
# Команда /check
@app.on_message(filters.private & filters.command("check"))
async def manual_trigger(_, message):
    await message.reply("Запускаємо перевірку каналів...")
    await check_channels()
    await message.reply("Перевірка завершена.")

# Завантаження попередніх хешів
posted_hashes.update(load_hashes_from_s3())

# Запуск бота________________________________________________________________________
async def main():
    async with app:
        logging.info("Бот запущений.")
        while True:
            await check_channels()
            
if __name__ == "main":
    asyncio.run(main())  # Використовується asyncio для асинхронного 
