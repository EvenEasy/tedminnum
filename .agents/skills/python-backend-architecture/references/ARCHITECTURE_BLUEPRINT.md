# Blueprint: прагматична async Python backend architecture

Це самодостатня methodology, отримана з дослідження реального layered async backend. Вона зберігає його характерні сильні рішення: невеликі class-based application operations, constructor injection, application-owned Protocol ports, plain domain dataclasses, окремі ORM models із ручним mapping, subsystem DI providers, явні APP/REQUEST lifetimes і caller-owned transactions. Вона не вимагає доступу до вихідного проєкту.

## Зміст і навігація

1–4: принципи, ступені обов’язковості, розмір системи, reference structure. 5–10: boundaries, domain, application, contracts, persistence, transactions. 11–17: DI, Telegram, HTTP, adapters, catalogs, async і scheduler. 18–23: errors, settings, naming/docs, testing, technology selection, modularization. 24–28: flows, decision records, anti-patterns, new/existing workflows і scenario validation. Конкретні generalized code templates — у [IMPLEMENTATION_EXAMPLES.md](IMPLEMENTATION_EXAMPLES.md).

## 1. Походження правил та сила вимоги

Окремо позначаємо дві незалежні осі:

| Походження | Значення |
|---|---|
| **Observed** | практика справді присутня у дослідженому backend |
| **Inferred** | ймовірна engineering мотивація, а не задокументований намір автора |
| **Recommended** | corrective improvement або future adaptation, відсутня чи непослідовна в оригіналі |
| **Optional** | альтернативний механізм, який обирають лише за потреби |
| **Unknown** | немає достатньої evidence про практику/вимогу |

| Нормативність | Значення |
|---|---|
| **REQUIRED** | умова збереження обраного підходу або correctness у названому контексті |
| **PREFERRED** | характерна корисна convention, можливі обґрунтовані альтернативи |
| **CONDITIONAL** | застосувати, якщо виконується явно вказана умова |
| **OPTIONAL** | інструмент чи pattern із конкретним trade-off, не prerequisite |

Наприклад, «Recommended / REQUIRED, якщо є concurrent duplicate requests» не означає, що оригінальний проєкт уже правильно розв’язував idempotency. REQUIRED тут — обмеження нової реалізації в цьому контексті. Framework/package choice майже завжди CONDITIONAL, а не REQUIRED.

## 2. Архітектурна філософія

**Observed / PREFERRED:** організовувати код за відповідальністю, а не навколо ORM або framework. Application operation має розповідати про намір користувача; repository — про persistence capability; handler — про конкретний transport interaction. Невеликі explicit класи кращі за універсальний framework усередині проєкту.

**Observed / REQUIRED для layered варіанта:** domain не знає transport, ORM, DI, environment або container. Application визначає потрібні capabilities і координує операцію; concrete adapters підставляються зовні. Відокремлювати імпорт framework від business policy, а не просто розкладати змішаний код по папках.

**Inferred / PREFERRED:** explicit lifetimes і прості extension seams важливіші за формальну максимальну кількість layers. Одне DTO/Protocol/service на кожну функцію не є метою. Не будувати rich DDD, CQRS, bus, UoW framework чи microservices без відповідного complexity driver.

**Recommended / REQUIRED:** відтворювати сильні conventions із виправленими contracts. Не повторювати змішаний datetime, disabled TLS, business decisions у двох transports, broad financial failure suppression або acknowledged background processing без визначеного delivery contract.

## 3. Вибір мінімального масштабу

| Профіль | Достатня структура | Що додавати лише за потреби |
|---|---|---|
| Малий async script / bot без meaningful domain | entrypoint, handlers, settings, кілька injected helpers | database, DI framework, repository interfaces, persistent scheduler |
| Один domain + persistence | `domain`, `application`, `infra`, `presentation`, composition | services понад use cases, generic DTO hierarchy, event bus |
| Telegram + HTTP | ті самі application operations, окремі transport packages, спільний composition root | aiohttp DI middleware, якщо ручні scopes вже зрозумілі; outbox за delivery requirements |
| Кілька business domains | modules з local layers, public contracts і data ownership | окремі deployments, network bus, distributed transactions |
| Окремі services | service-owned data, versioned contracts, consistency/observability/deployment design | це самостійне architectural рішення, не автоматичний export modules |

Для малого bot допустимі manual constructor wiring і пряме читання read-only catalog у handler. Для paid mutation, authorization, multi-repository write або спільного HTTP/Telegram workflow application boundary має бути явною незалежно від кількості файлів.

## 4. Reference project structure

**Observed / PREFERRED**, коли layers уже виправдані:

```text
pyproject.toml
src/
  backend/
    __main__.py
    config/
      settings.py
    di/
      container.py
      use_cases.py
      services.py             # якщо є reusable application services
      scheduler.py            # якщо потрібні background jobs
    domain/
      entities/
      value_objects/          # тільки meaningful values/invariants
      enums/
      exceptions/
    application/
      ports/
        repositories/
        transaction.py
      use_cases/
      services/
      policies/
      exceptions/
    infra/
      persistence/sqlalchemy/
        models/
        repositories/
        provider.py
        transaction.py
      content/yaml/
      http/
      integrations/
      scheduler/
    presentation/
      telegram/
        routers/
          feature/
            view/
        keyboard/
        fsm/
        jobs/
        setup.py
        provider.py
      http/
        app.py
        router.py
    shared/                   # невеликий набір справді загальних helpers
migration/                    # якщо є schema-managed DB
tests/                        # Recommended, не підтверджена практика оригіналу
```

