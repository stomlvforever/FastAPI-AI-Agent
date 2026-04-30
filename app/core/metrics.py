"""应用指标收集模块。

用内存计数器记录请求量、错误量、慢请求和端点统计，供 metrics 接口查看。"""

import time
from collections import defaultdict
from threading import Lock

from app.core.config import settings


class MetricsCollector:
    """线程安全的指标收集器。"""

    def __init__(self):
        self._lock = Lock()
        self._start_time = time.time()
        # 总请求计数（按 method + path 分组）
        self._request_count: dict[str, int] = defaultdict(int)
        # 总错误计数（按状态码分组）
        self._error_count: dict[str, int] = defaultdict(int)
        # 延迟累计（按 path 分组，用于计算平均延迟）
        self._latency_sum: dict[str, float] = defaultdict(float)
        self._latency_count: dict[str, int] = defaultdict(int)
        # 慢请求记录（最近 N 条）
        self._slow_requests: list[dict] = []
        self._slow_threshold = getattr(settings, "slow_request_threshold", 1.0)  # 秒
        self._max_slow_records = 50

    def record_request(self, method: str, path: str, status_code: int, duration: float):
        """记录一次请求。"""
        with self._lock:
            key = f"{method} {path}"
            self._request_count[key] += 1
            self._latency_sum[key] += duration
            self._latency_count[key] += 1

            if status_code >= 400:
                self._error_count[str(status_code)] += 1

            if duration >= self._slow_threshold:
                self._slow_requests.append({
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "timestamp": time.time(),
                })
                # 只保留最近 N 条
                if len(self._slow_requests) > self._max_slow_records:
                    self._slow_requests = self._slow_requests[-self._max_slow_records:]

    def get_metrics(self) -> dict:
        """导出当前指标快照。"""
        with self._lock:
            uptime = time.time() - self._start_time
            total_requests = sum(self._request_count.values())
            total_errors = sum(self._error_count.values())

            # 按请求量排序的 Top 10 端点
            top_endpoints = sorted(
                self._request_count.items(), key=lambda x: x[1], reverse=True
            )[:10]

            # 按平均延迟排序的 Top 10 慢端点
            avg_latency = {}
            for key in self._latency_sum:
                count = self._latency_count[key]
                if count > 0:
                    avg_latency[key] = round(self._latency_sum[key] / count * 1000, 2)
            slowest_endpoints = sorted(
                avg_latency.items(), key=lambda x: x[1], reverse=True
            )[:10]

            return {
                "uptime_seconds": round(uptime, 1),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": round(total_errors / max(total_requests, 1) * 100, 2),
                "top_endpoints": [
                    {"endpoint": k, "count": v} for k, v in top_endpoints
                ],
                "slowest_endpoints": [
                    {"endpoint": k, "avg_ms": v} for k, v in slowest_endpoints
                ],
                "errors_by_status": dict(self._error_count),
                "recent_slow_requests": self._slow_requests[-10:],
            }

    def reset(self):
        """重置所有指标（用于测试）。"""
        with self._lock:
            self._request_count.clear()
            self._error_count.clear()
            self._latency_sum.clear()
            self._latency_count.clear()
            self._slow_requests.clear()
            self._start_time = time.time()


# 全局单例
metrics = MetricsCollector()

