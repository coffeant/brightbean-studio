# Plan: Inbox Optimization - 收件箱文案修改 & Bug 修复

## Overview

**Objective**: 
1. 侧边栏文案从「社交收件箱」改为「收件箱」
2. 空状态描述已为正确文案，无需修改 (confirmed)
3. 修复 Bug：收件箱同步 (`InboxSyncEngine`) 未注册为周期性后台任务，导致消息不会每 5 分钟自动同步

## Background

`InboxSyncEngine.sync_all()` 是收件箱核心同步逻辑，轮询所有已关联社交账户的新消息（评论、提及、私信）。

当前问题：
- publisher 的 `run_publish_cycle` 和 social_accounts 的 `schedule_all_health_checks` 都通过 `AppConfig.ready()` + `post_migrate` 信号注册为周期性 `background_task`
- 但 inbox 同步**没有**做同样的注册，只在一个独立的 `management/commands/run_inbox_sync.py` 中可用
- `docker-compose.yml` 和 `Procfile` 中的 worker 只跑 `process_tasks`，不会启动 `run_inbox_sync`
- 因此 **收件箱不会自动每 5 分钟同步** — 这是功能性 Bug

## Scope

### IN
- `templates/base.html`: 侧边栏文案 `社交收件箱` → `收件箱`
- `apps/inbox/apps.py`: 新增周期性后台任务注册（每 5 分钟运行 `InboxSyncEngine.sync_all()`）
- `apps/inbox/tasks.py`: 新增一个 `@background` 函数 (如 `run_inbox_sync_all`) 作为入口

### OUT
- 不对 `_empty_state.html` 做任何修改（已正确）
- 不修改 docker-compose.yml / Procfile（使用已有 `process_tasks` worker）
- 不修改 `management/commands/run_inbox_sync.py`（保留作为手动调试入口）
- 不涉及 RSS/Feed 功能

## Task Breakdown

---

### Task 1: 修改侧边栏文案

**File**: `templates/base.html`

**Change**: Line 601, change `<span class="sidebar-nav-label">社交收箱</span>` to `<span class="sidebar-nav-label">收件箱</span>`

**Pattern reference**:
```
old: <span class="sidebar-nav-label">社交收件箱</span>
new: <span class="sidebar-nav-label">收件箱</span>
```

**Verification**: 搜索确认没有其他「社交收件箱」出现在模板文件中。

**QA**: 
- 手动检查侧边栏渲染后显示为「收件箱」
- 确保 active 状态样式不受影响

---

### Task 2: 创建 inbox 后台同步任务函数

**File**: `apps/inbox/tasks.py`

**What**: 在 `InboxSyncEngine` 类之外，新增一个模块级别的 `@background` 函数：

```python
@background(schedule=0)
def run_inbox_sync_all():
    """Recurring background task to sync all inbox messages."""
    engine = InboxSyncEngine()
    engine.sync_all()
```

**Pattern reference**: 参考 `apps/publisher/tasks.py` 的 `run_publish_cycle`：

```python
@background(schedule=0)
def run_publish_cycle():
    from apps.publisher.engine import PublishEngine
    engine = PublishEngine()
    published = engine.poll_and_publish()
    if published:
        logger.info("Publish cycle completed - %d post(s) published", published)
```

**Placement**: 放在文件末尾，`check_sla` 方法之后。

**QA**:
- 函数签名必须包含 `@background(schedule=0)` 装饰器
- 函数只实例化 `InboxSyncEngine` 并调用 `sync_all()`，不做别的
- 确保导入正确

---

### Task 3: 注册周期性任务

**File**: `apps/inbox/apps.py`

**What**: 将 `InboxConfig` 扩展为注册周期性后台任务。参考 `apps/publisher/apps.py` 的模式：

```python
"""AppConfig for the inbox app."""
import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class InboxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inbox"
    verbose_name = "Inbox"

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(self._register_inbox_sync_task, sender=self)

    @staticmethod
    def _register_inbox_sync_task(sender, **kwargs):
        """Register the recurring inbox sync task (every 5 minutes)."""
        try:
            from background_task.models import Task
            from apps.inbox.tasks import run_inbox_sync_all

            if not Task.objects.filter(verbose_name="run_inbox_sync_all").exists():
                run_inbox_sync_all(
                    repeat=300,  # 5 minutes in seconds
                    verbose_name="run_inbox_sync_all",
                )
                logger.info("Registered recurring inbox sync task (every 5min)")
        except Exception:
            logger.debug("Skipping inbox sync task registration (database not ready)")
```

**Pattern reference**: 参考 `apps/publisher/apps.py`：
- `_register_publish_task` → `repeat=15`（15秒）
- 我们的任务 → `repeat=300`（300秒 = 5分钟）

**QA**:
- `ready()` 方法连接到 `post_migrate` 信号
- `_register_inbox_sync_task` 用 `try/except` 保护（数据库未就绪时优雅降级）
- `Task.objects.filter(verbose_name=...)` 做幂等检查，避免重复注册
- `repeat=300` 对应 5 分钟同步间隔

---

### Task 4: 验证

**What**: 确认所有改动正确且可用。

**Steps**:
1. 检查 `templates/base.html` 中「社交收件箱」已全部替换为「收件箱」（仅剩一条，确认侧边栏渲染正确）
2. 检查 `apps/inbox/tasks.py` 中新增的 `run_inbox_sync_all` 函数导入无错误
3. 检查 `apps/inbox/apps.py` 的 `InboxConfig` 改动，确认：
   - `ready()` 方法存在
   - `post_migrate` 信号连接正确
   - `repeat` 参数为 300
4. 运行 `python manage.py check` 确认无 lint/import 错误
5. （可选）运行一次 migration 后检查 `background_task.Task` 表中是否出现 `run_inbox_sync_all`

## Files Modified Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `templates/base.html` | Edit | Line 601: `社交收件箱` → `收件箱` |
| `apps/inbox/tasks.py` | Edit | 新增 `run_inbox_sync_all` @background 函数 |
| `apps/inbox/apps.py` | Edit | 新增 `ready()` + 周期性任务注册 |

## Rollback Plan

如果出现问题：
1. 恢复 `templates/base.html` 中 `收件箱` → `社交收件箱`
2. 从 `apps/inbox/tasks.py` 中删除 `run_inbox_sync_all` 函数
3. 从 `apps/inbox/apps.py` 中恢复原始内容（只保留 class + 3 行属性）
4. 运行 `python manage.py process_tasks` 确保无报错（Task 表会自动清理孤立记录）

---

## Final Verification Wave

- [ ] Task 1: 侧边栏文案确认已修改
- [ ] Task 2: `run_inbox_sync_all` 函数已添加到 tasks.py
- [ ] Task 3: `apps.py` 注册逻辑已完成
- [ ] `python manage.py check` 通过
- [ ] 侧边栏 UI 显示「收件箱」正确
- [ ] 不需要用户手动批准，自动完成

**当所有验证通过后，通知用户查看结果。**
