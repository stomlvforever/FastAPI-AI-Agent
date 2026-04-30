"""Tests for Phase 2: Storage abstraction & Verification code system."""
import os
os.environ["ENVIRONMENT"] = "test"

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO

from fastapi import UploadFile


# ==================== Storage Tests ====================

class TestLocalStorage:
    """Test LocalStorage implementation."""

    @pytest.mark.asyncio
    async def test_save_file_returns_url(self, tmp_path):
        """保存文件后应返回 /static/avatars/xxx.jpg 格式的 URL"""
        from app.core.storage import LocalStorage

        storage = LocalStorage()
        storage.root = tmp_path  # 使用临时目录

        # 创建一个假的 UploadFile
        content = b"fake image content"
        file = UploadFile(filename="test.jpg", file=BytesIO(content))

        url = await storage.save(file, folder="avatars")

        assert url.startswith("/static/avatars/")
        assert url.endswith(".jpg")
        # 验证文件确实写入了磁盘
        saved_name = url.split("/")[-1]
        assert (tmp_path / "avatars" / saved_name).exists()

    @pytest.mark.asyncio
    async def test_save_file_with_no_folder(self, tmp_path):
        """不指定 folder 时应保存到根目录"""
        from app.core.storage import LocalStorage

        storage = LocalStorage()
        storage.root = tmp_path

        file = UploadFile(filename="doc.pdf", file=BytesIO(b"content"))
        url = await storage.save(file)

        assert url.startswith("/static/")
        assert url.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_delete_file(self, tmp_path):
        """删除已保存的文件"""
        from app.core.storage import LocalStorage

        storage = LocalStorage()
        storage.root = tmp_path

        file = UploadFile(filename="to_delete.png", file=BytesIO(b"data"))
        url = await storage.save(file, folder="avatars")

        result = await storage.delete(url)
        assert result is True

        # 再次删除应返回 False
        result2 = await storage.delete(url)
        assert result2 is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self, tmp_path):
        """删除不存在的文件应返回 False"""
        from app.core.storage import LocalStorage

        storage = LocalStorage()
        storage.root = tmp_path

        result = await storage.delete("/static/avatars/nonexistent.jpg")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_invalid_url(self, tmp_path):
        """无效 URL 前缀应返回 False"""
        from app.core.storage import LocalStorage

        storage = LocalStorage()
        storage.root = tmp_path

        result = await storage.delete("https://example.com/file.jpg")
        assert result is False


class TestStorageFactory:
    """Test get_storage_service factory."""

    def test_default_returns_local(self):
        """默认应返回 LocalStorage"""
        from app.core.storage import get_storage_service, LocalStorage
        service = get_storage_service()
        assert isinstance(service, LocalStorage)


# ==================== Verification Service Tests ====================

class TestVerificationService:
    """Test VerificationService with mocked Redis."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """创建一个模拟的 Redis 客户端"""
        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=False)
        redis.set = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        redis.ttl = AsyncMock(return_value=45)
        return redis

    @pytest.mark.asyncio
    async def test_send_code_generates_6_digits(self, mock_redis):
        """生成的验证码应为 6 位数字"""
        from app.services.verification_service import VerificationService
        service = VerificationService(mock_redis)

        code = await service.send_code("test@example.com")

        assert len(code) == 6
        assert code.isdigit()

    @pytest.mark.asyncio
    async def test_send_code_stores_in_redis(self, mock_redis):
        """验证码应被存入 Redis"""
        from app.services.verification_service import VerificationService
        service = VerificationService(mock_redis)

        code = await service.send_code("test@example.com")

        # 应该调用了 redis.set 两次（一次存码，一次存冷却）
        assert mock_redis.set.call_count == 2

    @pytest.mark.asyncio
    async def test_send_code_respects_cooldown(self, mock_redis):
        """冷却期内重复请求应抛出 ValueError"""
        from app.services.verification_service import VerificationService

        mock_redis.exists = AsyncMock(return_value=True)  # 冷却中
        service = VerificationService(mock_redis)

        with pytest.raises(ValueError, match="wait"):
            await service.send_code("test@example.com")

    @pytest.mark.asyncio
    async def test_verify_code_success(self, mock_redis):
        """正确验证码应返回 True 并删除"""
        from app.services.verification_service import VerificationService

        mock_redis.get = AsyncMock(return_value="123456")
        service = VerificationService(mock_redis)

        result = await service.verify_code("test@example.com", "123456")

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_code_wrong_code(self, mock_redis):
        """错误验证码应返回 False"""
        from app.services.verification_service import VerificationService

        mock_redis.get = AsyncMock(return_value="123456")
        service = VerificationService(mock_redis)

        result = await service.verify_code("test@example.com", "000000")

        assert result is False
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_code_expired(self, mock_redis):
        """过期（Redis 中不存在）应返回 False"""
        from app.services.verification_service import VerificationService

        mock_redis.get = AsyncMock(return_value=None)
        service = VerificationService(mock_redis)

        result = await service.verify_code("test@example.com", "123456")

        assert result is False


# ==================== SMS Provider Tests ====================

class TestMockSmsProvider:
    """Test MockSmsProvider."""

    @pytest.mark.asyncio
    async def test_mock_sms_returns_true(self):
        """Mock 短信发送应返回 True"""
        from app.core.sms import MockSmsProvider
        provider = MockSmsProvider()

        result = await provider.send_sms("13800138000", "123456")
        assert result is True

    def test_factory_default_returns_mock(self):
        """默认 sms_provider=mock 时应返回 MockSmsProvider"""
        from app.core.sms import get_sms_provider, MockSmsProvider
        provider = get_sms_provider()
        assert isinstance(provider, MockSmsProvider)


# ==================== API Route Tests ====================

class TestVerificationRoutes:
    """Test verification API endpoints."""

    @pytest.mark.asyncio
    async def test_send_code_success(self, client):
        """Success: send-code should queue Celery task and return 202."""
        with patch("app.api.v1.routes.verification.get_redis") as mock_get_redis, \
             patch("app.api.v1.routes.verification.TaskDispatchService.queue_verification_email") as mock_queue:

            mock_redis = AsyncMock()
            mock_redis.exists = AsyncMock(return_value=False)
            mock_redis.set = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_queue.return_value = "task-123"

            resp = await client.post(
                "/api/v1/auth/send-code",
                json={"email": "test@example.com"},
            )
            assert resp.status_code == 202
            assert "Verification code queued" in resp.json()["message"]
            assert resp.json()["task_id"] == "task-123"

    @pytest.mark.asyncio
    async def test_verify_code_invalid(self, client):
        """错误验证码应返回 400"""
        with patch("app.api.v1.routes.verification.get_redis") as mock_get_redis:

            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_get_redis.return_value = mock_redis

            resp = await client.post(
                "/api/v1/auth/verify-code",
                json={"email": "test@example.com", "code": "000000"},
            )
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_sms_code_success(self, client):
        """Success: send-sms-code should queue Celery task and return 202."""
        with patch("app.api.v1.routes.verification.get_redis") as mock_get_redis, \
             patch("app.api.v1.routes.verification.TaskDispatchService.queue_sms_code") as mock_queue:

            mock_redis = AsyncMock()
            mock_redis.exists = AsyncMock(return_value=False)
            mock_redis.set = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_queue.return_value = "task-456"

            resp = await client.post(
                "/api/v1/auth/send-sms-code",
                json={"phone": "13800138000"},
            )
            assert resp.status_code == 202
            assert "SMS code queued" in resp.json()["message"]
            assert resp.json()["task_id"] == "task-456"

