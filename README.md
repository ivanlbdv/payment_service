# Payment Service

Сервис для управления платежами и заказами с поддержкой эквайринга и наличных платежей.

---

## Описание

Payment Service — это веб‑сервис на базе Django REST Framework, предоставляющий API для:
* создания и отслеживания заказов;
* обработки платежей (эквайринг и наличные);
* синхронизации статусов платежей с внешним банковским шлюзом;
* выполнения возвратов платежей;
* автоматического обновления статусов заказов на основе связанных платежей.

---

## Основные возможности

* **Управление заказами**: создание, просмотр, отслеживание статуса оплаты (не оплачен, частично оплачен, оплачен).
* **Обработка платежей**: поддержка двух типов платежей — наличные и эквайринг.
* **Синхронизация со сторонним банком**: проверка статуса платежа, получение данных о сумме и времени оплаты.
* **Возврат платежей**: возможность отменить завершённый платёж и обновить статус заказа.
* **API‑документация**: автоматическая генерация OpenAPI‑схемы с поддержкой Swagger UI и ReDoc.
* **Логирование**: детальное логирование операций с возможностью записи в файл и консоль.
* **Валидация данных**: проверка корректности сумм, статусов и бизнес‑правил на уровне модели и сериализатора.

---

## Используемые технологии

* Python 3.x
* Django 5.2.12
* Django REST Framework 3.17.1
* PostgreSQL
* Redis (для Celery)
* Celery (планировщик задач)
* drf‑spectacular (генерация API‑документации)
* python‑decouple (управление конфигурацией)

---

## Установка и настройка

### Предварительные требования

* Python 3.10+
* PostgreSQL 12+
* Redis 6+

---

## Запуск проекта

- Клонируйте репозиторий и перейдите в папку проекта:

```bash
git clone git@github.com:ivanlbdv/payment_service.git
cd payment_service
```

- Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

- Настройте переменные окружения: создайте файл .env в корне проекта со следующим содержимым:

```env
DB_NAME=payment_service
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=your_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

- Выполните миграции базы данных:

```bash
python manage.py migrate
```

- Создайте суперпользователя для доступа к админ‑панели:

```bash
python manage.py createsuperuser
```

- Запустите сервер разработки:

```bash
python manage.py runserver
```

- Запустите Celery (если используются асинхронные задачи):

```bash
celery -A payment_service worker -l INFO
```

---

## API Endpoints

Доступ к API осуществляется по префиксу /api/.

### Основные эндпоинты

* GET /api/orders/<int:order_id>/ — получить информацию о заказе с платежами.

* POST /api/orders/<int:order_id>/payments/ — создать новый платёж для заказа.

* POST /api/payments/refund/ — выполнить возврат платежа.

* GET /api/schema/ — OpenAPI‑схема (JSON).

* GET /api/docs/ — Swagger UI (интерактивная документация).

* GET /api/redoc/ — ReDoc (альтернативная документация).

### Примеры запросов

#### Создание платежа

```http
POST /api/orders/1/payments/
Content-Type: application/json

{
  "amount": 500.00,
  "type": "cash"
}
```

#### Возврат платежа

```http
POST /api/payments/refund/
Content-Type: application/json

{
  "payment_id": 1
}
```

---

## Документация API

После запуска сервера доступна интерактивная документация:

Swagger UI: http://localhost:8000/api/docs/

ReDoc: http://localhost:8000/api/redoc/

---

## Тестирование

- Для запуска тестов выполните:

```bash
python manage.py test
```

Покрытие тестами:

1) модели (Order, Payment) — валидация полей, бизнес‑правила;
2) API‑эндпоинты — создание, возврат платежей, получение заказов;
3) Celery‑задачи — синхронизация статусов с банком;
4) админ‑панель — отображение и фильтрация данных.

---

## Логирование

Логи пишутся в:

1) консоль (уровень DEBUG);
2) файл logs/payment_service.log (уровень INFO).

Формат логов:

```
INFO 2026-03-26 10:00:00 payments.models Платёж создан. Order ID: 1, Amount: 500.00
ERROR 2026-03-26 10:01:00 payments.models Ошибка вызова API банка. Order ID: 1. Ошибка: Connection timeout
```

---

## Автор:

Иван Лебедев
https://github.com/ivanlbdv
