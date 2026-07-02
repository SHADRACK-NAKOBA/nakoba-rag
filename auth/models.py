"""auth/models.py — Auth data models"""
from dataclasses import dataclass, field
from pydantic import BaseModel


@dataclass
class UserContext:
    user_id: str
    email: str
    display_name: str = ""
    roles: list[str] = field(default_factory=list)
    token: str = ""

    def has_role(self, role: str) -> bool:
        return role in self.roles or "it_admin" in self.roles

    def is_read_only(self) -> bool:
        exec_roles = {"l3_support", "it_admin", "security_admin"}
        return not bool(exec_roles & set(self.roles))


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800


class LoginRequest(BaseModel):
    username: str
    password: str