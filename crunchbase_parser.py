# ГАЙД ПО ПАРСИНГУ КРАНЧБАЗЕ. НЕ УДАЛЯТЬ РУКИ ОТОРВУ https://www.scrapingbee.com/blog/how-to-scrape-with-camoufox-to-bypass-antibot-technology/

import time
from urllib.parse import quote
from tqdm import tqdm
from camoufox.sync_api import Camoufox


class CrunchbaseParser:
    def __init__(self):
        self.base_url = "https://www.crunchbase.com"
        self.user_data_dir = 'user-data-dir'
        
        # Конфиг для Camoufox из гайда
        self.camoufox_config = {
            'window.outerHeight': 1056,
            'window.outerWidth': 1920,
            'window.innerHeight': 1008,
            'window.innerWidth': 1920,
            'window.history.length': 4,
            'navigator.userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
            'navigator.appCodeName': 'Mozilla',
            'navigator.appName': 'Netscape',
            'navigator.appVersion': '5.0 (Windows)',
            'navigator.oscpu': 'Windows NT 10.0; Win64; x64',
            'navigator.language': 'en-US',
            'navigator.languages': ['en-US'],
            'navigator.platform': 'Win32',
            'navigator.hardwareConcurrency': 12,
            'navigator.product': 'Gecko',
            'navigator.productSub': '20030107',
            'navigator.maxTouchPoints': 10,
        }
    
    def search_organization(self, website, page):
        """
        Ищет организацию на Crunchbase по website через уже открытую страницу
        Возвращает (crunchbase_url, success)
        """
        try:
            encoded_website = quote(website)
            url = f"{self.base_url}/v4/data/autocompletes?query={encoded_website}&collection_ids=organizations&limit=1"
            
            # Делаем fetch через JavaScript чтобы получить чистый JSON
            result = page.evaluate(f"""
                async () => {{
                    const response = await fetch('{url}');
                    return await response.json();
                }}
            """)
            
            if result.get('count', 0) > 0 and result.get('entities') and len(result['entities']) > 0:
                entity = result['entities'][0]
                if entity.get('identifier') and entity['identifier'].get('permalink'):
                    permalink = entity['identifier']['permalink']
                    crunchbase_url = f"{self.base_url}/organization/{permalink}"
                    return crunchbase_url, True
            
            return None, False
                
        except Exception as e:
            print(f"\n⚠ Ошибка поиска на Crunchbase для {website}: {e}")
            return None, False
    
    def setup_authentication(self):
        """
        Открывает браузер для авторизации пользователя на Crunchbase
        Куки автоматически сохраняются в user-data-dir
        """
        print("\n" + "="*70)
        print("АВТОРИЗАЦИЯ НА CRUNCHBASE")
        print("="*70)
        print("Сейчас откроется браузер. Выполните следующие шаги:")
        print("1. Пройдите капчу (если появится)")
        print("2. Авторизуйтесь на Crunchbase (не закрывайте браузер)")
        print("3. После успешной авторизации нажмите Enter в консоли")
        print("="*70)
        
        with Camoufox(
            headless=False, 
            persistent_context=True,
            user_data_dir=self.user_data_dir,
            os=('windows'),
            config=self.camoufox_config,
            i_know_what_im_doing=True
        ) as browser:
            # Используем первую существующую страницу вместо создания новой
            pages = browser.pages
            if pages:
                page = pages[0]
            else:
                page = browser.new_page()
            
            page.goto("https://www.crunchbase.com/login")
            
            input("\n[Нажмите Enter после авторизации]")
            
            print("✓ Авторизация завершена, куки сохранены")
    
    def search_organizations_batch(self, products):
        """
        Ищет организации на Crunchbase для списка продуктов
        Добавляет ключ crunchbase_url к каждому продукту
        """
        print(f"\n🔍 Поиск компаний на Crunchbase ({len(products)} проектов)...")
        
        found_count = 0
        
        # Используем persistent context с сохраненными куками
        with Camoufox(
            headless=True, 
            persistent_context=True,
            user_data_dir=self.user_data_dir,
            os=('windows'),
            config=self.camoufox_config,
            i_know_what_im_doing=True
        ) as browser:
            # Используем первую существующую страницу вместо создания новой
            pages = browser.pages
            if pages:
                page = pages[0]
            else:
                page = browser.new_page()
            
            # Открываем главную страницу один раз
            page.goto("https://www.crunchbase.com", timeout=30000, wait_until='domcontentloaded')
            time.sleep(2)
            
            # Последовательно обрабатываем все продукты
            with tqdm(total=len(products), desc="Поиск на CB", unit="comp") as pbar:
                for product in products:
                    crunchbase_url, success = self.search_organization(product['website'], page)
                    if success and crunchbase_url:
                        product['crunchbase_url'] = crunchbase_url
                        found_count += 1
                    else:
                        product['crunchbase_url'] = ''
                    
                    pbar.update(1)
                    pbar.set_postfix({'найдено': found_count})
        
        print(f"✓ Найдено на Crunchbase: {found_count}/{len(products)}")
        return products
    
    def get_funding_amount(self, crunchbase_url, page):
        """
        Получает funding amount со страницы Crunchbase через открытую page
        """
        try:
            page.goto(crunchbase_url, timeout=60000, wait_until='networkidle')
            time.sleep(3)
            
            # Ищем элемент с funding
            try:
                overview_funding = page.query_selector('#overview_funding')
                if overview_funding:
                    links = overview_funding.query_selector_all('a')
                    for link in links:
                        text = link.inner_text()
                        if '$' in text:
                            return text.strip()
            except Exception:
                pass
            
            return None
            
        except Exception as e:
            print(f"\n⚠ Ошибка получения funding для {crunchbase_url}: {e}")
            return None
    
    def get_funding_amounts_batch(self, products):
        """
        Получает funding amounts для списка продуктов через camoufox
        """
        # Отслеживаем дубликаты crunchbase_url
        seen_urls = {}
        
        for p in products:
            cb_url = p.get('crunchbase_url')
            if cb_url:
                if cb_url not in seen_urls:
                    seen_urls[cb_url] = p['website']
                else:
                    p['crunchbase_url'] = ''
        
        # Фильтруем только продукты с непустым crunchbase_url
        products_with_cb = [p for p in products if p.get('crunchbase_url')]
        
        if not products_with_cb:
            print("\n⚠ Нет продуктов с Crunchbase URL для парсинга funding")
            return products
        
        print(f"\n💰 Парсинг funding amounts ({len(products_with_cb)} компаний)...")
        
        # Создаем mapping для быстрого обновления
        products_dict = {p['website']: p for p in products}

        # Используем persistent context с сохраненными куками
        with Camoufox(
            headless=True, 
            persistent_context=True,
            user_data_dir=self.user_data_dir,
            os=('windows'),
            config=self.camoufox_config,
            i_know_what_im_doing=True
        ) as browser:
            page = browser.new_page()
            
            # Парсим все страницы
            with tqdm(total=len(products_with_cb), desc="Парсинг funding", unit="comp") as pbar:
                for product in products_with_cb:
                    crunchbase_url = product.get('crunchbase_url')
                    if crunchbase_url:
                        funding = self.get_funding_amount(crunchbase_url, page)
                        products_dict[product['website']]['funding_amount'] = funding or ''
                    
                    pbar.update(1)
            
            # Для продуктов без crunchbase_url устанавливаем пустой funding
            for product in products_dict.values():
                if 'funding_amount' not in product:
                    product['funding_amount'] = ''
        
        print(f"✓ Парсинг funding завершен")
        return list(products_dict.values())