Не генерувати всі ці каталоги наперед. Мінімальний business slice — domain type/policy, application operation, потрібний port, adapter і transport handler; частину можна тримати в одному role-specific файлі до реального росту. Не створювати empty `services`, `events`, generic base classes чи pass methods як completed design.

Observed convention допускає subsystem `provider.py` поруч із adapters і загальний `di/container.py`, який їх збирає. Telegram-specific outbound adapters можуть жити в `presentation/telegram/access.py` або `jobs/`: вони належать framework boundary, хоча виконують outbound роль. У великому проєкті `infra/telegram` — рівноправна альтернатива; визначити локальну convention один раз.

## 5. Layer responsibilities і dependency rules

| Компонент | Відповідальність | Дозволені imports | Заборонені imports для обраного підходу |
|---|---|---|---|
| Domain | business concepts, meaningful invariants, state transitions | stdlib, власний domain | ORM, Telegram/HTTP types, DI, settings loader, file/network I/O |
| Application | use case orchestration, policy/authorization, ports, transaction boundary | domain, власні contracts, stdlib | concrete SQLAlchemy repos, Bot/Request/Response, container resolution |
| Infrastructure | persistence, external protocols, format/error translation | domain + application ports, конкретні libraries | inward application logic, захована business authorization |
| Presentation | routing, transport validation, identity extraction, FSM, response formatting | application API, domain/read models за потреби, framework | concrete persistence для business workflow, дубльована business mutation policy |
| Composition/config | concrete graph, resource ownership, startup/shutdown | усі layers у межах wiring | business workflow під виглядом provider factory |

**Observed / PREFERRED:** ports живуть в application, де є consumer; не переносити всі interfaces в domain автоматично. Business operations отримують typed dependencies у constructor, а не `AsyncContainer`.

**Recommended / REQUIRED, якщо є кілька transports:** одна business operation має однакові acceptance та fulfillment semantics через Telegram, HTTP і background invocation. Framework identity спочатку перевіряється transport, application отримує trusted subject/context. HTTP handler не імпортує чужий Telegram view для керування business success; notification оформлюється через application capability, якщо це частина workflow.

Прямий query до catalog port у handler дозволений, коли він лише читає/відображає public data. Якщо з’явилися authorization, calculation, filters із business semantics чи reusable policy — перенести їх до application query/service.

## 6. Domain modeling

**Observed / PREFERRED:** plain dataclasses для entities, `StrEnum` для обмежених множин, `Decimal` для грошей, classmethod `create` для meaningful construction/defaults. `slots=True` доречний для records, `frozen=True` — для values/snapshots. ORM inheritance не є способом створити domain entity.

**Recommended / REQUIRED за наявності invariant:** валідувати незалежно від framework input parsing. Pydantic parsing YAML не захищає прямий Python constructor. Factory або `__post_init__` має реально перевіряти non-empty/positive/allowed transition, якщо цього потребують вимоги. Не створювати «VO» лише заради папки; primitive може бути достатнім.

`frozen=True` не заморожує вкладені dict/list/mutable dataclass. Для справді immutable values обрати immutable nested representation або defensive copy/read-only mapping. Не вдавати immutable aggregate, якщо це mutable record.

Business state transition належить entity/domain policy, коли це локальне правило самого поняття. Multi-repository orchestration і виклики external capabilities належать application. Не викликати clock, database або Bot усередині неочевидного property.

**Recommended / PREFERRED:** aware UTC у domain. Якщо DB повертає naive UTC, normalize в adapter (`value.replace(tzinfo=UTC)` лише за підтвердженого storage contract), aware input переводити через `astimezone(UTC)`. Legacy naive domain можна тимчасово зберегти послідовно, але не змішувати. Calendar duration/month ≠ універсальні 30 днів: зафіксувати product policy.

Clock injection CONDITIONAL: потрібна для складної time policy/reproducible scheduling tests; для єдиного timestamp explicit параметр часто простіший. Domain events/aggregates OPTIONAL лише коли є реальні state/lifecycle requirements; вони не є частиною підтвердженого baseline.

## 7. Application use cases, services і DTO

**Observed / PREFERRED:** named operation class, constructor injection, `async def execute(...)`, поля `_repository`, `_transaction`, `_catalog`; короткий happy path і явні failure outcomes. Names описують business intent, не transport endpoint. Не змушувати caller передавати ORM object або aiogram Message.

Типовий порядок mutation:

1. Отримати/перевірити required data і trusted actor/context.
2. Застосувати missing/enabled/authorization/business policy.
3. Побудувати domain object/transition.
4. Зберегти related writes через repositories у спільній transaction.
5. Commit у визначеній application boundary; повернути domain result або stable application DTO.
6. Узгодити post-commit external effects відповідно до їх delivery contract.

