import os
import json
import datetime
import boto3

# Конфігурація S3
S3_BUCKET_NAME = "your-bucket-name"
LOCAL_CACHE_DIR = "cache"  # Локальна директорія для збереження файлів

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

# === Приклад використання ===

# Нові хеші для додавання
new_hashes_to_add = ["hash1", "hash2", "hash3"]

# Додаємо нові хеші в файл поточного місяця
add_hashes(new_hashes_to_add)
