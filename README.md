# HundredFlags SDK

Python-клиент для работы с агентными средами полигона HundredFlags.
SDK получает документацию конкретной задачи и вызывает тот же `agent-env` API,
которым пользуется браузер: состояние, действия, проверку и сброс.

## Установка

Требуется Python 3.12 или новее.

```sh
python -m pip install hundredflags-sdk
```

Для воспроизводимой установки этой версии:

```sh
python -m pip install hundredflags-sdk==0.6.2
```

Версия 0.6.2 работает с существующими экземплярами `agent-env` и их задачами.
Она требует обновлённого API документации: `task.documentation()` возвращает
текущую открытую часть состояния и действия. Обновляйте SDK вместе с платформой;
отдельные лаборатории или прогоны создавать не нужно.

При переходе с 0.5 замените обращения к `docs.instructions` и `docs.description`
на `docs.state` и `docs.actions`. Легенда и цель остаются на странице задачи.
`Client()` теперь читает токен из окружения; `RuntimeResponse.attempt_completed`
отделяет результат текущей попытки от уже полученного зачёта `completed`.

## Переход с ai-security-school-sdk

Пакет называется `hundredflags-sdk`. Начиная с 0.5.0 поддерживается только
импорт `hundredflags_sdk`; модуль совместимости `ai_security_school_sdk` удалён.
Идентификаторы задач и методы работы с ними сохранены.

Для перехода из существующего окружения:

```sh
python -m pip uninstall ai-security-school-sdk
python -m pip install --upgrade hundredflags-sdk
```

Удалите старую зависимость из `pyproject.toml` или `requirements.txt`, заменив
её на `hundredflags-sdk`. Во всём коде замените `ai_security_school_sdk` на
`hundredflags_sdk`, в том числе в импортах подмодулей `errors` и `models`.
Старый проект `ai-security-school-sdk` удалён из PyPI.

`AI_SECURITY_SCHOOL_TOKEN` и `AI_SECURITY_SCHOOL_BASE_URL` остаются совместимыми
именами переменных окружения. `HUNDREDFLAGS_TOKEN` и `HUNDREDFLAGS_BASE_URL`
имеют приоритет, когда заданы; явно переданный токен имеет приоритет над ними.

## Подключение и документация

На странице операции откройте инструкцию подключения. Создайте временный API-ключ
в личном кабинете платформы и передайте его через переменную окружения. Ключ
принадлежит вашему аккаунту и работает со всеми доступными вам задачами;
конкретную задачу выбирайте по её `task_id` в SDK.
`HUNDREDFLAGS_BASE_URL` можно задать для другого развёртывания; по умолчанию
используется `https://plgn.hundredflags.ru`.

`Client()` и `AsyncClient()` читают токен из `HUNDREDFLAGS_TOKEN`, если аргумент
`token` не задан или равен `None`. Явно переданный пустой или некорректный токен
вызывает `ConfigurationError`. Для чтения адреса из `HUNDREDFLAGS_BASE_URL`
используйте `Client.from_env()` или `AsyncClient.from_env()`; параметры этих
методов имеют приоритет над переменными окружения.

```sh
export HUNDREDFLAGS_TOKEN="YOUR_TOKEN"
```

```python
from hundredflags_sdk import Client

with Client() as client:
    for env in client.envs.list():
        print(env.instance_id, env.title)
        for task in env.tasks.list():
            print(task.task_id, task.title)

    task = client.tasks.get("YOUR_TASK_ID")
    docs = task.documentation()
    print(docs.status, docs.state)
    print(docs.action_payload_schema)
    print(docs.action_payload_examples)
    for action in docs.actions:
        print(action.name, action.description, action.input_schema, action.examples)
```

`client.envs.get(instance_id)` возвращает одну среду. `env.tasks.list()` возвращает
задачи из полученного списка; `env.tasks.get(task_id)` загружает документацию
выбранной задачи. Среда соответствует `agent-env-instance`, задача —
`ctf-instance`. Каждый вызов `task.documentation()` возвращает актуальную открытую
часть состояния в `docs.state` и доступные действия с описанием их назначения.
Условие задачи читается в интерфейсе платформы. Закрытое состояние среды и
внутренние инструменты агента в документацию не попадают. Набор действий и схемы
приходят с сервера, поэтому новая задача не требует новой версии SDK.

