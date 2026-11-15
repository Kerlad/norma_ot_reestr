import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import platform_info

from .base_backend import BaseBackend, BackendRegistry

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    total_retries: int = 3
    backoff_factor: float = 1.0
    status_forcelist: tuple = (429, 500, 502, 503, 504)
    allowed_methods: tuple = ("HEAD", "GET", "OPTIONS", "POST")
    timeout: int = 60


class _ContextAdapter(HTTPAdapter):
    def __init__(self, ssl_context, *args, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(*args, **kwargs)


class RequestsBackend(BaseBackend):
    name = "requests"

    def __init__(self):
        self._config = SessionConfig()

    @staticmethod
    def _make_adapter(retry_strategy, verify: bool) -> HTTPAdapter:
        """Windows: stock adapter. Linux: system trust store / CA file via an SSL context."""
        if verify is True and platform_info.IS_LINUX:
            from utils.tls_context import build_ssl_context
            return _ContextAdapter(build_ssl_context(), max_retries=retry_strategy)
        return HTTPAdapter(max_retries=retry_strategy)

    def _create_session(
        self,
        proxies: Optional[Dict[str, str]] = None,
        verify: bool = True,
    ) -> requests.Session:
        session = requests.Session()
        session.verify = verify
        if proxies:
            session.proxies.update(proxies)
        retry_strategy = Retry(
            total=self._config.total_retries,
            backoff_factor=self._config.backoff_factor,
            status_forcelist=list(self._config.status_forcelist),
            allowed_methods=list(self._config.allowed_methods),
        )
        adapter = self._make_adapter(retry_strategy, verify)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def is_available(self) -> bool:
        try:
            import requests as _
            return True
        except ImportError:
            return False

    def send(
        self, url: str, files: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 60, verify: bool = True,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> tuple[bool, int, bytes, str]:
        logger.info("RequestsBackend: POST")
        session = self._create_session(proxies, verify)
        try:
            response = session.post(
                url, files=files, headers=headers,
                timeout=timeout, verify=verify
            )
            return True, response.status_code, response.content, ""
        except requests.ConnectionError as e:
            logger.error("RequestsBackend connection error: %s", type(e).__name__)
            return False, 0, b"", str(e)
        except requests.Timeout as e:
            logger.error("RequestsBackend timeout: %s", type(e).__name__)
            return False, 0, b"", str(e)
        except requests.RequestException as e:
            logger.error("RequestsBackend request error: %s", type(e).__name__)
            return False, 0, b"", str(e)
        finally:
            session.close()

    def get(
        self, url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: int = 60, verify: bool = True,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> tuple[bool, int, bytes, str]:
        logger.info("RequestsBackend: GET")
        session = self._create_session(proxies, verify)
        try:
            response = session.get(
                url, headers=headers, params=params,
                timeout=timeout, verify=verify
            )
            return True, response.status_code, response.content, ""
        except requests.ConnectionError as e:
            logger.error("RequestsBackend connection error: %s", type(e).__name__)
            return False, 0, b"", str(e)
        except requests.Timeout as e:
            logger.error("RequestsBackend timeout: %s", type(e).__name__)
            return False, 0, b"", str(e)
        except requests.RequestException as e:
            logger.error("RequestsBackend request error: %s", type(e).__name__)
            return False, 0, b"", str(e)
        finally:
            session.close()


BackendRegistry.register(RequestsBackend)
