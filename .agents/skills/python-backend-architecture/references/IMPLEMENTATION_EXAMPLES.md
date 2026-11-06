# Узагальнені implementation examples

Це **generalized templates**, а не копії вихідного проєкту. Приклад реєстрації нотатки показує спостережений стиль: dataclasses → application ports → constructor-injected use case → окремий SQLAlchemy adapter → request-scoped DI → presentation handler. Назви, інваріанти та предметна область прикладу вигадані й не містять клієнтського контексту.

**Observed style:** `src` layout; `domain/application/infra/presentation/di`; `Protocol`; `create` та `execute`; `_to_domain`; repositories виконують flush, application комітить; APP engine/factory, REQUEST session/repositories/use cases; незалежні view functions; aiogram injection; explicit REQUEST scope для HTTP.

**Recommended corrections у шаблоні:** валідований immutable value object; узгоджені анотації; один UTC-aware часовий контракт; явний rollback; прогнозований validation error; public aiohttp lifecycle API. Ці виправлення не слід описувати як уже послідовно реалізовані практики вихідного проєкту.

## 1. Мінімальна структура й запуск прикладу

Нижче кожен підпис `### path.py` визначає окремий модуль. Корінь import path — `src`. Для звичайних packages додайте порожні `__init__.py`; namespace packages також працюють у цьому прикладі. Python-код не запускає сервер під час import.

```text
src/example_backend/
├── domain/notes.py
├── application/notes.py
├── infra/persistence.py
├── di/providers.py
├── presentation/views.py
├── presentation/http.py
└── presentation/telegram.py          # лише якщо потрібен Telegram
```

Приклади використовують Python 3.11+ (`datetime.UTC`); це межа сумісності наведеного коду, не універсальний version pin для methodology. Потрібні SQLAlchemy asyncio, відповідний async DB driver і Dishka; HTTP adapter потребує aiohttp, Telegram adapter — aiogram 3. Версії підбирайте сумісні з новим проєктом. Для SQLite-прикладу потрібен aiosqlite. aiohttp слід явно додати як direct dependency, якщо код безпосередньо його використовує.

У production schema створює migration. Якщо для isolated verification використовується `Base.metadata.create_all`, це допускається лише в тимчасовій БД; у наведених modules немає implicit schema creation.

## 2. Domain: сутність і справжній value object

### `src/example_backend/domain/notes.py`

```python
from dataclasses import dataclass
from datetime import UTC, datetime


class InvalidTitle(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Title:
    value: str

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not 1 <= len(value) <= 100:
            raise InvalidTitle("Заголовок має містити від 1 до 100 символів")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class Note:
    id: int | None
    title: Title
    created_at: datetime

    def __post_init__(self) -> None:
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at має містити timezone")

    @classmethod
    def create(cls, title: Title) -> "Note":
        return cls(id=None, title=title, created_at=datetime.now(UTC))
```

`Title` виправданий, оскільки централізує нетривіальний invariant. За відсутності такого правила достатньо поля `str`; не створюйте value objects лише заради структури. Немає imports із SQLAlchemy, Pydantic, Dishka чи presentation.

## 3. Application: ports та один owner транзакції

### `src/example_backend/application/notes.py`

```python
from typing import Protocol

from example_backend.domain.notes import Note, Title


class NoteRepository(Protocol):
    async def create(self, note: Note) -> Note: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class RegisterNote:
    def __init__(self, repository: NoteRepository, transaction: Transaction):
        self._repository = repository
        self._transaction = transaction

    async def execute(self, title: str) -> Note:
        note = Note.create(Title(title))
        try:
            saved = await self._repository.create(note)
            await self._transaction.commit()
        except BaseException:
            await self._transaction.rollback()
            raise
        return saved
```

Domain validation відбувається до першого write. `BaseException` тут має вузьку мету: rollback і повторне підняття, включно з `CancelledError`; помилки не перетворюються на успішний result. Закриття request session залишається додатковим cleanup. Це не правило catch-ити `BaseException` у business logic. Повторна cancellation під час rollback може перервати cleanup; гарантії shutdown визначає bootstrap.

`RegisterNote` — top-level write operation і transaction owner. Якщо потрібен більший atomic сценарій із кількома операціями, винесіть спільні write-кроки в non-committing collaborators і зробіть один outer use case. Послідовні виклики кількох self-committing use cases не створюють спільної atomic transaction.

## 4. Infrastructure: mapping, flush і часовий контракт

### `src/example_backend/infra/persistence.py`

