"""Identity and authorization enumerations."""

from enum import Enum


class MembershipRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ACCOUNTANT = "ACCOUNTANT"
    MANAGER = "MANAGER"
    USER = "USER"
    AUDITOR = "AUDITOR"