Service виділяти для повторно використовуваної orchestration або query API. Якщо service лише дублює один repository method і не створює стабільного API, окрема abstraction OPTIONAL. Не робити use case для кожного простого public catalog read.

**Recommended / CONDITIONAL:** command/result dataclass, коли primitives набагато, input містить actor/context, є several outcomes або interface використовується багатьма transports. Для трьох зрозумілих параметрів DTO не обов’язковий. Frozen command не замінює input validation.

Free/admin/promotional grant може бути легальним окремим intent. Не перетворювати `receipt=None` на неявний спосіб обійти paid policy. Розділити intents або передати explicit authorized reason; точну policy визначають requirements.

## 8. Ports і типові contracts

**Observed / PREFERRED:** `typing.Protocol`, methods за consumer capability, async для I/O, domain objects у return, відсутність generic base repository. Concrete implementation може явно наслідувати Protocol, але nominal inheritance не потрібне для structural typing.

**Recommended / REQUIRED:** ports та adapters узгоджують signatures, nullability, exceptions і transaction ownership. `get -> Entity | None`, `create -> Entity` або explicit conflict result; caller обробляє None до dereference. Не оголошувати method лише в concrete class, якщо application уже його використовує.

Різні payment inputs — raw signed webhook bytes і user-supplied transaction ID — не повинні мати incompatible override одного base method. Обрати окремі capability protocols або normalizing boundary DTO. Спільна назва не доводить substitutability.

Repository містить operations, потрібні application, а не весь ORM API. Query filter не приймає SQLAlchemy expression у application port. Запити reporting можуть мати окремий read model/query adapter без aggregate hydration. DTO/events serialization у cross-module API — explicit, не ORM dump.

## 9. Persistence standards

**Observed / PREFERRED:** SQLAlchemy async, окремі `*ORM` models, concrete `*ORMRepository`, explicit `_to_domain`, handwritten inserts/selects/updates. Small duplication mapping прийнятне, поки mapper framework не дає доведеної користі.

**Observed / REQUIRED для transaction composition:** repository не commit. `flush()` доречний для generated ID/constraint check до завершення use case. Повернений ID не означає committed row. DB failure після flush робить transaction failed; перед продовженням потрібен rollback, а не logging + продовження.

**Recommended / REQUIRED:** schema constraints відповідають invariants: uniqueness для idempotency/business keys, FK відповідно до data ownership, nullability узгоджена з domain і migrations. Не додавати FK автоматично до зовнішнього service ID. Monetary storage обирати свідомо: Numeric/Decimal чи integer minor units із currency semantics; string amounts не універсальний стандарт.

Dialect-specific upsert/RETURNING дозволений, якщо backend обрано явно. Alternative backend потребує execution tests; generic ORM не гарантує portability. In-memory SQLite має інший pool support, ніж file-backed або PostgreSQL; не копіювати pool_size/max_overflow constants без перевірки dialect. Schema setup належить migrations/deployment; не підміняти migration history `create_all()` у production.

Indexes додавати за query shape/даними: status+run_at для jobs, subject+sort key для history — candidates, не universal checklist. Перевірити query plan/вимірювання за потреби. Немає підстав обіцяти throughput із pool size.

## 10. Transaction management, idempotency і post-commit effects

**Observed / PREFERRED:** lightweight `ITransactionManager` із `commit/rollback`, за потреби `add_after_commit(Callable[[], None])`. REQUEST provider yield-ить session і закриває її; він **не commit-ить** автоматично після handler. Operation/application workflow явно володіє transaction. Це transaction coordinator, не обов’язково повний Unit of Work.

Для вкладених use cases визначити **одного** commit owner. Клас із власним commit може бути top-level operation; reusable sub-operation має працювати у caller-owned transaction без незалежного commit. Не перетворювати кожен service method на окрему transaction, якщо потрібна атомарність кількох writes.

**Compatibility для existing проєкту:** якщо established owner — request dependency з `session.begin()` або explicit transaction middleware, зберегти його в межах extension без requested transaction refactor. Новий collaborator не викликає self-commit усередині цієї boundary. Preference application-owned commit стосується нового обраного підходу; не змінювати success/rollback semantics усього existing backend заради convention.

**Observed / PREFERRED:** after-commit hook придатний для швидкого локального `wake_up()`: register після запланованої зміни, виконати після успішного DB commit, очистити на rollback. Hook не має робити довгий network I/O.

**Recommended / REQUIRED:** відрізняти commit failure від callback failure після successful commit. Дані вже durable; rollback не скасує їх. Для disposable local notification hook failure можна залогувати та відновити polling; для critical delivery використати persisted intent. Process crash між commit і hook залишається можливим.

**Recommended / CONDITIONAL, коли можуть надходити duplicates:** idempotency належить application operation + DB uniqueness, не лише presentation `if_exists`. `SELECT exists` — optimization, не concurrency lock. Integrity conflict переводити в stable duplicate/already-applied outcome з коректним rollback або backend conflict strategy. Не повертати success для невідомого failure.

Database transaction не атомарна з Telegram/external API. Обрати contract:

