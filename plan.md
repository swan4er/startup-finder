# План разработки консольного приложения для поиска идеи стартапа

## Архитектура

Создам модульное приложение со следующей структурой:

- `main.py` - главное CLI меню с интерактивными вопросами
- `config_manager.py` - управление конфигом (токен ProductHunt, куки Crunchbase)
- `producthunt_parser.py` - парсинг ProductHunt через GraphQL API
- `crunchbase_parser.py` - парсинг Crunchbase через autocomplete API + camoufox
- `filters.py` - фильтрация по черному списку, сотрудникам, доступности сайтов
- `utils.py` - вспомогательные функции (редирект resolver, проверка сайтов)
- `requirements.txt` - зависимости

## Основные этапы

### 1. Конфигурация

- Создать `config.json` для хранения токена ProductHunt и куки Crunchbase
- В `config_manager.py` реализовать сохранение/загрузку токена и куки
- При первом запуске или отсутствии токена - запросить у пользователя

### 2. ProductHunt парсинг

На базе `01_parser.py`:

- Адаптировать GraphQL запрос с параметрами (годы, фильтры)
- Фильтровать на этапе парсинга: черный список в названии, количество makers
- Собирать данные: name, description, votesCount, website (PH ссылка), url (producthunt_url), makers, created_at

### 3. Резолв настоящих URL

После парсинга ProductHunt:

- Многопоточно (ThreadPoolExecutor) пройтись по всем PH website ссылкам
- Сделать HEAD/GET запрос с `allow_redirects=True` и получить финальный URL
- Параллельно проверить доступность сайта (200/403 статусы)
- Обновить колонку website на настоящий URL

### 4. Сохранение промежуточного результата

- Экспорт в `producthunt.xlsx` с помощью openpyxl/pandas
- Колонки: name, description, votesCount, website, producthunt_url, makers, created_at

### 5. Crunchbase парсинг - получение куки

- При первом запуске открыть браузер через camoufox
- Показать инструкцию: "Авторизуйтесь на crunchbase.com и нажмите Enter"
- После Enter извлечь куки из браузера и сохранить в config.json
- Если не удастся - показать инструкцию по ручному получению JSON куки

### 6. Crunchbase парсинг - поиск компаний

- Для каждого website из таблицы:
- Отправить запрос к `https://www.crunchbase.com/v4/data/autocompletes?query={website}&collection_ids=organizations&limit=1`
- Извлечь permalink из ответа
- Сформировать crunchbase_url: `https://www.crunchbase.com/organization/{permalink}`
- Добавить колонку crunchbase_url в таблицу

### 7. Crunchbase парсинг - получение funding

- Использовать camoufox в headless режиме с загруженными куками
- Для каждого crunchbase_url:
- Открыть страницу через camoufox
- Найти элемент с селектором `#company_funding .tile-field`, содержащий "$"
- Извлечь текст с суммой инвестиций
- Записать в колонку funding_amount (или оставить пустым, если не найдено)
- Многопоточность на уровне нескольких браузерных инстансов

### 8. Финальная таблица

- Добавить колонки crunchbase_url и funding_amount
- Сохранить финальный результат в `producthunt.xlsx`

## CLI интерфейс

При запуске `main.py`:

1. Проверка токена ProductHunt (запрос, если нет)
2. Меню опций:

- За сколько лет собирать (default: 3)
- Черный список слов через запятую (default: пусто)
- Макс. сотрудников (default: 10)

3. Запуск парсинга с прогресс-баром
4. После ProductHunt - вопрос: продолжить с Crunchbase? (Y/n)
5. Проверка/получение куки Crunchbase
6. Парсинг Crunchbase с прогресс-баром
7. Вывод статистики и путь к файлу

## Технические детали

- Использовать `requests` для API запросов
- `ThreadPoolExecutor` для многопоточности (проверка сайтов, резолв URL)
- `camoufox` для обхода Cloudflare на Crunchbase
- `openpyxl` или `pandas` для работы с Excel
- `tqdm` для прогресс-баров
- Обработка rate limits ProductHunt (пауза при 429)
- Retry логика для failed запросов
