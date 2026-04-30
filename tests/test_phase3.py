"""Phase 3 Tests: Database Indexes, Metrics, and Monitoring.

测试内容：
1. ORM 模型索引声明验证
2. MetricsCollector 单元测试
3. /metrics 端点集成测试
4. Alembic 迁移脚本结构检查
"""
import time
import pytest
import pytest_asyncio

from app.core.metrics import MetricsCollector


# ==================== 1. ORM 模型索引验证 ====================


class TestModelIndexes:
    """验证所有 ORM 模型中声明了必要的索引。"""

    def test_item_owner_id_indexed(self):
        """items.owner_id 必须有索引（FK 列高频查询）。"""
        from app.db.models.item import Item
        col = Item.__table__.columns["owner_id"]
        assert col.index is True, "items.owner_id 缺少索引"

    def test_item_created_at_indexed(self):
        """items.created_at 必须有索引（排序列）。"""
        from app.db.models.item import Item
        col = Item.__table__.columns["created_at"]
        assert col.index is True, "items.created_at 缺少索引"

    def test_comment_item_id_indexed(self):
        """comments.item_id 必须有索引（FK 列高频查询）。"""
        from app.db.models.comment import Comment
        col = Comment.__table__.columns["item_id"]
        assert col.index is True, "comments.item_id 缺少索引"

    def test_comment_author_id_indexed(self):
        """comments.author_id 必须有索引（FK 列）。"""
        from app.db.models.comment import Comment
        col = Comment.__table__.columns["author_id"]
        assert col.index is True, "comments.author_id 缺少索引"

    def test_comment_created_at_indexed(self):
        """comments.created_at 必须有索引（排序列）。"""
        from app.db.models.comment import Comment
        col = Comment.__table__.columns["created_at"]
        assert col.index is True, "comments.created_at 缺少索引"

    def test_article_created_at_indexed(self):
        """articles.created_at 必须有索引（排序列）。"""
        from app.db.models.article import Article
        col = Article.__table__.columns["created_at"]
        assert col.index is True, "articles.created_at 缺少索引"

    def test_article_slug_indexed(self):
        """articles.slug 必须有索引（已有 unique+index）。"""
        from app.db.models.article import Article
        col = Article.__table__.columns["slug"]
        assert col.index is True, "articles.slug 缺少索引"

    def test_article_author_id_indexed(self):
        """articles.author_id 必须有索引（已有 index）。"""
        from app.db.models.article import Article
        col = Article.__table__.columns["author_id"]
        assert col.index is True, "articles.author_id 缺少索引"

    def test_favorites_article_id_has_index(self):
        """favorites 表的 article_id 必须有单独索引（联合 PK 第二列）。"""
        from app.db.models.favorite import Favorite
        table = Favorite.__table__
        index_names = [idx.name for idx in table.indexes]
        assert "ix_favorites_article_id" in index_names, (
            f"favorites 缺少 ix_favorites_article_id 索引, 现有索引: {index_names}"
        )

    def test_followers_following_id_has_index(self):
        """followers 表的 following_id 必须有单独索引（联合 PK 第二列）。"""
        from app.db.models.follower import Follower
        table = Follower.__table__
        index_names = [idx.name for idx in table.indexes]
        assert "ix_followers_following_id" in index_names, (
            f"followers 缺少 ix_followers_following_id 索引, 现有索引: {index_names}"
        )

    def test_item_tags_tag_id_has_index(self):
        """item_tags 关联表的 tag_id 必须有单独索引。"""
        from app.db.models.tag import item_tags
        index_names = [idx.name for idx in item_tags.indexes]
        assert "ix_item_tags_tag_id" in index_names, (
            f"item_tags 缺少 ix_item_tags_tag_id 索引, 现有索引: {index_names}"
        )

    def test_article_tags_tag_id_has_index(self):
        """article_tags 关联表的 tag_id 必须有单独索引。"""
        from app.db.models.article import article_tags
        index_names = [idx.name for idx in article_tags.indexes]
        assert "ix_article_tags_tag_id" in index_names, (
            f"article_tags 缺少 ix_article_tags_tag_id 索引, 现有索引: {index_names}"
        )

    def test_user_email_indexed(self):
        """users.email 必须有索引（已有 unique+index）。"""
        from app.db.models.user import User
        col = User.__table__.columns["email"]
        assert col.index is True, "users.email 缺少索引"


# ==================== 2. MetricsCollector 单元测试 ====================


