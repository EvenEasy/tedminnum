---
name: python-backend-architecture
description: Проєктуй, розширюй або адресно рефакторуй async Python backend за прагматичним layered підходом із application ports, constructor DI та явними transactions і resource lifetimes. Застосовуй для Python backend, Telegram/HTTP інтеграцій і modular growth, коли користувач обирає цю methodology; узгоджуй її з наявною архітектурою.
---

# Python Backend Architecture

Створюй реалізацію за вимогами користувача, зберігаючи невеликі operation classes, inward dependencies і явні ownership boundaries. Не вимагай повного stack чи folder tree для малого проєкту. Цей skill не надає дозволу на unrelated refactoring, live integration calls або deployment.

## Знання та навігація

- Прочитай [references/ARCHITECTURE_BLUEPRINT.md](references/ARCHITECTURE_BLUEPRINT.md): для вибору масштабу — розділи 1–5; domain/application/persistence/DI — 6–11; Telegram/HTTP/adapters/async/jobs — 12–19; verification/technology/modules — 20–28. Відкривай relevant частини докладно перед відповідною реалізацією.
- Використовуй [references/IMPLEMENTATION_EXAMPLES.md](references/IMPLEMENTATION_EXAMPLES.md), якщо потрібні concrete code templates для наскрізного flow, provider wiring або transport integration. Приклади generalized; адаптуй назви та business invariants, не додавай їх features у чужий продукт автоматично.
- `Observed` означає підтверджений стиль вихідного backend; `Recommended` — corrective improvement; `Inferred`, `Optional`, `Unknown` не подавай як established conventions. REQUIRED/PREFERRED/CONDITIONAL/OPTIONAL у blueprint мають context, а не універсальну силу.

## Workflow A — новий проєкт

1. Визнач business intents, actors/invariants, interfaces, persistence, delivery needs і deployment model. Уточнюй лише відсутні рішення, що materially змінюють реалізацію; незалежну роботу продовжуй.
2. Вибери мінімальний complexity profile: малий bot/script, один domain із persistence, bot + HTTP або кілька modules. Frameworks conditional: aiogram для Telegram, aiohttp для потрібного HTTP, SQLAlchemy/Alembic за DB, Dishka за достатнього dependency/lifecycle graph. Manual composition допустима.
3. Зафіксуй коротку implementation map: responsibilities/dependencies, application operations/ports, transaction owner, APP/operation lifetimes, time/error/idempotency і shutdown contracts. Не генеруй empty optional layers.
4. Реалізуй один complete vertical flow: transport input → application intent → domain/policy → adapter → explicit commit/result → response. Provider bindings лишаються в composition root. Простий public read може йти прямо в query/catalog port.
5. Додай наступні features за тією самою формою, перевіряючи, чи нова abstraction створює конкретну користь. Multi-domain modules вводь за ownership потреби; service extraction — окреме рішення.
6. Виконай relevant safe checks і повідом результат/limits. Для critical writes/async lifecycle перевір meaningful failure paths, не тільки happy path.

## Workflow B — existing проєкт

1. Прочитай local instructions, manifests, entrypoints, actual imports і representative execution flows. З’ясуй наявні transaction/resource owners до змін.
2. Порівняй зі blueprint: що сумісне, де є conflict із requirements, що лишається optional. Не вважай інший framework/naming layout дефектом.
3. Обери найменший requested extension/refactor. Зберігай functional behavior і public contracts; schema/transaction changes пояснюй конкретними consequences. Для review-only запиту лише аналізуй.
4. Реалізуй локальну boundary там, де це допомагає intent запиту; не мігруй увесь repo на іншу структуру і не додавай dependencies без потреби. Existing DI/manual wiring підтримуй, якщо воно задовольняє lifetimes.
5. Перевір behavior affected flow і нові boundaries. Окремо зазнач untouched debt/limits без розширення scope.

## Essential implementation constraints

- Domain framework-free; application отримує domain/primitives/DTO і application-owned ports, а не Bot/Request/ORM/container. Concrete implementations знає composition root.
- Перевага named class-based use cases із constructor dependencies та `async execute`. Не вводь generic repositories, buses або rich DDD автоматично.
- Для нової реалізації repositories map ORM↔domain, можуть flush, не commit; один top-level application operation/workflow володіє transaction, DI cleanup не commit-ить. В existing проєкті з явним outer `session.begin()`/transaction middleware збережи цього owner: новий collaborator не додає self-commit. Зміна transaction model потребує requested scope й перевірки behavior.
- APP — engine/factory/Bot/client/catalog/registry; operation — session/repos/transaction/use case. Background execution відкриває новий scope; concurrent tasks не ділять AsyncSession.
- Обов’язкові business policies і external fulfillment однакові для всіх transports. Public catalog reads можуть бути простими; mutation/authorization не дублюються в handlers.
- Ідемпотентність спирається на application semantics і DB uniqueness; exists-check не lock. Після commit зовнішні effects мають explicit best-effort або durable reconciliation contract.
- Єдина UTC policy; explicit adapter normalization. Standard TLS, typed integration failures, bounded timeout/retry лише за safe semantics.
- Кожна task має owner, exception/ACK policy і shutdown path. Спершу зупиняються/дренуються consumers, потім shared resources. Persistent local scheduler optional і не є distributed exactly-once queue.
- Не копіюй client-specific identifiers/content/policies із джерела methodology. Не представляй Recommended improvements як already observed behavior.

## Перевірка перед завершенням

Перевір actual imports, complete request flow, signatures/nullability, commit/rollback, scope ownership і cleanup. Для selected capability перевір missing/invalid/duplicate/cancellation path, якщо це materially впливає на correctness. Оцінюй commands перед запуском: scripts із live APIs, credentials або mutable DB не є safe tests лише через назву.

У відповіді поясни обраний масштаб, зміни та їх purpose, relevant verification і material limitations. Не заявляй operational guarantees або успішні тести, яких не виконував.
