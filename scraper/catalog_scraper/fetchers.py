"""Livello di trasporto HTML.

Due implementazioni intercambiabili dietro la stessa interfaccia:

* `RequestsFetcher`  -> HTML server-side (veloce, nessun browser).
* `SeleniumFetcher`  -> cataloghi renderizzati in JS / infinite scroll.

Entrambe applicano rate limiting e, di default, rispettano robots.txt.
"""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import url2pathname

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import HttpConfig

logger = logging.getLogger(__name__)


class FetchError(RuntimeError):
    """Errore non recuperabile durante il download di una pagina."""


class BaseFetcher(ABC):
    def __init__(self, config: HttpConfig) -> None:
        self.config = config
        self._last_request_at = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    # ------------------------------------------------------------------ #
    # API pubblica
    # ------------------------------------------------------------------ #
    @abstractmethod
    def _download(self, url: str) -> str: ...

    def get(self, url: str) -> str:
        # file:// serve a provare la configurazione su pagine salvate in locale.
        if url.startswith("file://"):
            path = url2pathname(urlparse(url).path)
            logger.info("READ %s", path)
            try:
                return Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise FetchError(f"File non leggibile: {path}: {exc}") from exc

        if self.config.respect_robots and not self.is_allowed(url):
            raise FetchError(f"robots.txt vieta lo scraping di {url}")
        self._throttle()
        logger.info("GET %s", url)
        return self._download(url)

    def close(self) -> None:  # pragma: no cover - override opzionale
        return None

    def __enter__(self) -> "BaseFetcher":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Buona educazione
    # ------------------------------------------------------------------ #
    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.config.delay:
            time.sleep(self.config.delay - elapsed)
        self._last_request_at = time.monotonic()

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(urljoin(root, "/robots.txt"))
            try:
                parser.read()
            except Exception as exc:  # robots irraggiungibile -> non blocchiamo
                logger.warning("robots.txt non leggibile per %s: %s", root, exc)
                parser = None
            self._robots[root] = parser
        parser = self._robots[root]
        if parser is None:
            return True
        return parser.can_fetch(self.config.user_agent, url)


class RequestsFetcher(BaseFetcher):
    """Download HTML statico con retry esponenziale e connection pooling."""

    def __init__(self, config: HttpConfig) -> None:
        super().__init__(config)
        self.session = requests.Session()
        retry = Retry(
            total=config.retries,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": config.user_agent,
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
                **config.headers,
            }
        )

    def _download(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise FetchError(f"Download fallito per {url}: {exc}") from exc
        # requests indovina male l'encoding quando manca il charset nell'header
        if response.encoding is None or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        return response.text

    def close(self) -> None:
        self.session.close()


class SeleniumFetcher(BaseFetcher):
    """Rendering completo via Chrome headless per cataloghi JS-driven."""

    def __init__(self, config: HttpConfig) -> None:
        super().__init__(config)
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = self._build_driver()
        return self._driver

    def _build_driver(self):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:  # pragma: no cover
            raise FetchError(
                "Selenium non installato. Usa: pip install 'catalog-scraper[selenium]'"
            ) from exc

        options = Options()
        if self.config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,2400")
        options.add_argument(f"--user-agent={self.config.user_agent}")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(self.config.timeout)
        return driver

    def _download(self, url: str) -> str:
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            self.driver.get(url)
            if self.config.wait_selector:
                WebDriverWait(self.driver, self.config.wait_timeout).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, self.config.wait_selector)
                    )
                )
            if self.config.scroll:
                self._scroll_to_bottom()
            return self.driver.page_source
        except TimeoutException as exc:
            raise FetchError(f"Timeout in attesa del contenuto su {url}") from exc
        except WebDriverException as exc:
            raise FetchError(f"Selenium ha fallito su {url}: {exc}") from exc

    def _scroll_to_bottom(self) -> None:
        """Infinite scroll: continua finché l'altezza pagina smette di crescere."""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        for _ in range(self.config.scroll_max):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(self.config.scroll_pause)
            height = self.driver.execute_script("return document.body.scrollHeight")
            if height == last_height:
                break
            last_height = height

    def close(self) -> None:
        if self._driver is not None:
            self._driver.quit()
            self._driver = None


def build_fetcher(config: HttpConfig) -> BaseFetcher:
    """Factory: istanzia il fetcher indicato in `http.engine`."""
    if config.engine == "selenium":
        return SeleniumFetcher(config)
    return RequestsFetcher(config)
