"""短信发送抽象模块。

封装 mock、阿里云、Twilio 等短信供应商的统一发送接口。"""

from abc import ABC, abstractmethod

from loguru import logger

from app.core.config import settings


class SmsProvider(ABC):
    """短信发送统一接口"""

    @abstractmethod
    async def send_sms(self, phone: str, code: str) -> bool:
        """发送短信验证码，成功返回 True。"""


class MockSmsProvider(SmsProvider):
    """Mock 实现：仅打印到控制台，用于开发/测试。"""

    async def send_sms(self, phone: str, code: str) -> bool:
        logger.info(f"[SMS-Mock] Sending code {code} to {phone}")
        print(f"\n{'='*40}")
        print(f"  [SMS Mock] To: {phone}")
        print(f"  [SMS Mock] Code: {code}")
        print(f"  [SMS Mock] (This is a mock, no real SMS sent)")
        print(f"{'='*40}\n")
        return True


class AliyunSmsProvider(SmsProvider):
    """阿里云短信实现。需安装 alibabacloud-dysmsapi20170525。"""

    def __init__(self):
        try:
            from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
            from alibabacloud_tea_openapi import models as open_api_models
        except ImportError:
            logger.error("Missing dependency: pip install alibabacloud_dysmsapi20170525")
            # 这里如果不抛异常，后面调用都会报错。
            # 为了不影响应用启动（如果没配置短信），可以暂时 pass，等到 send_sms 时再报错
            self.client = None
            return

        # 初始化 Client
        config = open_api_models.Config(
            access_key_id=settings.aliyun_access_key_id,
            access_key_secret=settings.aliyun_access_key_secret
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        self.client = DysmsClient(config)

    async def send_sms(self, phone: str, code: str) -> bool:
        if not self.client:
            logger.error("❌ Aliyun SDK not installed or client init failed")
            return False

        try:
            from alibabacloud_dysmsapi20170525 import models as dysms_models
            from alibabacloud_tea_util import models as util_models
            import json
        except ImportError:
             return False

        # 检查配置
        if not settings.aliyun_sms_sign_name or not settings.aliyun_sms_template_code:
            logger.error("❌ Aliyun SMS config missing: sign_name or template_code")
            return False

        request = dysms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=settings.aliyun_sms_sign_name,
            template_code=settings.aliyun_sms_template_code,
            template_param=json.dumps({"code": code}),  # 假设模板变量名为 code
        )
        
        try:
            # 同步 SDK 调用（为了不阻塞 Loop，放入线程池执行）
            import asyncio
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self.client.send_sms_with_options(request, util_models.RuntimeOptions())
            )
            
            if resp.body.code == 'OK':
                logger.info(f"✅ SMS sent to {phone}: {resp.body.message}")
                return True
            else:
                logger.error(f"❌ SMS failed: {resp.body.code} - {resp.body.message}")
                return False
        except Exception as e:
            logger.exception(f"❌ SMS exception: {str(e)}")
            return False


class TwilioSmsProvider(SmsProvider):
    """Twilio 短信（预留桩，需安装 twilio）。"""

    async def send_sms(self, phone: str, code: str) -> bool:
        # TODO: 接入 Twilio SDK
        # from twilio.rest import Client
        # ...
        raise NotImplementedError("Twilio SMS not configured yet")


def get_sms_provider() -> SmsProvider:
    """根据 settings.sms_provider 返回对应的短信实现。"""
    provider = getattr(settings, "sms_provider", "mock")
    if provider == "aliyun":
        return AliyunSmsProvider()
    elif provider == "twilio":
        return TwilioSmsProvider()
    return MockSmsProvider()