- **OPTIONAL:** best-effort notification після commit, якщо втрачений alert не порушує business result.
- **CONDITIONAL:** durable effect status + reconciliation або transactional outbox, якщо надання доступу/відправка команди є обов’язковим результатом.
- **REQUIRED у critical delivery:** повтор receipt не повинен заважати відновленню незавершеного fulfillment; store acceptance і delivery як різні стани.

Зовнішні calls зазвичай виконувати поза відкритою DB transaction. Якщо після external validation потрібен write, заново перевірити concurrency-sensitive invariant під write boundary. Не гарантувати exactly-once delivery для API, що не підтримує його.

## 11. Dependency Injection та object lifecycle

**Observed / CONDITIONAL:** Dishka доречна для shared transports, кількох adapters, DB sessions і background jobs. Для маленького dependency graph manual wiring з context managers зберігає ту саму methodology.

| Scope | Що зберігати | Що не зберігати |
|---|---|---|
| APP | validated settings, engine, sessionmaker, reusable ClientSession/Bot, read-only catalogs, registry типів, scheduler strategy | mutable AsyncSession, event-specific user/FSM state, request repo |
| REQUEST / operation | session, repositories, transaction coordinator, use case/service, request-specific adapter | resource, що має пережити scope без власного lifetime |
| Окремий job scope | repos/tx на конкретне виконання job | session, успадкована від завершеного HTTP/update scope |

**Observed / PREFERRED:** subsystem Provider поруч із adapter; `provide(Concrete, provides=Port, scope=...)`; один `create_container(settings)` збирає graph. Async generator providers володіють resource initialization/finally cleanup. `async_sessionmaker(..., expire_on_commit=False, autoflush=False)` — observed preference, а не універсальна вимога: explicit flush і відсутність lazy access після scope мають бути послідовними.

**REQUIRED:** APP object не залежить від REQUEST object. Якщо runner APP має виконувати роботу, composition root передає callbacks, які відкривають REQUEST. Application executor може отримати caller-owned repo/tx і вузький resolver для handler registry; це локальний extension seam, не дозвіл на service locator у всіх use cases.

Контейнер закривається після stop/drain усіх workers/requests. Одна owner cleanup policy для shared Bot/client; перевірити framework registration, щоб він не закрив shared session раніше за інші users. Тестові provider replacement/fakes — Recommended, не доведена звичка вихідного автора.

## 12. Telegram presentation

**Observed / CONDITIONAL, якщо обрано aiogram:** feature `Router`, explicit router composition, explicit `@inject`/`FromDishka` за використання Dishka. Для inline callback flows — typed `CallbackData` + `StrEnum` actions; command-only bot їх не потребує. Application class methods не прикрашати framework injection decorators.

**Observed / PREFERRED:** pure view functions повертають `(text, markup)`; keyboard helpers концентрують markup/callback packing. Поєднання callback model і static builders допускається для малого bot. Для великої keyboard surface можна розділити schema/builders, не змінюючи application.

Handler: filter → перевірка форми input → trusted identity → application call → error/outcome mapping → callback ACK/message/edit. Не затримувати ACK callback query довгим network call, якщо UX потребує негайної відповіді. User-supplied ID у callback вважати untrusted/stale: missing/disabled/authorization policy перевіряє application.

FSM зберігає presentation interaction state, не authoritative paid/permission state. **Recommended / CONDITIONAL:** text filter, cancel/retry path, bounded temporary message metadata; storage/isolation обрати за deployment. MemoryStorage доречна, якщо restart loss допустимий; Redis/shared storage сама по собі не вирішує concurrent updates — потрібна event isolation/locking policy. Не вигадувати Redis dependency, якщо concurrency/storage вимог немає.

Webhook і polling — альтернативні delivery modes, не автоматично одночасні. Webhook secret/token verification підключати за framework contract; lifecycle Dispatcher/FSM також явно прив’язати до server. Визначити `handle_in_background`, ACK і task ownership; framework default не є перевіреною delivery guarantee. Polling cancellation має зупинити й дочекатися underlying polling task до shared resource cleanup.

Outbound Telegram implementation може бути поруч із presentation, але mandatory access/notification workflow координує application, не лише один transport handler.

## 13. HTTP interface поруч із bot

**Observed / CONDITIONAL:** aiohttp application builder, callable router/controller, explicit REQUEST child container всередині request. Це валідна проста інтеграція; окремий DI middleware OPTIONAL за великої кількості endpoints. Application use cases ті самі, що для Telegram.

**Recommended / REQUIRED:** parse/validate request shape на HTTP boundary, authentication/raw-body signature verification до trusted command creation, stable status/outcome mapping. Не логувати credentials або raw private payloads. Signed body не звільняє від schema validation та business checks.

URL/path configuration має узгоджувати route registration і outbound webhook registration. Request handler не повертає 200 до потрібної durability boundary без явного delivery design. Retryable infrastructure failure і invalid signature/input — різні outcomes.

Public `AppRunner`/`TCPSite` + application cleanup contexts — preferred corrective integration. Private `_run_app` не portable API. Один root process координує bot/server/worker startup і shutdown; HTTP route не закриває APP container після запиту.

## 14. External integrations

**Observed / PREFERRED:** adapter реалізує application port, приймає settings/transport dependencies, перекладає external data в domain/application result. Vendor-specific signature/address/event parsing лишається тут, а не в entity/use case.

