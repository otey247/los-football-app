import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.crud import get_user_by_email
from app.models import BlogPost


def _create_blog_post(
    db: Session,
    *,
    title: str = "League Notes",
    slug: str | None = None,
    published: bool = True,
) -> BlogPost:
    user = get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user
    post = BlogPost(
        title=title,
        slug=slug or f"league-notes-{uuid.uuid4()}",
        excerpt="Short league update",
        content="Full private commissioner notes",
        published=published,
        author_id=user.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def test_read_blog_posts_only_returns_published_summaries(
    client: TestClient, db: Session
) -> None:
    published = _create_blog_post(db, title="Published Post", published=True)
    draft = _create_blog_post(db, title="Draft Post", published=False)

    response = client.get(f"{settings.API_V1_STR}/blog/")

    assert response.status_code == 200
    content = response.json()
    titles = {post["title"] for post in content["data"]}
    assert published.title in titles
    assert draft.title not in titles
    assert all("content" not in post for post in content["data"])


def test_read_draft_blog_post_not_found(client: TestClient, db: Session) -> None:
    draft = _create_blog_post(db, published=False)

    response = client.get(f"{settings.API_V1_STR}/blog/{draft.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Blog post not found"


def test_create_blog_post_superuser_only(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {
        "title": "No Access",
        "slug": f"no-access-{uuid.uuid4()}",
        "excerpt": "Should fail",
        "content": "Only superusers can post",
        "published": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/blog/",
        headers=normal_user_token_headers,
        json=data,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_create_blog_post_rejects_duplicate_slug(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    slug = f"duplicate-{uuid.uuid4()}"
    _create_blog_post(db, slug=slug)
    data = {
        "title": "Duplicate",
        "slug": slug,
        "excerpt": "Duplicate slug",
        "content": "This should not be created",
        "published": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/blog/",
        headers=superuser_token_headers,
        json=data,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "A post with this slug already exists"


def test_update_and_delete_blog_post_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    post = _create_blog_post(db, title="Old Title")

    update_response = client.put(
        f"{settings.API_V1_STR}/blog/{post.id}",
        headers=superuser_token_headers,
        json={"title": "New Title", "published": False},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "New Title"
    assert updated["published"] is False

    delete_response = client.delete(
        f"{settings.API_V1_STR}/blog/{post.id}",
        headers=superuser_token_headers,
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Blog post deleted successfully"
    assert db.exec(select(BlogPost).where(BlogPost.id == post.id)).first() is None


def test_update_and_delete_blog_post_normal_user_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    post = _create_blog_post(db)

    update_response = client.put(
        f"{settings.API_V1_STR}/blog/{post.id}",
        headers=normal_user_token_headers,
        json={"title": "Blocked"},
    )
    delete_response = client.delete(
        f"{settings.API_V1_STR}/blog/{post.id}",
        headers=normal_user_token_headers,
    )

    assert update_response.status_code == 403
    assert delete_response.status_code == 403
