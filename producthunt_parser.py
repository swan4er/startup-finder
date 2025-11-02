import requests
from datetime import datetime, timedelta
import time
from tqdm import tqdm

class ProductHuntParser:
    def __init__(self, token, years=3, blacklist=None, max_makers=10, max_products=5000):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Host': 'api.producthunt.com'
        }
        self.years = years
        self.blacklist = [word.lower() for word in (blacklist or [])]
        self.max_makers = max_makers
        self.max_products = max_products
        
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=years*365)
        self.end_cursor = None
        
    def _is_blacklisted(self, name):
        """Проверяет, содержит ли название слово из черного списка"""
        if not self.blacklist:
            return False
        
        name_lower = name.lower()
        for word in self.blacklist:
            if word in name_lower:
                return True
        return False
    
    def _fetch_page(self):
        """Получает одну страницу результатов от ProductHunt API"""
        end_cursor_query = ''
        if self.end_cursor:
            end_cursor_query = f'after: "{self.end_cursor}",'
        
        query = """
        {
          posts(%s postedAfter: "%s", postedBefore: "%s", order: VOTES) {
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              node {
                name
                description
                votesCount
                url
                website
                createdAt
                makers {
                    id
                }
              }
            }
          }
        }
        """ % (end_cursor_query, self.start_date.isoformat(), self.end_date.isoformat())
        
        try:
            response = requests.post(
                'https://api.producthunt.com/v2/api/graphql',
                json={'query': query},
                headers=self.headers,
                timeout=30
            )
        except requests.RequestException as e:
            print(f"\n❌ Ошибка соединения: {e}")
            return {
                'data': None,
                'status': 0,
                'error': True,
                'reset_in': None,
                'has_next_page': False
            }
        
        if response.status_code == 200:
            resp = response.json()
            
            try:
                self.end_cursor = resp['data']['posts']['pageInfo']['endCursor']
            except (KeyError, TypeError):
                pass
            
            try:
                has_next_page = resp['data']['posts']['pageInfo']['hasNextPage']
            except (KeyError, TypeError):
                has_next_page = False
            
            return {
                'data': resp,
                'status': response.status_code,
                'error': False,
                'reset_in': None,
                'has_next_page': has_next_page
            }
        else:
            # Детальная диагностика ошибки
            print(f"\n❌ HTTP {response.status_code}")
            try:
                resp = response.json()
                print(f"Ответ API: {resp}")
                
                if resp.get('errors'):
                    for error in resp['errors']:
                        if error.get('error') == 'rate_limit_reached':
                            reset_in = error.get('details', {}).get('reset_in', 60)
                            return {
                                'data': None,
                                'status': response.status_code,
                                'error': True,
                                'reset_in': reset_in,
                                'has_next_page': False
                            }
                        print(f"Ошибка API: {error.get('message', error)}")
            except Exception as e:
                print(f"Текст ответа: {response.text[:500]}")
            
            return {
                'data': None,
                'status': response.status_code,
                'error': True,
                'reset_in': None,
                'has_next_page': False
            }
    
    def _process_product(self, node):
        """Обрабатывает один продукт и применяет фильтры"""
        name = node.get('name', '')
        makers_count = len(node.get('makers', []))
        
        # Фильтр: черный список
        if self._is_blacklisted(name):
            return None
        
        # Фильтр: максимальное количество сотрудников
        if makers_count > self.max_makers:
            return None
        
        return {
            'name': name,
            'description': node.get('description', ''),
            'votesCount': node.get('votesCount', 0),
            'website': node.get('website', ''),
            'producthunt_url': node.get('url', ''),
            'makers': makers_count,
            'created_at': node.get('createdAt', '')
        }
    
    def parse(self):
        """
        Парсит ProductHunt и возвращает список отфильтрованных продуктов
        """
        print(f"\n{'='*60}")
        print(f"ПАРСИНГ PRODUCTHUNT")
        print(f"{'='*60}")
        print(f"Период: {self.start_date.strftime('%Y-%m-%d')} - {self.end_date.strftime('%Y-%m-%d')}")
        print(f"Черный список: {', '.join(self.blacklist) if self.blacklist else 'нет'}")
        print(f"Макс. сотрудников: {self.max_makers}")
        print(f"Лимит проектов: {self.max_products}")
        print(f"{'='*60}\n")
        
        products = []
        page = 0
        empty_pages_count = 0  # Счетчик страниц подряд без продуктов
        max_empty_pages = 10   # Лимит пустых страниц подряд
        
        with tqdm(desc="Парсинг страниц", unit="page") as pbar:
            while True:
                page += 1
                pbar.set_description(f"Парсинг страницы {page}")
                
                result = self._fetch_page()
                
                # Обработка ошибок
                if result['error']:
                    if result['status'] == 429 and result['reset_in'] >= 0:
                        reset_in = result['reset_in'] if result['reset_in'] > 0 else 700

                        print(f"\n⏸ Rate limit достигнут. Собрано проектов: {len(products)}")
                        print(f"Поставили на паузу. Парсинг автоматически продолжится через {reset_in} сек...")
                        print("Если хотите остановить парсинг ProductHunt и перейти к следующему шагу, нажмите Ctrl+C")
                        
                        try:
                            time.sleep(reset_in)
                        except KeyboardInterrupt:
                            print("\n⏹ Парсинг остановлен пользователем")
                            break
                        
                        continue
                    elif result['status'] == 401:
                        print(f"\n" + "="*60)
                        print("❌ ОШИБКА АВТОРИЗАЦИИ (401)")
                        print("="*60)
                        print("\nВаш токен не работает. Возможные причины:")
                        print("1. Используется Client ID вместо Developer Token")
                        print("2. Токен скопирован не полностью")
                        print("3. Добавлен префикс 'Bearer ' (не нужен)")
                        print("4. Токен истек или был отозван")
                        print("\n📖 ИНСТРУКЦИЯ ПО ПОЛУЧЕНИЮ ПРАВИЛЬНОГО ТОКЕНА:")
                        print("1. Откройте: https://api.producthunt.com/v2/oauth/applications")
                        print("2. Создайте новое приложение (Create an application)")
                        print("3. Скопируйте 'Developer token' - длинную строку")
                        print("4. НЕ копируйте Client ID или Client Secret!")
                        print("\n💡 Подробная инструкция в файле: TOKEN_GUIDE.md")
                        print("="*60)
                        break
                    else:
                        print(f"\n❌ Ошибка API: {result['status']}")
                        break
                
                # Обработка продуктов
                products_before = len(products)
                
                try:
                    edges = result['data']['data']['posts']['edges']
                    for edge in edges:
                        node = edge['node']
                        product = self._process_product(node)
                        if product:
                            products.append(product)
                except (KeyError, TypeError) as e:
                    print(f"\n⚠ Ошибка обработки данных: {e}")
                    break
                
                # Проверка на пустые страницы подряд
                if len(products) == products_before:
                    empty_pages_count += 1
                else:
                    empty_pages_count = 0
                
                pbar.update(1)
                pbar.set_postfix({'собрано': len(products)})
                
                # Если слишком много страниц подряд без результатов
                if empty_pages_count >= max_empty_pages:
                    print(f"\n⚠ Остановка: {max_empty_pages} страниц подряд без подходящих продуктов")
                    print(f"💡 Попробуйте увеличить 'Макс. сотрудников' в настройках")
                    break
                
                # Проверка лимита проектов
                if len(products) >= self.max_products:
                    print(f"\n✓ Достигнут лимит проектов: {self.max_products}")
                    break
                
                # Проверка на последнюю страницу
                if not result['has_next_page']:
                    print("\n✓ Дошли до конца")
                    break
        
        print(f"\n✓ Парсинг завершен. Собрано продуктов: {len(products)}")
        return products

