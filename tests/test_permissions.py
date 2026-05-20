from astrbot_plugin_blog_manager.tools.blog_tools import (
    PERMISSION_DENIED_MESSAGE,
    is_admin_event,
)


class AdminEvent:
    def is_admin(self):
        return True


class MemberEvent:
    def is_admin(self):
        return False


class BrokenEvent:
    def is_admin(self):
        raise RuntimeError("boom")


class RoleAdminEvent:
    role = "admin"


def test_is_admin_event_uses_astrbot_is_admin_method():
    assert is_admin_event(AdminEvent())
    assert not is_admin_event(MemberEvent())


def test_is_admin_event_falls_back_to_role():
    assert is_admin_event(RoleAdminEvent())


def test_is_admin_event_denies_on_error():
    assert not is_admin_event(BrokenEvent())
    assert "AstrBot 管理员" in PERMISSION_DENIED_MESSAGE
