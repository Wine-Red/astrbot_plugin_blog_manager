from astrbot_plugin_blog_manager.models import DeleteResult, PullRequestMergeResult, PublishResult


def test_publish_result_includes_pr_number():
    result = PublishResult(
        mode="pr",
        branch="astrbot/blog/demo",
        commit_sha="abc123",
        article_path="src/content/posts/demo.md",
        article_title="示例文章",
        slug="示例文章",
        pr_number=12,
        pr_url="https://github.com/example/repo/pull/12",
    )

    lines = result.to_lines()

    assert any("PR 编号: 12" == line for line in lines)


def test_pull_request_merge_result_to_lines():
    result = PullRequestMergeResult(
        number=12,
        title="Publish blog article: 示例文章",
        merged=True,
        sha="deadbeef",
        method="squash",
        url="https://github.com/example/repo/pull/12",
    )

    lines = result.to_lines()

    assert any("状态: 已合并" == line for line in lines)
    assert any("合并方式: squash" == line for line in lines)


def test_delete_result_to_lines():
    result = DeleteResult(
        mode="pr",
        target="welcome-to-my-blog",
        deleted_path="src/content/posts/2026-05-18-welcome-to-my-blog.md",
        branch="astrbot/blog/delete",
        commit_sha="abc123",
        pr_number=18,
        pr_url="https://github.com/example/repo/pull/18",
    )

    lines = result.to_lines()

    assert any("目标: welcome-to-my-blog" == line for line in lines)
    assert any("PR 编号: 18" == line for line in lines)