## Выполнение действий

Для действия с именем используйте `task.actions.ИМЯ(**arguments)` или
`task.actions.call(name, arguments)`.
Имя и аргументы выбираются из документации конкретной задачи:

```python
with Client.from_env() as client:
    task = client.tasks.get("YOUR_TASK_ID")
    print(task.actions.list())

    # Используйте это имя только если оно есть в документации выбранной задачи.
    result = task.actions.send_message(message="Проверь новый документ")
    print(result.status, result.response, result.state)
    print(task.state().model_dump())
```

Вызов без аргументов выглядит как `task.actions.read_public()`, а в async-клиенте —
`await task.actions.read_public()`, если это действие опубликовано в документации
задачи. Вызов через точку принимает именованные аргументы; эквивалентный вариант
со словарём — `task.actions.call("send_message", {"message": "Проверь новый документ"})`.

Оба варианта заново получают документацию перед выполнением и проверяют, что
действие доступно и аргументы соответствуют актуальной схеме. Получение атрибута
само по себе не отправляет запрос; `dir(task.actions)` показывает действия из
последнего снимка документации. Для действий с именами `list`, `call`, начинающихся
с `_` или не подходящих для Python-атрибута используйте `.call(name, arguments)`.
Методы SDK сохраняют своё назначение.

Метод вставляет поле `action` в тело запроса. В `arguments` передаются остальные
поля; `input_schema` и `examples` описанного действия не содержат `action`.
SDK проверяет аргументы и полное тело по JSON Schema перед отправкой. Сервер
применяет проверки существующего обработчика действия, а также контролирует
доступ, пререквизиты и бюджет пользователя.

`task.act(payload)` принимает полное нативное тело действия. Так поддерживаются
и существующие среды, у которых нет именованных действий, например чат:

```python
with Client.from_env() as client:
    task = client.tasks.get("YOUR_CHAT_TASK_ID")
    docs = task.documentation()
    print(docs.action_payload_schema, docs.action_payload_examples)
    result = task.act({"message": "Привет"})
    print(result.model_dump())
```

Пустой `docs.actions` не означает отсутствие возможностей: используйте полную
схему `action_payload_schema`. SDK не угадывает имена действий по коду runtime.
Документация не исполняется как Python-код, внешние ссылки JSON Schema не
загружаются. Внешние поверхности сценария, например MCP-сервис или реестр
зависимостей, используются через их собственные интерфейсы.

## Состояние, проверка и сброс

```python
with Client.from_env() as client:
    task = client.tasks.get("YOUR_TASK_ID")
    current = task.state()
    print(current.status, current.missing_prerequisites)

    if task.documentation().supports_standalone_grading:
        verdict = task.grade()
        print(verdict.grader_passed, verdict.grader_result, verdict.attempt_completed)

    # При необходимости передайте task.grade({...}) полезную нагрузку проверки.
    # Явный сброс через существующее поведение среды:
    # task.reset()
```

`supports_grading` означает наличие оценивания вообще; `supports_standalone_grading`
разрешает отдельный вызов `grade()`. Некоторые задания оценивают ответ внутри
своих действий, например `submit_card` или `submit_finding`.

Браузер и скрипты одного пользователя разделяют состояние одной задачи.
Разные задачи разделяют его только в средах с общей областью состояния;
документная среда хранит отдельное состояние для каждой задачи. Получение нового
handle или создание второго клиента не создаёт отдельную попытку. Сброс действует
в области состояния, заданной средой, и очищает
результат текущей попытки (`attempt_completed=False`). Уже полученный зачёт
сохраняется: `completed=True` продолжает обозначать глобальное прохождение задачи.
Локальный контекстный менеджер закрывает только HTTP-соединения.

Алгоритм атаки работает в вашем Python-процессе. Вызовы возвращают обычные ответы
runtime без фоновых заданий SDK, checkpoint, fork или воспроизведения сценария.
Вызовы одной среды выполняйте последовательно: параллельные кандидаты будут
менять одно состояние. Async-клиент удобен для неблокирующего ожидания и работы
с разными независимыми средами.

