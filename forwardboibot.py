reply(f"Додано хештег: {keyword} → {hashtag}")
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

if name == "__main__":
    asyncio.run(main())
