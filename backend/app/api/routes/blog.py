import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    BlogPost,
    BlogPostCreate,
    BlogPostList,
    BlogPostListPublic,
    BlogPostPublic,
    BlogPostsPublic,
    BlogPostUpdate,
    Message,
    User,
)

router = APIRouter(prefix="/blog", tags=["blog"])


def _to_public(post: BlogPost, author: User | None = None) -> BlogPostPublic:
    resolved_author = author or post.author
    author_name = (
        resolved_author.full_name or resolved_author.email
        if resolved_author
        else None
    )
    return BlogPostPublic(
        **post.model_dump(exclude={"author"}),
        author_name=author_name,
    )


def _to_list_public(post: BlogPost, author: User | None = None) -> BlogPostListPublic:
    resolved_author = author or post.author
    author_name = (
        resolved_author.full_name or resolved_author.email
        if resolved_author
        else None
    )
    return BlogPostListPublic(
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        published=post.published,
        id=post.id,
        created_at=post.created_at,
        updated_at=post.updated_at,
        author_id=post.author_id,
        author_name=author_name,
    )


@router.get("/", response_model=BlogPostList)
def read_blog_posts(
    session: SessionDep,
    skip: int = 0,
    limit: int = 50,
) -> Any:
    """Retrieve published blog posts."""
    count_statement = (
        select(func.count()).select_from(BlogPost).where(BlogPost.published.is_(True))  # type: ignore[attr-defined]
    )
    statement = (
        select(BlogPost, User)
        .join(User, BlogPost.author_id == User.id)
        .where(BlogPost.published.is_(True))  # type: ignore[attr-defined]
        .order_by(col(BlogPost.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    count = session.exec(count_statement).one()
    posts = session.exec(statement).all()
    return BlogPostList(
        data=[_to_list_public(post, author) for post, author in posts],
        count=count,
    )


@router.get("/admin", response_model=BlogPostsPublic)
def read_all_blog_posts(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Admin-only: list all blog posts regardless of published status."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    count_statement = select(func.count()).select_from(BlogPost)
    count = session.exec(count_statement).one()
    statement = (
        select(BlogPost, User)
        .join(User, BlogPost.author_id == User.id)
        .order_by(col(BlogPost.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    posts = session.exec(statement).all()
    return BlogPostsPublic(
        data=[_to_public(post, author) for post, author in posts],
        count=count,
    )


@router.get("/{id}", response_model=BlogPostPublic)
def read_blog_post(session: SessionDep, id: uuid.UUID) -> Any:
    """Get a single blog post by ID."""
    post = session.get(BlogPost, id)
    if not post or not post.published:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return _to_public(post)


@router.post("/", response_model=BlogPostPublic)
def create_blog_post(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    post_in: BlogPostCreate,
) -> Any:
    """Create a new blog post (super admin only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    existing = session.exec(
        select(BlogPost).where(BlogPost.slug == post_in.slug)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A post with this slug already exists")
    post = BlogPost.model_validate(post_in, update={"author_id": current_user.id})
    session.add(post)
    session.commit()
    session.refresh(post)
    return _to_public(post)


@router.put("/{id}", response_model=BlogPostPublic)
def update_blog_post(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    post_in: BlogPostUpdate,
) -> Any:
    """Update a blog post (super admin only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    post = session.get(BlogPost, id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    if post_in.slug and post_in.slug != post.slug:
        existing = session.exec(
            select(BlogPost).where(BlogPost.slug == post_in.slug)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="A post with this slug already exists")
    update_dict = post_in.model_dump(exclude_unset=True)
    update_dict["updated_at"] = datetime.now(timezone.utc)
    post.sqlmodel_update(update_dict)
    session.add(post)
    session.commit()
    session.refresh(post)
    return _to_public(post)


@router.delete("/{id}")
def delete_blog_post(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete a blog post (super admin only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    post = session.get(BlogPost, id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    session.delete(post)
    session.commit()
    return Message(message="Blog post deleted successfully")