**Recommended / REQUIRED:** standard TLS verification, explicit resource ownership, timeout budget і typed transport/protocol failure. Reusable APP ClientSession краща для частих requests; per-call session допустима за низької частоти та явного trade-off. Не повертати live ClientResponse після close context; materialize status/data/result усередині нього.

Retry CONDITIONAL: bounded attempts/backoff/jitter для transient failures і безпечних operations. Не retry invoice creation/transfer без idempotency contract. Cancellation не перехоплювати як ordinary success/invalid payment. Provider outage ≠ user invalid input.

Payment authenticity, ownership/order binding, amount/currency policy, finality, receipt uniqueness і external fulfillment — **окремі guarantees**. Перевірка receiver/token у public ledger не доводить, що claimant є payer. Не копіювати specific blockchain/provider policy в generic backend. Key loading/refresh та signature verification тестувати валідними синтетичними fixtures; відсутній key — configuration/provider error, а не indistinguishable invalid signature.

## 15. Configuration і content catalogs

**Observed / PREFERRED:** Pydantic Settings на зовнішньому boundary, nested settings models, environment separator `__`, явна startup validation, `.env` для local dev і ignored private artifacts. Конкретні settings мають належати capability, а не глобально вимагатися для вимкненої integration.

**Recommended / REQUIRED:** не логувати settings dump із secrets; sanitized examples мають бути runnable для обраної configuration. URLs/ports/paths перевірити на consistency, secrets representation обрати безпечно. Generated webhook secret підходить singleton, stable shared secret — replicas/rolling deployment. Migration tool має потребувати DB config, а не всіх Telegram/payment credentials.

**Observed / CONDITIONAL:** YAML catalogs підходять для невеликого controlled read-only content, не для runtime transactional data. `yaml.safe_load`, flatten hierarchical media keys, contextual load errors, domain conversion у adapter через `TypeAdapter` — підтверджений стиль. Validation I/O не переносити в domain. Завантажувати startup/lazy APP initialization, не на кожний request.

**Recommended:** schema validation, duplicate-ID checks, price/duration invariants за потреби, immutable nested structure. Async method port для in-memory read допустимий за consumer compatibility, але не обов’язковий. Не робити `async` façade над synchronous file load у request loop. Hot reload/versioning OPTIONAL; revision у catalog не є реалізованим distributed versioning.

## 16. Async execution і shutdown

**Observed / PREFERRED:** `asyncio.run` у entrypoint, `TaskGroup` для sibling long-running tasks, generator/provider `finally` для resources. Blocking file load допускається під час startup за невеликого каталогу; великий/повторний load — `to_thread` або async I/O за виміряної потреби.

**Recommended / REQUIRED:** кожна task має owner, observable exceptions і stop/drain contract. `TaskGroup` володіє лише створеними ним tasks, не всіма framework internals. Не переносити repository/session із request у detached task; нова task відкриває власний operation scope. Паралельні DB operations не ділять один AsyncSession.

Graceful shutdown sequence:

1. Прийняти OS/framework stop signal і припинити intake/new work.
2. Зупинити scheduler/polling; завершити або скасувати owned tasks із визначеним budget.
3. Дочекатися in-flight handlers/jobs або зафіксувати uncertain outcome відповідно до delivery policy.
4. Виконати Dispatcher/FSM/server cleanup.
5. Закрити APP resources/container після їхніх consumers.

Який resource закриває server hook, а який provider — визначити явно, щоб Bot не закрився під job. `CancelledError` зазвичай propagate після cleanup; не перетворювати cancellation на DONE. Startup failure теж має cleanup path. Readiness не повинна оголошуватися до required initialization; remote webhook registration узгодити з listener availability/deployment.

**CONDITIONAL:** bounded queue/semaphore/concurrency limits для високого intake; timeout budgets і cancellation tests. Не обіцяти runtime scale без вимірювання. Короткий sequential worker — легітимна backpressure policy для малого workload.

## 17. Database-backed scheduler як окрема optional capability

**Observed / CONDITIONAL:** якщо jobs мають переживати restart і broker не потрібен, розділити:

- domain Job record із kind/status/run_at/payload/group key;
- application `SchedulerService`, який пише jobs у caller transaction;
- application `JobExecutor` із registry `kind -> handler type`;
- infrastructure `SchedulerStrategy`, яка чекає/будить і викликає execution callback;
- framework-specific handler, наприклад Telegram sender;
- composition callbacks, які відкривають короткі scopes для query та execution.

**Observed / PREFERRED:** після committed schedule/cancel/reschedule — local wake; Event очищати до query, щоб не втратити change, який відбувся під час читання. Runner щоразу читає актуальний найближчий job. Conditional atomic `UPDATE ... WHERE status=PENDING ... RETURNING` для claim. Commit PROCESSING **до** external handler; після success mark DONE, після failure rollback/mark FAILED/commit.

**Recommended / REQUIRED:** один узгоджений time contract, registered payload validation, допустимі state transitions і completeness checks. Registry розширюється handler + binding + registration, не switch у всіх layers. Typed/versioned payload потрібний, коли dict contract уже став нестабільним.