```python
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from example_backend.application.notes import NoteRepository, Transaction
from example_backend.domain.notes import Note, Title


class Base(DeclarativeBase):
    pass


class NoteORM(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SQLNoteRepository(NoteRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_domain(model: NoteORM) -> Note:
        created_at = model.created_at
        # У цій schema SQLite зберігає UTC без offset; domain завжди aware.
        if created_at.utcoffset() is None:
            created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = created_at.astimezone(UTC)
        return Note(model.id, Title(model.title), created_at)

    async def create(self, note: Note) -> Note:
        model = NoteORM(
            title=note.title.value,
            created_at=note.created_at.astimezone(UTC),
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_domain(model)


class SQLAlchemyTransaction(Transaction):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
```

`DeclarativeBase` — modern generalized variant; вихідний стиль використовував також `declarative_base()`. Це взаємозамінний технічний вибір, не новий architectural layer.

UTC conversion тут допустиме, бо **schema contract прямо визначає naive timestamps як UTC**. Не застосовуйте `replace(tzinfo=UTC)` до невідомих legacy local times. `DateTime(timezone=True)` сам по собі не гарантує однакове повернення timezone на всіх DB backends.

Repository повертає domain object, а не tracked ORM instance. `flush` отримує ID і перевіряє write у поточній transaction; commit залишається у use case. Не додавайте generic `BaseRepository`, якщо немає повторної нетривіальної поведінки.

## 5. Dishka: lifetimes і composition root

### `src/example_backend/di/providers.py`

```python
from collections.abc import AsyncIterator
from dataclasses import dataclass

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from example_backend.application.notes import NoteRepository, RegisterNote, Transaction
from example_backend.infra.persistence import SQLAlchemyTransaction, SQLNoteRepository


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: str


class DatabaseProvider(Provider):
    def __init__(self, settings: DatabaseSettings):
        super().__init__()
        self._settings = settings

    @provide(scope=Scope.APP)
    async def engine(self) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(self._settings.url, pool_pre_ping=True)
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide(scope=Scope.APP)
    def factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self, factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session


class OperationsProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(SQLNoteRepository, provides=NoteRepository)
    transaction = provide(SQLAlchemyTransaction, provides=Transaction)
    register_note = provide(RegisterNote)


def create_container(settings: DatabaseSettings) -> AsyncContainer:
    return make_async_container(DatabaseProvider(settings), OperationsProvider())
```

Session, repository, transaction manager та use case кешуються в одному REQUEST scope. Другий operation scope отримує іншу session. APP dependency не повинна захоплювати REQUEST object. Синхронна settings dataclass у прикладі зберігає мінімум коду; для deployment з nested environment settings умовно застосуйте Pydantic Settings, як описано в blueprint.

Під час паралельних tasks відкривайте окремі operation scopes: один `AsyncSession` не слід ділити між concurrent database operations. Не переносіть pool constants між різними DB drivers без перевірки їхньої підтримки.

## 6. Presentation: HTTP із explicit REQUEST scope

### `src/example_backend/presentation/views.py`

```python
from example_backend.domain.notes import Note


def note_saved_view(note: Note) -> str:
    return f"Збережено нотатку #{note.id}"
```

### `src/example_backend/presentation/http.py`

```python
from aiohttp import web
from dishka import AsyncContainer, Scope

from example_backend.application.notes import RegisterNote
from example_backend.domain.notes import InvalidTitle


class RegisterNoteHandler:
    def __init__(self, container: AsyncContainer):
        self._container = container

    async def __call__(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            return web.json_response({"error": "invalid_json"}, status=400)

        if not isinstance(body, dict) or not isinstance(body.get("title"), str):
            return web.json_response({"error": "title_required"}, status=400)

        try:
            async with self._container(scope=Scope.REQUEST) as scope:
                operation = await scope.get(RegisterNote)
                note = await operation.execute(body["title"])
        except InvalidTitle as error:
            return web.json_response({"error": str(error)}, status=422)

        return web.json_response({"id": note.id, "title": note.title.value}, status=201)


def build_app(container: AsyncContainer) -> web.Application:
    app = web.Application(client_max_size=16 * 1024)
    app.router.add_post("/notes", RegisterNoteHandler(container))
    return app
```

Handler парсить transport input, викликає use case та відображає очікуваний validation error. Infrastructure failure не маскується під 201. JSON shape validation тут невелика; складні контракти виправдовують окремі Pydantic request/response models на presentation boundary.

У цьому навчальному endpoint **немає user identity, authorization або idempotency contract**. Для реального private API додайте authentication middleware й передавайте actor context у application operation; для retry-sensitive creation визначте request key та database uniqueness. Не приписуйте ці властивості самому DI або `Protocol`.

Один варіант standalone lifecycle, який запускає лише HTTP server, наведено окремо. Він використовує public `AppRunner` / `TCPSite`; production binding, signals та stop policy належать deployment requirements. Функція сама не викликається під час import.

