export function testDatabase(): string {
  const value = process.env.E2E_DATABASE_URL;
  if (!value || process.env.ALLOW_DESTRUCTIVE_TESTS !== "1")
    throw new Error(
      "Browser tests require E2E_DATABASE_URL and ALLOW_DESTRUCTIVE_TESTS=1 for a confirmed disposable database",
    );
  const parsed = new URL(value);
  if (
    parsed.protocol !== "postgresql+asyncpg:" ||
    parsed.pathname !== "/ted_e2e_test" ||
    parsed.search ||
    parsed.hash
  )
    throw new Error(
      "Browser tests require a separate disposable database named ted_e2e_test",
    );
  return value;
}