Політика recovery має відповідати unknown side effects. Observed conservative strategy: PROCESSING після restart → FAILED, без blind replay. Це дозволено для **single scheduler owner**, але потребує ручної/автоматичної reconciliation, якщо delivery обов’язкова. Для multiple workers потрібні ownership/lease/heartbeat і non-global recovery. Local Event не будить інші processes; shared notifications або bounded polling CONDITIONAL.

Persistent scheduler не дорівнює broker/outbox/exactly-once engine. Retry attempts/backoff/dead-letter, parallel workers і distributed locks OPTIONAL за requirements. Не додавати весь scheduler у простий bot, який має лише ephemeral animation/timer.

## 18. Exceptions і result contracts

**Observed / PREFERRED:** окремі domain/application exceptions з machine code, user-safe message і contextual metadata. Domain errors framework-free. Infrastructure переводить vendor errors у application-meaningful capability failures; presentation maps errors to transport response.

**Recommended / REQUIRED:** not-found/disabled/conflict/permission/timeout/provider-unavailable не зливати в `None`, якщо caller має діяти по-різному. `None` коректний для звичайного `get` miss, але не приховує failed DB write. Unique conflicts translate лише за відомого constraint; unknown IntegrityError не прирівнювати до duplicate.

Broad best-effort helper допустимий для message deletion або необов’язкового alert, якщо failure залоговано. Не застосовувати до receipt persistence, access fulfillment або commit. Error logger не має сам падати, покладаючись на необов’язковий `awaitable.__qualname__`. Не додавати metadata до shared mutable class dict; instance-specific metadata створюється окремо.

After-commit error повідомляє, що state вже збережено; не обіцяти rollback. Публічний response не розкриває provider details, SQL, secrets або private inputs. Correlation/operation IDs Recommended для distributed/external flows.

## 19. Startup, settings і technology composition

**Observed / PREFERRED:** entrypoint невеликий: load/validate config → logging → container → required recovery/init → transport setup → run owned tasks → cleanup. Provider фабрики створюють graph/resources, а не виконують user business operation. Startup recovery — окрема explicit operation.

Відокремити enabling interfaces від configuration всіх possible integrations. Bot-only mode не вимагає HTTP bind/payment settings; no-DB mode не створює engine. Production migrations запускаються окремою deployment action, не implicit user request initialization. Ports/bind addresses/timeouts належать settings за real deployment потреби.

## 20. Naming, imports, comments і документація

**Observed / PREFERRED:** `src/<package>`, `snake_case.py`, PascalCase classes, `*ORM`, `*ORMRepository`, `*Provider`, named `*Service`, operation `.execute()`, private injected fields `_name`; module `__init__` exports для коротких imports. Ports можуть мати `I` prefix для capability interfaces, repository ports — без нього. Не перейменовувати existing project лише заради цієї суміші.

**Recommended:** explicit return types на ports/use cases/mappers/provider factories; сучасні `list/tuple/dict` annotations; без mutable default arguments. `Any`, dict payload і type ignores лишати лише з поясненим boundary. Module-level router composition не повинна приховано запускати network/DB.

Comments пояснюють transaction/time/recovery invariants і trade-offs, не переповідають `select/return`. Docstrings мають описувати owner, failure contract та non-obvious semantics. Видаляти stale claims про conversion/flush, яких код не робить. README/runbook має пояснювати setup, delivery mode, migration, shutdown і safe test commands; наявність comments не замінює ці contracts.

## 21. Testing та verification

Автоматизованої suite в дослідженому baseline не було. Усе нижче — **Recommended / CONDITIONAL відповідно до change risk**, а не вигадана established testing practice.

- Domain: meaningful invariants, monetary/time boundaries, state transitions без I/O.
- Application: fake ports; multi-write success/rollback, missing/disabled policy, authorization, duplicate/conflict result, post-commit uncertainty. Не тестувати лише те, що `.execute` повторює implementation calls.
- Persistence adapters: disposable DB цільового dialect; generated IDs, mapping round-trip, constraints, concurrent duplicate/claim semantics, migrations upgrade/schema match. SQLite test не доводить PostgreSQL behavior.
- Transport: framework input → trusted application input, error/status mapping; shared outcome між HTTP/Telegram.
- Lifecycle: startup failure/cancellation, slow in-flight handler, scheduler stop, APP resource close після consumers, no session reuse across tasks.
- Critical integration: synthetic valid/invalid signatures, provider failure, ownership/finality policy без live payments.
- Architecture: lightweight import/dependency checks, якщо кількість contributors/modules це виправдовує.

Перш ніж виконувати existing tests/scripts, визначити external side effects, credentials, DB mutation і network. Manual integration script не автоматично safe. Не запускати production main/webhook/migrations для «перевірки imports». Syntax/DI graph pass — корисний, але не доказ operational readiness. Для reversible documentation edits достатньо link/schema/example checks.

## 22. Адаптивна technology policy