## Async

```python
import asyncio
from hundredflags_sdk import AsyncClient


async def main():
    async with AsyncClient.from_env() as client:
        task = await client.tasks.get("YOUR_TASK_ID")
        docs = await task.documentation()
        print(docs.status, docs.state)
        for action in docs.actions:
            print(action.name, action.description)
        result = await task.act({"message": "Привет"})  # Если разрешено схемой.
        print(result.response)
        print((await task.state()).state)


asyncio.run(main())
```

Методы async-ресурсов, включая `env.tasks.list()`, вызываются через `await`.
Конструкторы, `from_env()`, поля `.info`, `.task_id`, `.instance_id` и `.title`
синхронные. `task.documentation()` обновляет снимок `.info`; `task.state()`
получает текущее серверное состояние. Дополнительные поля ответов сохраняются
в моделях и доступны через `model_dump()`.

Примеры: [документация и вызов](https://github.com/ai-security-lab-itmo/hundredflags-sdk/blob/v0.6.2/examples/first_experiment.py),
[последовательный поиск кандидатов](https://github.com/ai-security-lab-itmo/hundredflags-sdk/blob/v0.6.2/examples/async_search.py),
[связанные задачи одной среды](https://github.com/ai-security-lab-itmo/hundredflags-sdk/blob/v0.6.2/examples/multistage.py).

## Ошибки и сетевые повторы

- `APIError` содержит `code`, `message`, `status_code`, `details` и `usage`.
  Для HTTP 401/403/404/409/429 используются `AuthenticationError`,
  `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `LimitExceededError`.
- Успешный HTTP-ответ с `status="locked"` остаётся `RuntimeResponse`:
  проверьте `status` и `missing_prerequisites` перед дальнейшими действиями.
- `ActionValidationError` означает локальное несоответствие схеме,
  `ProtocolError` — некорректный ответ или неподдерживаемую ссылку в схеме.
- Автоматические повторы допускаются только для GET: при сетевых ошибках и
  HTTP 429/502/503/504. Параметры клиента: `timeout=120`, `connect_timeout=5`,
  `max_retries=2`, `retry_backoff=0.25`; `max_retries=0` отключает повторы.
  `connect_timeout` ограничивает установку соединения, а `timeout` — ожидание
  ответа, отправку данных и ожидание свободного соединения. Соединение также
  ограничивается `timeout`, если он короче. Это таймауты отдельных сетевых фаз,
  а не общий срок выполнения с повторами. `TransportError` указывает запрос,
  число попыток и фазу сетевого сбоя.
- Действия, проверка и сброс **никогда не повторяются автоматически**.
  При сетевом сбое `TransportError.may_have_executed` показывает, что изменение
  могло уже выполниться. Сначала изучите `task.state()` и только затем решайте,
  нужен ли повтор. Таймаут или отмена async-корутины не доказывают, что сервер
  остановил исполнение.
- Для удалённого сервера требуется HTTPS. HTTP доступен для локальной разработки;
  перенаправления HTTP не выполняются, чтобы не передавать токен другому адресу.

## Разработка

```sh
uv sync --python 3.12
uv run pytest
uv run ruff check .
uv run mypy src
uv build
```

Пакет не импортирует backend платформы. Sync/async тестируются через HTTPX
MockTransport против одного контракта `/api/agent-env`.
Публикация описана в [PUBLISHING.md](https://github.com/ai-security-lab-itmo/hundredflags-sdk/blob/main/PUBLISHING.md).

## Runtime contract

Version 0.6 keeps the shared `/api/agent-env` runtime and requires its public-state documentation response. Task documentation contains `state` and action descriptors, without narrative `description` or `instructions`. Runtime responses distinguish current `attempt_completed` from durable `completed`. HTTP failures use `{ "error": { "code", "message", "details" }, "usage", "retry_after" }`. Task prerequisite and completion metadata refer to explicit task IDs; shared environment state does not imply shared task credit. Upgrade the platform, course clients, and SDK together.
