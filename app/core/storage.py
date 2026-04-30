"""文件存储抽象模块。

统一本地存储和对象存储接口，用于头像等上传文件管理。"""

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from loguru import logger

from app.core.config import BASE_DIR, settings


# ---------- 抽象基类 ----------

class StorageService(ABC):
    """文件存储统一接口"""

    @abstractmethod
    async def save(self, file: UploadFile, folder: str = "") -> str:
        """保存文件，返回可访问的 URL。"""

    @abstractmethod
    async def delete(self, file_url: str) -> bool:
        """删除文件，成功返回 True。"""


# ---------- 本地存储实现 ----------

class LocalStorage(StorageService):
    """将文件存储到本地 uploads/ 目录"""

    def __init__(self):
        self.root = BASE_DIR / "uploads"
        self.root.mkdir(parents=True, exist_ok=True)
        # 对应 app.mount("/static/avatars", ...) 的前缀
        self.url_prefix = "/static"

    async def save(self, file: UploadFile, folder: str = "") -> str:
        ext = Path(file.filename or "file").suffix.lower()
        name = f"{uuid.uuid4().hex}{ext}"

        target_dir = self.root / folder if folder else self.root
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / name

        await file.seek(0)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(await file.read())

        url = f"{self.url_prefix}/{folder}/{name}" if folder else f"{self.url_prefix}/{name}"
        logger.info(f"[LocalStorage] saved -> {url}")
        return url

    async def delete(self, file_url: str) -> bool:
        if not file_url or not file_url.startswith(self.url_prefix):
            return False
        relative = file_url[len(self.url_prefix):].lstrip("/")
        path = self.root / relative
        if path.is_file():
            path.unlink()
            logger.info(f"[LocalStorage] deleted -> {file_url}")
            return True
        return False


# ---------- S3 兼容存储实现（预留） ----------

class S3Storage(StorageService):
    """AWS S3 / MinIO 兼容存储（需要 boto3）。

    所需环境变量：
    - S3_BUCKET_NAME, S3_REGION
    - S3_ENDPOINT_URL (MinIO 时填写，AWS 留空)
    - S3_ACCESS_KEY / S3_SECRET_KEY
    """

    def __init__(self):
        try:
            import boto3
        except ImportError:
            raise RuntimeError("S3Storage requires boto3. Run: pip install boto3")

        session = boto3.Session(
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        kwargs = {}
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        self.client = session.client("s3", **kwargs)
        self.bucket = settings.s3_bucket_name

    async def save(self, file: UploadFile, folder: str = "") -> str:
        ext = Path(file.filename or "file").suffix.lower()
        key = f"{folder}/{uuid.uuid4().hex}{ext}" if folder else f"{uuid.uuid4().hex}{ext}"

        await file.seek(0)
        content = await file.read()

        # boto3 是同步的，生产建议用 aioboto3 或线程池
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
        )

        if settings.s3_endpoint_url:
            url = f"{settings.s3_endpoint_url}/{self.bucket}/{key}"
        else:
            url = f"https://{self.bucket}.s3.{settings.s3_region}.amazonaws.com/{key}"

        logger.info(f"[S3Storage] uploaded -> {url}")
        return url

    async def delete(self, file_url: str) -> bool:
        try:
            if settings.s3_endpoint_url:
                key = file_url.split(f"/{self.bucket}/", 1)[1]
            else:
                key = file_url.split(".amazonaws.com/", 1)[1]
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"[S3Storage] deleted -> {key}")
            return True
        except Exception as e:
            logger.error(f"[S3Storage] delete failed: {e}")
            return False


# ---------- 工厂函数 ----------

def get_storage_service() -> StorageService:
    """根据 settings.storage_type 返回对应的存储实现。"""
    if settings.storage_type == "s3":
        return S3Storage()
    return LocalStorage()

