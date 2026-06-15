import uuid
from datetime import datetime, timezone

from pydantic import EmailStr
from sqlalchemy import DateTime, Text
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# ---------------------------------------------------------------------------
# Blog Post
# ---------------------------------------------------------------------------

class BlogPostBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, unique=True, index=True)
    content: str = Field(min_length=1, sa_type=Text())
    excerpt: str | None = Field(default=None, max_length=500)
    published: bool = Field(default=False)


class BlogPostCreate(BlogPostBase):
    pass


class BlogPostUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    excerpt: str | None = Field(default=None, max_length=500)
    published: bool | None = None


class BlogPost(BlogPostBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    author_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    author: User | None = Relationship()


class BlogPostPublic(BlogPostBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author_id: uuid.UUID
    author_name: str | None = None


class BlogPostsPublic(SQLModel):
    data: list[BlogPostPublic]
    count: int


class BlogPostListPublic(SQLModel):
    title: str
    slug: str
    excerpt: str | None = None
    published: bool
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author_id: uuid.UUID
    author_name: str | None = None


class BlogPostList(SQLModel):
    data: list[BlogPostListPublic]
    count: int


# ---------------------------------------------------------------------------
# Scheduled / saved reports (emailed to the commissioner)
# ---------------------------------------------------------------------------

class ScheduledReportBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    league_id: str = Field(default="", max_length=64)
    # Comma-separated Sleeper stat keys to include in the report.
    stat_keys: str = Field(sa_type=Text())
    recipient_email: EmailStr = Field(max_length=255)
    # "manual" or "weekly".
    frequency: str = Field(default="weekly", max_length=32)
    enabled: bool = Field(default=True)


class ScheduledReportCreate(ScheduledReportBase):
    pass


class ScheduledReportUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    league_id: str | None = Field(default=None, max_length=64)
    stat_keys: str | None = Field(default=None)
    recipient_email: EmailStr | None = Field(default=None, max_length=255)
    frequency: str | None = Field(default=None, max_length=32)
    enabled: bool | None = None


class ScheduledReport(ScheduledReportBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    last_sent_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )


class ScheduledReportPublic(ScheduledReportBase):
    id: uuid.UUID
    last_sent_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner_id: uuid.UUID


class ScheduledReportsPublic(SQLModel):
    data: list[ScheduledReportPublic]
    count: int


# ---------------------------------------------------------------------------
# Product usage analytics
# ---------------------------------------------------------------------------

class UsageEventCreate(SQLModel):
    # e.g. "page_view", "card_open", "export".
    event_type: str = Field(min_length=1, max_length=64)
    # The thing engaged with: a stat key, route path, or feature key.
    target: str = Field(min_length=1, max_length=255)
    path: str | None = Field(default=None, max_length=255)


class UsageEvent(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_type: str = Field(max_length=64, index=True)
    target: str = Field(max_length=255, index=True)
    path: str | None = Field(default=None, max_length=255)
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="SET NULL"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class UsageSummaryRow(SQLModel):
    event_type: str
    target: str
    count: int


class UsageSummary(SQLModel):
    total_events: int
    rows: list[UsageSummaryRow]


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