```python
import asyncio
from aiohttp import web

from example_backend.di.providers import DatabaseSettings, create_container
from example_backend.presentation.http import build_app


async def serve_http(database_url: str, stop: asyncio.Event) -> None:
    container = create_container(DatabaseSettings(database_url))
    runner = web.AppRunner(build_app(container))
    try:
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 8080).start()
        await stop.wait()
    finally:
        try:
            await runner.cleanup()
        finally:
            await container.close()
```

Root container живе довше HTTP requests. Якщо він спільний із bot та workers, його закриває спільний process owner після зупинки всіх interfaces, а не окремий HTTP cleanup callback. У разі помилки під час startup також виконується cleanup уже створених ресурсів.

## 7. Умовний Telegram adapter із тим самим use case

### `src/example_backend/presentation/telegram.py`

```python
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka, inject

from example_backend.application.notes import RegisterNote
from example_backend.domain.notes import InvalidTitle
from example_backend.presentation.views import note_saved_view


router = Router()


@router.message(Command("note"), F.chat.type == "private")
@inject
async def register_note(
    message: Message,
    command: CommandObject,
    operation: FromDishka[RegisterNote],
) -> None:
    try:
        note = await operation.execute(command.args or "")
    except InvalidTitle as error:
        await message.answer(str(error))
        return
    await message.answer(note_saved_view(note))
```

У composition root для Telegram підключіть той самий root container до Dispatcher. `setup_dishka` створює aiogram operation scope; handlers не отримують root container і не роблять service lookup самостійно.

```python
from aiogram import Dispatcher
from dishka.integrations.aiogram import setup_dishka

from example_backend.presentation.telegram import router


def build_dispatcher(container):
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    setup_dishka(container=container, router=dispatcher)
    return dispatcher
```

Handler не використовує event-specific DI context objects, тому `AiogramProvider` у цьому мінімальному graph не потрібний. Додайте його, якщо providers реально потребують `TelegramObject` або інші integration-provided dependencies. Bot створюйте як APP resource з `finally: await bot.session.close()` або явно керуйте ним у bootstrap; оберіть одного lifecycle owner.

У комбінованому bot+HTTP процесі обидва interfaces викликають `RegisterNote`, але отримують незалежні REQUEST sessions. Shared application code не потребує imports із aiogram чи aiohttp. FSM, CallbackData та pure keyboard/view builders додавайте лише для відповідних interaction flows.

## 8. Умовний after-commit wakeup

Коли operation додає persisted job, спостережений корисний принцип — `flush job → register wakeup → commit → wake scheduler`. Wakeup не можна виконувати до commit: worker може не побачити job. Нижче — окремий generalized варіант transaction adapter для такого випадку.

```python
import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession
from example_backend.infra.persistence import SQLAlchemyTransaction


class AfterCommitTransaction(SQLAlchemyTransaction):
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self._callbacks: list[Callable[[], None]] = []

    def add_after_commit(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    async def commit(self) -> None:
        await super().commit()
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            try:
                callback()
            except Exception:
                logging.getLogger(__name__).exception("After-commit wakeup failed")

    async def rollback(self) -> None:
        self._callbacks.clear()
        await super().rollback()
```

Для використання розширте application `Transaction` port методом `add_after_commit` і замініть binding на `AfterCommitTransaction`; не змушуйте application залежати від concrete class. Цей conditional interface extension потрібен лише operation, що планує jobs. Поведінка logging callback failure — **Recommended correction**: після успішного DB commit не можна повідомляти caller, ніби DB transaction rolled back. Основна DB commit error продовжує поширюватись.

Callback тут синхронний, короткий і лише подає local `asyncio.Event.set()`-подібний сигнал. Це не durable delivery й не місце для payment, message send або довгого async I/O. Втрата сигналу має компенсуватися worker polling persisted jobs. Якщо потрібен гарантований зовнішній side effect, оцініть durable outbox/reconciliation як окреме рішення; воно не виникає автоматично з цих callbacks.

## 9. Що перевірити на цьому vertical slice

1. Domain відхиляє порожній/завеликий title незалежно від transport.
2. Repository повертає domain `Note` із generated ID та aware timestamp.
3. Одна operation використовує спільну session для repository і transaction; різні REQUEST scopes — різні sessions.
4. Commit відбувається один раз на top-level write; repository не комітить.
5. При repository/commit error operation поширює exception і робить rollback; domain validation не створює DB write.
6. HTTP і Telegram викликають той самий use case; business rules не копіюються в handlers.
7. Shutdown спершу припиняє/очікує interfaces і tasks, потім закриває root container.

Це verification criteria, а не твердження про наявність tests у вихідному проєкті. Для нового проєкту достатньо meaningful tests для invariants, transaction failure, DI lifetimes і transport mappings. Повну integration suite, migrations та network bootstrap слід перевіряти у відповідному ізольованому environment.
