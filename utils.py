import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
import subprocess
import sys

def resolve_redirect_url_with_browser(ph_url, browser_context, timeout=10000):
    """
    Использует Playwright для резолва ProductHunt редиректов
    ProductHunt блокирует requests, но браузер работает
    
    Возвращает (final_url, is_accessible)
    """
    try:
        # Создаем новую страницу в контексте
        page = browser_context.new_page()
        
        # Переходим по ссылке (браузер автоматически следует редиректам)
        response = page.goto(ph_url, timeout=timeout, wait_until='domcontentloaded')
        
        # Получаем финальный URL
        final_url = page.url.replace('?ref=producthunt', '')
        
        # Проверяем статус
        is_accessible = response and response.status in [200, 403]
        
        page.close()
        
        return final_url, is_accessible
        
    except Exception as e:
        # Если браузер не смог загрузить страницу
        try:
            page.close()
        except:
            pass
        return ph_url, False


def resolve_redirect_url(ph_url, timeout=10):
    """
    Fallback функция без браузера (для non-PH ссылок)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(ph_url, headers=headers, timeout=timeout, allow_redirects=True)
        final_url = response.url if response.url else ph_url
        is_accessible = response.status_code in [200, 403]
        return final_url, is_accessible
    except requests.RequestException:
        return ph_url, False

def check_website_accessibility(url, timeout=10):
    """
    Проверяет доступность сайта
    Возвращает True, если сайт доступен (200 или 403)
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code in [200, 403]
    except requests.RequestException:
        try:
            response = requests.get(url, timeout=timeout, allow_redirects=True)
            return response.status_code in [200, 403]
        except requests.RequestException:
            return False

def install_playwright_browsers():
    """
    Устанавливает браузеры Playwright если они не установлены
    """
    try:
        print("\n📥 Установка браузера Playwright...")
        print("Это может занять несколько минут при первом запуске.")
        
        # Запускаем playwright install chromium
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Браузер Playwright установлен успешно!")
            return True
        else:
            print(f"⚠ Ошибка установки: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"⚠ Не удалось установить браузер автоматически: {e}")
        print("Попробуйте вручную: playwright install chromium")
        return False


def resolve_urls_batch(products, max_workers=20):
    """
    Резолвит URL из ProductHunt в реальные URL компаний через Playwright
    
    ProductHunt блокирует requests, поэтому используем настоящий браузер.
    Playwright легче чем Camoufox и работает быстрее.
    
    max_workers: количество параллельных браузерных контекстов (5-10 оптимально)
    """
    print(f"\n🔗 Резолв ProductHunt URL ({len(products)} проектов)...")
    print("⚙️ Запуск браузера...")
    
    results = []
    
    # Импортируем Playwright здесь, чтобы поймать ошибку отсутствия браузера
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n❌ Playwright не установлен!")
        print("Установите: pip install playwright")
        return []
    
    # Пытаемся запустить Playwright
    try:
        with sync_playwright() as playwright:
            # Используем Chromium (быстрее всего)
            browser = playwright.chromium.launch(headless=True)
            
            # Создаем контекст браузера с настройками
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US'
            )
            
            print("✓ Браузер запущен")
            
            # Обрабатываем URL последовательно (браузер уже быстрый)
            # Многопоточность с браузером сложна и может вызвать проблемы
            with tqdm(total=len(products), desc="Резолв URL", unit="url") as pbar:
                for product in products:
                    try:
                        real_url, is_accessible = resolve_redirect_url_with_browser(
                            product['website'], 
                            context,
                            timeout=10000
                        )
                        
                        product['website'] = real_url
                        product['is_accessible'] = is_accessible
                        results.append(product)
                        
                    except Exception as e:
                        print(f"\n⚠ Ошибка для {product.get('name', 'Unknown')}: {e}")
                        product['is_accessible'] = False
                        results.append(product)
                    finally:
                        pbar.update(1)
            
            context.close()
            browser.close()
        
    except Exception as e:
        error_msg = str(e)
        
        # Проверяем, связана ли ошибка с отсутствием браузера
        if "Executable doesn't exist" in error_msg or "playwright install" in error_msg:
            print("\n⚠ Браузер Playwright не установлен")
            
            # Предлагаем автоматическую установку
            install_choice = input("Установить браузер автоматически? (Y/n): ").strip().lower()
            
            if install_choice in ['', 'y', 'yes', 'д', 'да']:
                if install_playwright_browsers():
                    print("\n🔄 Повторный запуск резолва URL...")
                    # Рекурсивно вызываем функцию после установки
                    return resolve_urls_batch(products, max_workers)
                else:
                    print("\n❌ Не удалось установить браузер")
                    print("Установите вручную: playwright install chromium")
                    return []
            else:
                print("\n❌ Резолв URL отменен")
                print("Для работы программы установите браузер: playwright install chromium")
                return []
        else:
            # Другая ошибка
            print(f"\n❌ Ошибка Playwright: {e}")
            return []
    
    # Фильтруем только доступные проекты
    accessible_products = [p for p in results if p.get('is_accessible', False)]
    filtered_count = len(results) - len(accessible_products)
    
    print(f"\n✓ Резолв завершен:")
    print(f"  - Доступных проектов: {len(accessible_products)}")
    print(f"  - Недоступных (отфильтровано): {filtered_count}")
    
    if len(accessible_products) == 0:
        print("\n⚠ ВНИМАНИЕ: Все сайты недоступны!")
    
    return accessible_products

