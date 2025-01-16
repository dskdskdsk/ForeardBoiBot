import asyncio
from pyrogram import Client, filters
import re

# Параметри вашого облікового запису
api_id = "23390151"
api_hash = "69d820891b50ddcdcb9abb473ecdfc32"
session_name = "my_account"

# Ініціалізація клієнта
app = Client("my_account", api_id="23390151", api_hash="69d820891b50ddcdcb9abb473ecdfc32")

# Список джерел і цільовий канал
source_channels = [
    "@forwardboibottestchannel",  # Юзернейм або ID джерела
    "source_channel_2",
    "source_channel_3"
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
LAST_CHECKED_MESSAGES = {}

# Зберігаємо фрази для фільтрації
filters_list = ["general cargo"]

# Функція перевірки тексту на динамічні хештеги
def get_dynamic_hashtags(text):
    hashtags = []
    for keyword, hashtag in dynamic_hashtags.items():
        # Точний збіг слова (без врахування регістру)
        if re.search(rf'\b{keyword}\b', text, re.IGNORECASE):
            hashtags.append(hashtag)
    return hashtags

# Функція перевірки каналів
async def check_channels():
    while True:
        for channel in source_channels:
            async for message in app.get_chat_history(channel, limit=10):
                if channel not in LAST_CHECKED_MESSAGES or message.id > LAST_CHECKED_MESSAGES[channel]:
                    # Ігнорувати повідомлення з медіа або посиланнями
                    if message.text and not message.media and not re.search(r'http[s]?://', message.text):
                        # Перевірка на наявність заборонених фраз
                        if any(phrase.lower() in message.text.lower() for phrase in filters_list):
                            print("Пост містить заборонену фразу, не копіюємо.")
                        else:
                            original_text = message.text
                            dynamic_tags = get_dynamic_hashtags(original_text)
                            all_hashtags = " ".join(permanent_hashtags + dynamic_tags)
                            formatted_message = message_template.format(content=original_text, hashtags=all_hashtags)
                            await app.send_message(target_channel, formatted_message)
                    LAST_CHECKED_MESSAGES[channel] = message.id
        print("Перевірка завершена. Засинаємо на 5 хвилин.")
        await asyncio.sleep(300)

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

# Основний блок запуску
async def main():
    async with app:
        print("Бот запущений.")
        await check_channels()  # Запускаємо автоматичну перевірку

if __name__ == "__main__":
    asyncio.run(main())
