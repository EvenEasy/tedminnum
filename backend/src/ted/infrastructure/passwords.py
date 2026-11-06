from argon2 import PasswordHasher
from argon2.exceptions import VerificationError


class ArgonPasswords:
    def __init__(self) -> None:
        self.hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
        self.dummy_hash = self.hasher.hash("not-an-account-password")

    def hash(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return self.hasher.verify(hashed, password)
        except VerificationError:
            return False
