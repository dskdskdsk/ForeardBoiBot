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

# Логування команд в Telegram боті
@app.on_message(filters.private & filters.command)
async def log_commands(_, message):
    logging.info(f"Отримана команда: {message.text}")

# Команда /help
@app.on_message(filters.private & filters.command("help"))
async def help_command(_, message):
    """Виводить список доступних команд."""
    help_text = """
Доступні команди:

- **/show_template {шаблон}** — показати шаблон для повідомлень.
- **/set_template {шаблон}** — змінити шаблон для повідомлень.
- **/add_hashtag слово:хештег** — додати динамічний хештег.
- **/remove_hashtag слово** — видалити динамічний хештег.
- **/list_hashtags** — показати список динамічних хештегів.
- **/add_filter {фраза}** — додати фразу для фільтрації.
- **/remove_filter {фраза}** — видалити фразу з фільтрації.
- **/list_filters** — показати список фраз для фільтрації.
- **/addchannel @канал** — додати джерело каналів.
- **/removechannel @канал** — видалити канал зі списку джерел.
- **/list_channels** — показати список усіх джерел.
- **/check** — запустити перевірку каналів вручну.
- **/info** — отримати інформацію про поточні налаштування.
- **/start** — почати роботу з ботом (початкове налаштування).
    """
    logging.info("Список команд відправлено.")
    await message.reply(help_text)

# Команда /show_template
@app.on_message(filters.private & filters.command("show_template"))
async def show_template(_, message):
    await message.reply(f"Поточний шаблон:\n\n{message_template}")

# Команда /set_template
@app.on_message(filters.private & filters.command("set_template"))
async def set_template(_, message):
    """Змінює шаблон для повідомлень."""
    global message_template
    new_template = message.text[len("/set_template "):].strip()
    if new_template:
        message_template = new_template
        logging.info(f"Шаблон оновлено на: {message_template}")
        await message.reply(f"Шаблон оновлено:\n\n{message_template}")
    else:
        await message.reply("Будь ласка, вкажіть новий шаблон після команди.")

# Команда /add_hashtag
@app.on_message(filters.private & filters.command("add_hashtag"))
async def add_hashtag(_, message):
    """Додає новий динамічний хештег."""
    global dynamic_hashtags
    try:
        keyword, hashtag = map(str.strip, message.text[len("/add_hashtag "):].split(":"))
        if keyword and hashtag:
            dynamic_hashtags[keyword] = hashtag
            logging.info(f"Додано динамічний хештег: '{keyword}' => '{hashtag}'")
            await message.reply(f"Додано динамічний хештег:\n'{keyword}' => '{hashtag}'")
        else:
            raise ValueError
    except ValueError:
        await message.reply("Неправильний формат. Використовуйте: /add_hashtag слово:хештег")

# Команда /remove_hashtag
@app.on_message(filters.private & filters.command("remove_hashtag"))
async def remove_hashtag(_, message):
    """Видаляє динамічний хештег."""
    global dynamic_hashtags
    keyword = message.text[len("/remove_hashtag "):].strip()
    if keyword in dynamic_hashtags:
        del dynamic_hashtags[keyword]
        logging.info(f"Хештег для '{keyword}' видалено.")
        await message.reply(f"Хештег для '{keyword}' видалено.")
    else:
        await message.reply(f"Хештег для '{keyword}' не знайдено.")

# Команда /list_hashtag
@app.on_message(filters.private & filters.command("list_hashtags"))
async def list_hashtags(_, message):
    """Показує список динамічних хештегів."""
    if dynamic_hashtags:
        hashtags_list = "\n".join([f"{key}: {value}" for key, value in dynamic_hashtags.items()])
        logging.info("Список динамічних хештегів відправлено.")
        await message.reply(f"Список динамічних хештегів:\n{hashtags_list}")
    else:
        await message.reply("Список динамічних хештегів порожній.")

# Команда /add_filter
@app.on_message(filters.private & filters.command("add_filter"))
async def add_filter(_, message):
    """Додає нову фразу до фільтрів."""
    global filters_list
    phrase = message.text[len("/add_filter "):].strip()
    if phrase and phrase not in filters_list:
        filters_list.append(phrase)
        logging.info(f"Фразу '{phrase}' додано до фільтрів.")
        await message.reply(f"Фразу '{phrase}' додано до фільтрів.")
    else:
        await message.reply(f"Фраза '{phrase}' вже є або не вказано тексту.")

# Команда /remove_filter
@app.on_message(filters.private & filters.command("remove_filter"))
async def remove_filter(_, message):
    """Видаляє фразу з фільтрів."""
    global filters_list
    phrase = message.text[len("/remove_filter "):].strip()
    if phrase in filters_list:
        filters_list.remove(phrase)
        logging.info(f"Фразу '{phrase}' видалено з фільтрів.")
        await message.reply(f"Фразу '{phrase}' видалено з фільтрів.")
    else:
        await message.reply(f"Фраза '{phrase}' не знайдена у фільтрах.")

# Команда /list_filters
@app.on_message(filters.private & filters.command("list_filters"))
async def list_filters(_, message):
    """Показує список фраз для фільтрації."""
    if filters_list:
        filters_text = "\n".join(filters_list)
        logging.info("Список фільтрів відправлено.")
        await message.reply(f"Список фраз для фільтрації:\n{filters_text}")
    else:
        await message.reply("Список фільтрів порожній.")