class TestMetricsCollector:
    """MetricsCollector 核心逻辑测试。"""

    def test_initial_metrics(self):
        """初始状态指标应为零。"""
        m = MetricsCollector()
        data = m.get_metrics()
        assert data["total_requests"] == 0
        assert data["total_errors"] == 0
        assert data["error_rate"] == 0.0
        assert data["top_endpoints"] == []

    def test_record_normal_request(self):
        """记录正常请求后计数+1。"""
        m = MetricsCollector()
        m.record_request("GET", "/api/v1/health", 200, 0.05)
        data = m.get_metrics()
        assert data["total_requests"] == 1
        assert data["total_errors"] == 0
        assert len(data["top_endpoints"]) == 1
        assert data["top_endpoints"][0]["endpoint"] == "GET /api/v1/health"

    def test_record_error_request(self):
        """记录 4xx/5xx 请求后错误计数+1。"""
        m = MetricsCollector()
        m.record_request("POST", "/api/v1/auth/login", 401, 0.1)
        m.record_request("GET", "/api/v1/items", 500, 0.2)
        data = m.get_metrics()
        assert data["total_requests"] == 2
        assert data["total_errors"] == 2
        assert data["errors_by_status"]["401"] == 1
        assert data["errors_by_status"]["500"] == 1

    def test_slow_request_tracking(self):
        """超过阈值的请求会被记录为慢请求。"""
        m = MetricsCollector()
        m._slow_threshold = 0.5  # 降低阈值方便测试
        m.record_request("GET", "/api/v1/articles", 200, 0.3)   # 快
        m.record_request("GET", "/api/v1/articles", 200, 0.8)   # 慢
        m.record_request("GET", "/api/v1/articles", 200, 1.5)   # 慢
        data = m.get_metrics()
        assert len(data["recent_slow_requests"]) == 2
        assert data["recent_slow_requests"][0]["duration_ms"] == 800.0

    def test_average_latency(self):
        """平均延迟计算正确。"""
        m = MetricsCollector()
        m.record_request("GET", "/test", 200, 0.1)
        m.record_request("GET", "/test", 200, 0.3)
        data = m.get_metrics()
        # 平均 (100+300)/2 = 200ms
        ep = data["slowest_endpoints"][0]
        assert ep["endpoint"] == "GET /test"
        assert ep["avg_ms"] == 200.0

    def test_top_endpoints_sorted(self):
        """Top 端点按请求量降序排列。"""
        m = MetricsCollector()
        for _ in range(5):
            m.record_request("GET", "/a", 200, 0.01)
        for _ in range(10):
            m.record_request("GET", "/b", 200, 0.01)
        for _ in range(3):
            m.record_request("GET", "/c", 200, 0.01)
        data = m.get_metrics()
        endpoints = [e["endpoint"] for e in data["top_endpoints"]]
        assert endpoints == ["GET /b", "GET /a", "GET /c"]

    def test_reset(self):
        """reset() 清空所有指标。"""
        m = MetricsCollector()
        m.record_request("GET", "/test", 200, 0.1)
        m.reset()
        data = m.get_metrics()
        assert data["total_requests"] == 0

    def test_uptime(self):
        """运行时长应大于 0。"""
        m = MetricsCollector()
        time.sleep(0.1)
        data = m.get_metrics()
        assert data["uptime_seconds"] >= 0.1

    def test_error_rate_calculation(self):
        """错误率计算: errors / total * 100。"""
        m = MetricsCollector()
        m.record_request("GET", "/a", 200, 0.01)
        m.record_request("GET", "/a", 200, 0.01)
        m.record_request("GET", "/a", 500, 0.01)
        m.record_request("GET", "/a", 404, 0.01)
        data = m.get_metrics()
        # 2 errors / 4 total = 50%
        assert data["error_rate"] == 50.0


# ==================== 3. /metrics 端点集成测试 ====================


@pytest.mark.asyncio
class TestMetricsEndpoint:
    """测试 /v1/metrics 端点（需要管理员权限）。"""

    async def test_metrics_unauthorized(self, client):
        """未认证用户不能访问 /metrics。"""
        resp = await client.get("/api/v1/metrics")
        assert resp.status_code == 401

    async def test_metrics_forbidden_for_normal_user(self, client, auth_headers):
        """普通用户访问 /metrics 返回 403。"""
        resp = await client.get("/api/v1/metrics", headers=auth_headers)
        assert resp.status_code == 403

    async def test_metrics_accessible_by_admin(self, client, db_session):
        """管理员用户可以正常访问 /metrics。"""
        from app.core.security import create_access_token, get_password_hash
        from app.db.models.user import User

        admin = User(
            email="admin@example.com",
            hashed_password=get_password_hash("adminpass"),
            full_name="Admin",
            role="admin",
        )
        db_session.add(admin)
        await db_session.commit()

        token = create_access_token(subject=admin.email)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/v1/metrics", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # 验证返回的指标结构
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "total_errors" in data
        assert "error_rate" in data
        assert "top_endpoints" in data
        assert "slowest_endpoints" in data
        assert "errors_by_status" in data
        assert "recent_slow_requests" in data


# ==================== 4. Alembic 迁移脚本结构检查 ====================


class TestAlembicMigration:
    """验证索引迁移脚本结构正确。"""

    def test_migration_file_exists(self):
        """迁移文件存在。"""
        from pathlib import Path
        migration = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "a3f7b9c12d45_add_performance_indexes.py"
        assert migration.exists(), f"迁移文件不存在: {migration}"

    def test_migration_has_all_indexes(self):
        """迁移文件包含所有 10 个索引。"""
        from pathlib import Path
        migration = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "a3f7b9c12d45_add_performance_indexes.py"
        content = migration.read_text(encoding="utf-8")

        expected_indexes = [
            "ix_items_owner_id",
            "ix_items_created_at",
            "ix_comments_item_id",
            "ix_comments_author_id",
            "ix_comments_created_at",
            "ix_favorites_article_id",
            "ix_followers_following_id",
            "ix_articles_created_at",
            "ix_item_tags_tag_id",
            "ix_article_tags_tag_id",
        ]
        for idx in expected_indexes:
            assert idx in content, f"迁移文件缺少索引: {idx}"

    def test_migration_has_downgrade(self):
        """迁移文件包含 downgrade 函数（可回滚）。"""
        from pathlib import Path
        migration = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "a3f7b9c12d45_add_performance_indexes.py"
        content = migration.read_text(encoding="utf-8")
        assert "def downgrade" in content
        assert "drop_index" in content
