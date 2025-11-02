import json
import os

CONFIG_FILE = 'config.json'

def load_config():
    """Загружает конфигурацию из файла"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    """Сохраняет конфигурацию в файл"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def get_producthunt_token():
    """Получает токен ProductHunt из конфига или запрашивает у пользователя"""
    config = load_config()
    
    if 'producthunt_token' in config and config['producthunt_token']:
        return config['producthunt_token']
    
    print("\n" + "="*60)
    print("НАСТРОЙКА ТОКЕНА PRODUCTHUNT")
    print("="*60)
    print("Токен не найден в конфигурации.")
    print("\nИнструкция по получению токена:")
    print("1. Перейдите на https://www.producthunt.com/")
    print("2. Войдите в аккаунт (или создайте новый)")
    print("3. Перейдите на https://api.producthunt.com/v2/oauth/applications")
    print("4. Нажмите 'Create an application'")
    print("5. Заполните форму и создайте приложение")
    print("6. Скопируйте 'Developer token' (это длинная строка)")
    print("7. Вставьте токен ниже (без префикса 'Bearer ')")
    print("\nФормат токена: abc123-defGHI456_jklMNO789")
    print("="*60)
    
    token = input("\nВведите токен ProductHunt: ").strip()
    
    if not token:
        raise ValueError("Токен не может быть пустым")
    
    config['producthunt_token'] = token
    save_config(config)
    print("✓ Токен сохранен в config.json\n")
    
    return token


