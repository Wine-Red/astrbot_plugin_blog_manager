"""Future task placeholders."""

from __future__ import annotations

from ..exceptions import TaskFeatureDisabledError
from ..models import ScheduledPublishSpec, TaskExecutionResult


class TaskService:
    """Placeholder scheduling entrypoint reserved for future daily reports."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    async def schedule_daily_report(self, spec: ScheduledPublishSpec) -> TaskExecutionResult:
        if not self.enabled:
            raise TaskFeatureDisabledError("当前未启用定时任务能力。")
        return TaskExecutionResult(
            accepted=False,
            message=(
                "已预留定时任务接口，但首期版本尚未实现完整的 FutureTask/日报调度闭环。"
            ),
        )
