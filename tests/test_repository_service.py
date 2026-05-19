import pytest

from astrbot_plugin_blog_manager.exceptions import PluginConfigError
from astrbot_plugin_blog_manager.services.repository_service import RepositoryService


class DummyClient:
    pass


def build_service(config=None):
    return RepositoryService(DummyClient(), config or {"content_dir": "src/content/posts"})


def test_repository_service_allows_article_path_inside_content_dir():
    service = build_service()

    assert (
        service._ensure_article_path_allowed("src/content/posts/demo.md")
        == "src/content/posts/demo.md"
    )


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "src/content/posts/../pages/demo.md",
        "src/assets/blog/demo.md",
        "src/content/posts/demo.txt",
        "",
    ],
)
def test_repository_service_rejects_article_path_outside_content_dir(path):
    service = build_service()

    with pytest.raises(PluginConfigError):
        service._ensure_article_path_allowed(path)


def test_repository_service_rejects_invalid_write_mode():
    service = build_service({"content_dir": "src/content/posts", "write_mode": "force"})

    with pytest.raises(PluginConfigError):
        service._write_mode()