| Технологія | Observed responsibility | Preference / умова | Альтернативи й обмеження |
|---|---|---|---|
| Python + asyncio | основний runtime | PREFERRED для async I/O backend | конкретну supported версію обирати за target ecosystem; не успадковувати version pin |
| aiogram 3 | Telegram routers/FSM/webhook/polling | CONDITIONAL для Telegram | інший transport не потребує aiogram; перевірити актуальні APIs installed version |
| aiohttp | HTTP server та outbound calls | PREFERRED коли bot + small HTTP у спільному loop | FastAPI/Starlette або інший async client допустимі; shared application contracts зберігаються |
| Dishka | scoped DI/resources/framework integration | PREFERRED за кількох interfaces/jobs/session graph | manual composition для малого system, інший DI за existing architecture |
| SQLAlchemy async | ORM/repos/session factory | CONDITIONAL за relational persistence | explicit SQL/read adapters можливі; async driver має відповідати DB |
| aiosqlite / SQLite | observed local DB driver | CONDITIONAL для малого single-node workload | PostgreSQL за concurrency/ops потреби, але не підтверджений production backend baseline |
| Alembic | async schema migrations | PREFERRED для SQLAlchemy schema evolution | інший migration tool за stack; DB-only config та disposable tests |
| Pydantic Settings | nested env validation | PREFERRED для typed application configuration | dataclass/manual config у малому проєкті; прямі imports мають direct dependency |
| Pydantic TypeAdapter | YAML→typed objects в adapter | CONDITIONAL для external structured content | explicit parser, schema library; не додає framework dependency до domain |
| PyYAML | read-only catalogs | CONDITIONAL для controlled file content | JSON/TOML/DB/CMS за editing/consistency requirements |
| ECDSA library | vendor webhook signature | CONDITIONAL лише відповідному integration | алгоритм/library визначає офіційний protocol; не generic backend dependency |
| Власний asyncio scheduler | persisted single-process jobs | OPTIONAL при простому workload | broker/task queue/system scheduler за durability/distribution requirements |

aiohttp і Pydantic в оригіналі імпортувалися напряму, але частково надходили transitively. **Recommended:** dependencies, які код імпортує напряму, задекларувати явно; lockfile забезпечує reproducibility, не замінює direct manifest contract. Не ставити packages тільки для optional папок.

## 23. Modularization і майбутнє service extraction

**Recommended / CONDITIONAL**, якщо з’явилися кілька coherent business domains:

```text
backend/
  modules/
    notes/
      domain/
      application/
      infra/
      presentation/
      api.py                 # public application contracts за потреби
    accounts/
      ...
  config/
  di/
  __main__.py
```

Це future adaptation, а не observed vertical structure. Module володіє entities, repositories і writes до своїх tables. Інший module використовує public application API/read contract, не private ORM/repo. Один deployment/shared engine допустимі; cross-module transaction coordination потребує визначеного owner, не випадкових shared commits.

Shared code обмежити технічними primitives/resources; бізнес-поняття із різною семантикою не об’єднувати лише через однакові назви полів. Boundary tests/owner documentation виправдані із ростом команди.

Окремий service — інше operational рішення: власні data, auth/network failure, versioned messages/APIs, idempotency, eventual consistency/compensation, tracing, deployment і migrations. Local function calls не можна механічно замінити HTTP і зберегти transaction semantics. Outbox/inbox/saga CONDITIONAL, не обов’язковий додаток до modular monolith.

## 24. Reference flows і extension recipes

**Read/display:** handler validates callback → public catalog/query port → domain/read data → pure view/keyboard → transport response. Application use case додається при business policy, а не за формальністю.

**Transactional create:** trusted transport identity + validated values → named application `execute` → domain factory → repository mapping/add/flush → transaction commit → stable result → presentation output. Session/tx/repo shared у одному operation scope. Concrete code — [IMPLEMENTATION_EXAMPLES.md](IMPLEMENTATION_EXAMPLES.md).

**External acceptance + fulfillment:** raw input authenticity → provider adapter result → application ownership/amount/status policy → receipt/operation uniqueness + DB commit → persisted effect delivery/reconciliation за requirement → response. Duplicate acceptance не означає завершений delivery.

**Job:** application schedules у caller transaction → commit → local wake → short query scope → due execution scope → atomic claim + commit → handler external call → finalize status + commit. APP registry містить types, не session. Unknown crash outcome не replay-ити навмання.

**Новий feature:** визначити intent/invariants → додати application operation і лише потрібні ports → adapter/migration, якщо є нові storage needs → provider bindings → transport mapping → focused verification. Не дублювати operation під кожний transport.

**Нова integration:** додати capability-specific port лише якщо application має consumer → adapter з lifecycle/errors/timeout → composition binding → contract tests. Новий vendor не повинен змінювати domain constructor, якщо business semantics ті самі.

## 25. Decision records для основних conventions

