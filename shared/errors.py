"""自定义异常类型与错误处理策略。"""


class AppError(Exception):
    """应用基础异常。"""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause

    def __str__(self) -> str:
        if self.cause is None:
            return self.message
        return f"{self.message} (caused by: {self.cause})"


class CollectorError(AppError):
    """采集层异常：API 调用失败、超时、限流等。"""


class GeneratorError(AppError):
    """生成层异常：数据整理或模板渲染失败。"""


class NotifierError(AppError):
    """推送层异常：邮件或飞书机器人发送失败。"""


class ConfigError(AppError):
    """配置读取或校验失败。"""