# Команда /check
@app.on_message(filters.private & filters.command("check"))
async def manual_trigger(_, message):
    """Вручну запускає перевірку каналів."""
    logging.info("Запуск перевірки каналів вручну за допомогою команди /check.")
    await message.reply("Запускаємо перевірку каналів...")
    await check_channels()
    await message.reply("Перевірка завершена.")

# Команда /info
@app.on_message(filters.private & filters.command("info"))
async def get_info(_, message):
    """Надає інформацію про поточний стан бота."""
    logging.info("Отримання інформації про стан бота за допомогою команди /info.")
    info_message = (
        f"Інформація про бота:\n"
        f"- Перевіряється {len(source_channels)} каналів.\n"
        f"- Кількість збережених хешів: {len(posted_hashes)}\n"
        f"- Цільовий канал: {target_channel}\n"
        f"- Статус: Активний\n"
        f"- Час до наступної перевірки: 6 годин."
    )
    await message.reply(info_message)

# Використовуємо єдиний список для каналів
source_channels = []

# Команда /addchannel
@app.on_message(filters.private & filters.command("addchannel"))
async def add_channel(_, message):
    """Додає новий канал до списку джерел."""
    try:
        channel = message.text.split(" ", 1)[1].strip()
        if not channel.startswith("@"):
            raise ValueError("Канал повинен починатися з '@'.")
        if channel in source_channels:
            await message.reply(f"Канал {channel} вже є в списку джерел.")
            return
        source_channels.append(channel)
        logging.info(f"Канал {channel} додано до списку джерел.")
        await message.reply(f"Канал {channel} успішно додано.")
    except IndexError:
        await message.reply("Будь ласка, вкажіть канал у форматі '@channel'.")
    except Exception as e:
        logging.error(f"Помилка при додаванні каналу: {e}")
        await message.reply(f"Помилка: {e}")

# Команда /removechannel
@app.on_message(filters.private & filters.command("removechannel"))
async def remove_channel(_, message):
    """Видаляє канал із списку джерел."""
    try:
        channel = message.text.split(" ", 1)[1].strip()
        if channel not in source_channels:
            await message.reply(f"Каналу {channel} немає в списку джерел.")
            return
        source_channels.remove(channel)
        logging.info(f"Канал {channel} видалено зі списку джерел.")
        await message.reply(f"Канал {channel} успішно видалено.")
    except IndexError:
        await message.reply("Будь ласка, вкажіть канал у форматі '@channel'.")
    except Exception as e:
        logging.error(f"Помилка при видаленні каналу: {e}")
        await message.reply(f"Помилка: {e}")

# Команда /list_channels
@app.on_message(filters.command("list_channels") & filters.private)
async def list_channels(client, message):
    """Показує список каналів, які підключені до бота."""
    if source_channels:
        channels_list = "\n".join(source_channels)
        await message.reply(f"Ваші канали:\n{channels_list}")
    else:
        await message.reply("У вас немає підключених каналів.")

# Команда /hashinfo
@app.on_message(filters.private & filters.command("hashinfo"))
async def hash_info(_, message):
    """Показує загальну інформацію про збережені хеші."""
    logging.info("Запит інформації про збережені хеші через команду /hashinfo.")
    hash_message = (
        f"Інформація про збережені хеші:\n"
        f"- Загальна кількість хешів: {len(posted_hashes)}\n"
        f"- Локальний кеш файл: {'Знайдено' if os.path.exists(LOCAL_CACHE_FILE) else 'Не знайдено'}\n"
        f"- Хеш-файл у S3: {S3_FILE_KEY}\n"
    )
    await message.reply(hash_message)

# Команда /start
@app.on_message(filters.private & filters.command("start"))
async def start_command(_, message):
    """Початкове привітання та коротке пояснення функціоналу."""
    start_text = """
Привіт! 👋
Я бот для автоматизації обробки постів із Telegram-каналів. Ось що я можу:
- Переносити пости з каналів-джерел у ваш цільовий канал.
- Додавати/видаляти хештеги та фільтрувати контент.
- Гнучко налаштовувати шаблони повідомлень.

Список доступних команд:
- **/help** — Показати всі доступні команди.

Налаштуйте мене під свої потреби та запустіть обробку командою **/check**!
"""
    logging.info("Користувач викликав команду /start.")
    await message.reply(start_text)

# === Основна функція перевірки каналів ===
async def check_channels():
    global posted_hashes
    for channel in source_channels:
        logging.info(f"Перевірка каналу: {channel}")  # Лог для кожного каналу
        async for message in app.get_chat_history(channel, limit=10):
            logging.info(f"Перевірка повідомлення з каналу {channel}, ID {message.id}")  # Лог для кожного повідомлення
            if channel not in LAST_CHECKED_MESSAGES or message.id > LAST_CHECKED_MESSAGES[channel]:
                if message.text and not message.media and not re.search(r'http[s]?://', message.text):
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
    logging.info("Перевірка завершена. Засинаємо на 6 годин.")
    await asyncio.sleep(21600)

# === Завантаження попередніх хешів ===
posted_hashes = load_hashes_from_s3()

# === Запуск бота ===
async def main():
    async with app:
        logging.info("Бот запущений.")
        await check_channels()

if __name__ == "__main__":
    app.run(main())