| Рішення | Purpose / owner / allowed boundary | Typical implementation / extension | Trade-off / applicability / mistakes |
|---|---|---|---|
| Plain domain | зберегти business concepts без frameworks; domain owner | dataclass + factory/invariant; нова policy/value за реальною потребою | simple records не rich DDD; не зберігати ORM/Request усередині |
| Application ports | consumer формулює capability; application→domain | Protocol + concrete adapter; заміна provider binding | більше mapping/typing, виправдано для I/O seams; не generic CRUD universe |
| Named use case | одна business operation; application owner | constructor ports + execute + explicit result/commit | легко тестувати; не розміщувати multi-transport policy у handler |
| Separate ORM mapping | відокремити persistence lifecycle; infra owner | `*ORMRepository._to_domain`, flush; новий dialect adapter | duplication прийнятна; не повертати lazy ORM поза scope |
| Scoped DI | lifetime/resource safety; composition owner | APP resources, REQUEST session/repo/tx, yield/finally | graph complexity; manual wiring для малого app; не APP session |
| Explicit transaction | атомарність selected writes; top-level operation owner | lightweight commit/rollback + optional hook | nested commit потребує дизайну; не auto-commit teardown чи swallowed failure |
| Feature routers + views | framework parsing/formatting окремо; presentation owner | typed callback, pure `(text, markup)`, shared application operation | простий read може йти в port; не дублювати authorization/fulfillment |
| Persistent job registry | extension без DB session у singleton; application + infra runner | kind→handler type, per-job scope, claim/commit | single-owner baseline; не називати distributed exactly-once queue |
| Catalog adapter | content editing без domain YAML dependency; infra owner | safe_load + TypeAdapter/validation + readonly map | startup/file consistency; не authoritative mutable business state |
| Modular growth | business ownership без premature services; module API | local layers/public contracts + root composition | нова Recommended адаптація; не cross-import чужих ORM |

Ці records разом із профільними розділами визначають responsibilities, allowed/prohibited dependencies, reasoning та applicability. Не перетворювати Suggested choice на REQUIRED без context.

## 26. Anti-patterns, які не слід копіювати

1. Називати папки Clean Architecture, зберігаючи concrete DB calls і paid policy в handlers.
2. Вимагати Dishka/ORM/repository/UoW/DTO/event bus для кожного маленького bot.
3. Дозволяти REQUEST session жити в APP singleton або кількох concurrent tasks.
4. Commit у repository/DI finalizer, коли use case очікує атомарність кількох writes.
5. `except Exception: log; commit` для critical persistence; unknown failure як success.
6. `exists` як єдиний concurrency/idempotency механізм; duplicate receipt як доказ delivered effect.
7. Mixed naive/aware time, factory без заявленого invariant, shallow frozen як гарантія deep immutability.
8. Disabled TLS, missing key initialization, raw hash як доказ payer ownership, retry unsafe writes навмання.
9. Detached tasks без owner/ACK/durability/shutdown policy; private server API як portable foundation.
10. Global fail-processing recovery при multiple active workers; in-process event як distributed wake.
11. Contracts, methods і examples, що не збігаються; placeholder pass як finished implementation.
12. Нав’язування microservices або rich DDD лише тому, що проєкт має domain folder.

## 27. Workflow створення і розвитку проєктів

### Новий backend

Спочатку визначити intents, actors, invariants, interfaces, storage, delivery/correctness needs і deployment model. Обрати мінімальний профіль із розділу 3. Зафіксувати коротко: layers, selected technologies, ports/transaction owner, APP/operation lifetimes, failure/duplicate/time policy і тільки необхідні extension points.

Реалізувати один наскрізний feature. Використати generalized examples як форму boundaries, не як обов’язковий feature set. Пройти success, invalid input, rollback, duplicate і cancellation там, де вони мають наслідки. Лише після цього масштабувати conventions на наступні modules.

### Existing backend

Прочитати local instructions і actual entrypoints/dependencies/flows. Зіставити наявні boundaries із blueprint; не перейменовувати всю структуру. Вибрати conventions, сумісні зі stack і scope запиту. Планувати найменшу зміну зі збереженням functional behavior; schema/transaction/lifetime changes оцінювати як окремі risks.

Для нового feature впровадити boundary локально; для refactoring зберегти public contracts або запропонувати migration/compatibility path. Якщо user просить лише audit — описати, не рефакторити. Existing FastAPI/manual DI/інший repository style не є сам по собі defect. Підтвердити результат relevant checks, а решту technical debt позначити без розширення завдання.

## 28. Scenario-based acceptance

| Сценарій | Рішення, які має дати skill | Межі складності |
|---|---|---|
| A: small async Telegram bot | feature router, pure view, мінімальні injected capabilities; typed callback лише для callback UI, named mutation operation за потреби | без DB/DI framework/scheduler, якщо немає вимоги; memory FSM лише за допустимого restart loss |
| B: bot + aiohttp + DB + DI | shared application operations, APP engine/Bot/client, REQUEST session/repo/tx; transport error mapping; public server lifecycle | жодних business decisions у HTTP-specific Telegram calls; explicit delivery і shutdown policy |
| C: modular monolith + integrations | local layered modules/public APIs, owned data, per-capability adapters, single composition root; observed conventions з Recommended module boundaries | без automatic microservices; shared DB не означає shared private ORM |
| D: existing async backend | inventory/compatibility map, narrow requested extension/refactor, existing framework/naming preservation, focused regression | blueprint як decision aid; no full rewrite, dependency churn чи unrelated feature work |

Якщо рішення для сценарію не пояснює конкретний commit owner, dependency direction і resource lifetime, воно ще не actionable. Якщо для сценарію A породжується повна структура зі всіма optional technologies, complexity selection не пройшла перевірку.
