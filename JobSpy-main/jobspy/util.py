from __future__ import annotations

import logging
import re
from itertools import cycle

import numpy as np
import requests
import tls_client
import urllib3
from markdownify import markdownify as md
from requests.adapters import HTTPAdapter, Retry

from jobspy.model import CompensationInterval, JobType, Site

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_logger(name: str):
    logger = logging.getLogger(f"JobSpy:{name}")
    logger.propagate = False
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        formatter = logging.Formatter(format)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger


class RotatingProxySession:
    def __init__(self, proxies=None):
        if isinstance(proxies, str):
            self.proxy_cycle = cycle([self.format_proxy(proxies)])
        elif isinstance(proxies, list):
            self.proxy_cycle = (
                cycle([self.format_proxy(proxy) for proxy in proxies])
                if proxies
                else None
            )
        else:
            self.proxy_cycle = None

    @staticmethod
    def format_proxy(proxy):
        """Utility method to format a proxy string into a dictionary."""
        if proxy.startswith("http://") or proxy.startswith("https://"):
            return {"http": proxy, "https": proxy}
        if proxy.startswith("socks5://"):
            return {"http": proxy, "https": proxy}
        return {"http": f"http://{proxy}", "https": f"http://{proxy}"}


class RequestsRotating(RotatingProxySession, requests.Session):
    def __init__(self, proxies=None, has_retry=False, delay=1, clear_cookies=False):
        RotatingProxySession.__init__(self, proxies=proxies)
        requests.Session.__init__(self)
        self.clear_cookies = clear_cookies
        self.allow_redirects = True
        self.setup_session(has_retry, delay)

    def setup_session(self, has_retry, delay):
        if has_retry:
            retries = Retry(
                total=3,
                connect=3,
                status=3,
                status_forcelist=[500, 502, 503, 504, 429],
                backoff_factor=delay,
            )
            adapter = HTTPAdapter(max_retries=retries)
            self.mount("http://", adapter)
            self.mount("https://", adapter)

    def request(self, method, url, **kwargs):
        if self.clear_cookies:
            self.cookies.clear()

        if self.proxy_cycle:
            next_proxy = next(self.proxy_cycle)
            if next_proxy["http"] != "http://localhost":
                self.proxies = next_proxy
            else:
                self.proxies = {}
        return requests.Session.request(self, method, url, **kwargs)


class TLSRotating(RotatingProxySession, tls_client.Session):
    def __init__(self, proxies=None):
        RotatingProxySession.__init__(self, proxies=proxies)
        tls_client.Session.__init__(self, random_tls_extension_order=True)

    def execute_request(self, *args, **kwargs):
        if self.proxy_cycle:
            next_proxy = next(self.proxy_cycle)
            if next_proxy["http"] != "http://localhost":
                self.proxies = next_proxy
            else:
                self.proxies = {}
        response = tls_client.Session.execute_request(self, *args, **kwargs)
        response.ok = response.status_code in range(200, 400)
        return response


def create_session(
    *,
    proxies: dict | str | None = None,
    ca_cert: str | None = None,
    is_tls: bool = True,
    has_retry: bool = False,
    delay: int = 1,
    clear_cookies: bool = False,
) -> requests.Session:
    """
    Creates a requests session with optional tls, proxy, and retry settings.
    :return: A session object
    """
    if is_tls:
        session = TLSRotating(proxies=proxies)
    else:
        session = RequestsRotating(
            proxies=proxies,
            has_retry=has_retry,
            delay=delay,
            clear_cookies=clear_cookies,
        )

    if ca_cert:
        session.verify = ca_cert

    return session


def set_logger_level(verbose: int):
    """
    Adjusts the logger's level. This function allows the logging level to be changed at runtime.

    Parameters:
    - verbose: int {0, 1, 2} (default=2, all logs)
    """
    if verbose is None:
        return
    level_name = {2: "INFO", 1: "WARNING", 0: "ERROR"}.get(verbose, "INFO")
    level = getattr(logging, level_name.upper(), None)
    if level is not None:
        for logger_name in logging.root.manager.loggerDict:
            if logger_name.startswith("JobSpy:"):
                logging.getLogger(logger_name).setLevel(level)
    else:
        raise ValueError(f"Invalid log level: {level_name}")


def markdown_converter(description_html: str):
    if description_html is None:
        return None
    markdown = md(description_html)
    return markdown.strip()

def plain_converter(decription_html:str):
    from bs4 import BeautifulSoup
    if decription_html is None:
        return None
    soup = BeautifulSoup(decription_html, "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r'\s+',' ',text)
    return text.strip()


def extract_emails_from_text(text: str) -> list[str] | None:
    if not text:
        return None
    email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    return email_regex.findall(text)


def extract_company_from_description(description: str) -> str | None:
    if not description:
        return None
    # Look for patterns like "Company: XYZ" or "Client: XYZ" or "at XYZ, we are"
    patterns = [
        r"(?:company|employer|client|organization)\s*:\s*([A-Za-z0-9\s,&.\-]{3,40})",
        r"(?:about|at)\s+([A-Z][A-Za-z0-9\s,&.\-]{2,40}),\s+we\s+are",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            comp = match.group(1).strip()
            comp = re.split(r"[\n\.]", comp)[0].strip()
            if comp and len(comp) > 2:
                return comp
    return None


def get_enum_from_job_type(job_type_str: str) -> JobType | None:
    """
    Given a string, returns the corresponding JobType enum member if a match is found.
    """
    res = None
    for job_type in JobType:
        if job_type_str in job_type.value:
            res = job_type
    return res


def currency_parser(cur_str):
    # Remove any non-numerical characters
    # except for ',' '.' or '-' (e.g. EUR)
    cur_str = re.sub("[^-0-9.,]", "", cur_str)
    # Remove any 000s separators (either , or .)
    cur_str = re.sub("[.,]", "", cur_str[:-3]) + cur_str[-3:]

    if "." in list(cur_str[-3:]):
        num = float(cur_str)
    elif "," in list(cur_str[-3:]):
        num = float(cur_str.replace(",", "."))
    else:
        num = float(cur_str)

    return np.round(num, 2)


def remove_attributes(tag):
    for attr in list(tag.attrs):
        del tag[attr]
    return tag


def extract_salary(
    salary_str,
    lower_limit=1000,
    upper_limit=700000,
    hourly_threshold=350,
    monthly_threshold=30000,
    enforce_annual_salary=False,
):
    """
    Extracts salary information from a string and returns the salary interval, min and max salary values, and currency.
    (TODO: Needs test cases as the regex is complicated and may not cover all edge cases)
    """
    if not salary_str:
        return None, None, None, None

    annual_max_salary = None
    # Support $, ₹, €, £, Rs., INR, AED, Dh
    min_max_pattern = r"([\$₹€£]|(?:Rs\.?|INR|AED|Dh))\s*(\d+(?:,\d+)?(?:\.\d+)?)([kK]?)\s*[-—–to\s]+\s*(?:\$|₹|€|£|Rs\.?|INR|AED|Dh)?\s*(\d+(?:,\d+)?(?:\.\d+)?)([kK]?)"

    def to_int(s):
        return int(float(s.replace(",", "")))

    def convert_hourly_to_annual(hourly_wage):
        return hourly_wage * 2080

    def convert_monthly_to_annual(monthly_wage):
        return monthly_wage * 12

    match = re.search(min_max_pattern, salary_str)

    if match:
        currency_symbol = match.group(1).lower()
        min_salary = to_int(match.group(2))
        max_salary = to_int(match.group(4))
        
        # Detect currency code
        currency_code = "USD"
        if "$" in currency_symbol:
            currency_code = "USD"
        elif "₹" in currency_symbol or "rs" in currency_symbol or "inr" in currency_symbol:
            currency_code = "INR"
        elif "€" in currency_symbol:
            currency_code = "EUR"
        elif "£" in currency_symbol:
            currency_code = "GBP"
        elif "aed" in currency_symbol or "dh" in currency_symbol:
            currency_code = "AED"

        # Handle 'k' suffix for min and max salaries independently
        if "k" in match.group(3).lower() or "k" in match.group(5).lower():
            min_salary *= 1000
            max_salary *= 1000

        # Convert to annual if less than the hourly threshold (only for USD)
        if currency_code == "USD" and min_salary < hourly_threshold:
            interval = CompensationInterval.HOURLY.value
            annual_min_salary = convert_hourly_to_annual(min_salary)
            if max_salary < hourly_threshold:
                annual_max_salary = convert_hourly_to_annual(max_salary)
        elif currency_code == "USD" and min_salary < monthly_threshold:
            interval = CompensationInterval.MONTHLY.value
            annual_min_salary = convert_monthly_to_annual(min_salary)
            if max_salary < monthly_threshold:
                annual_max_salary = convert_monthly_to_annual(max_salary)
        else:
            interval = CompensationInterval.YEARLY.value
            annual_min_salary = min_salary
            annual_max_salary = max_salary

        # For international currencies, validate or directly return yearly/monthly based on amount
        if currency_code != "USD":
            # Indian/Gulf salaries are usually annual or monthly.
            # If the numbers are small, e.g. < 100000, it's likely monthly (e.g. 5000 AED/month or 25000 INR/month)
            if min_salary < 100000:
                interval = CompensationInterval.MONTHLY.value
            else:
                interval = CompensationInterval.YEARLY.value

        if enforce_annual_salary:
            if interval == CompensationInterval.MONTHLY.value:
                min_salary = convert_monthly_to_annual(min_salary)
                max_salary = convert_monthly_to_annual(max_salary)
                interval = CompensationInterval.YEARLY.value
            elif interval == CompensationInterval.HOURLY.value:
                min_salary = convert_hourly_to_annual(min_salary)
                max_salary = convert_hourly_to_annual(max_salary)
                interval = CompensationInterval.YEARLY.value

        return interval, min_salary, max_salary, currency_code
    return None, None, None, None


def extract_job_type(description: str):
    if not description:
        return []

    keywords = {
        JobType.FULL_TIME: r"full\s?time",
        JobType.PART_TIME: r"part\s?time",
        JobType.INTERNSHIP: r"internship",
        JobType.CONTRACT: r"contract",
    }

    listing_types = []
    for key, pattern in keywords.items():
        if re.search(pattern, description, re.IGNORECASE):
            listing_types.append(key)

    return listing_types if listing_types else None


def map_str_to_site(site_name: str) -> Site:
    return Site[site_name.upper()]


def get_enum_from_value(value_str):
    for job_type in JobType:
        if value_str in job_type.value:
            return job_type
    raise Exception(f"Invalid job type: {value_str}")


def convert_to_annual(job_data: dict):
    if job_data["interval"] == "hourly":
        job_data["min_amount"] *= 2080
        job_data["max_amount"] *= 2080
    if job_data["interval"] == "monthly":
        job_data["min_amount"] *= 12
        job_data["max_amount"] *= 12
    if job_data["interval"] == "weekly":
        job_data["min_amount"] *= 52
        job_data["max_amount"] *= 52
    if job_data["interval"] == "daily":
        job_data["min_amount"] *= 260
        job_data["max_amount"] *= 260
    job_data["interval"] = "yearly"


desired_order = [
    "id",
    "site",
    "job_url",
    "job_url_direct",
    "title",
    "company",
    "location",
    "date_posted",
    "posted_in_hours",
    "job_type",
    "salary_source",
    "interval",
    "min_amount",
    "max_amount",
    "currency",
    "is_remote",
    "job_level",
    "job_function",
    "listing_type",
    "emails",
    "description",
    "company_industry",
    "company_url",
    "company_logo",
    "company_url_direct",
    "company_addresses",
    "company_num_employees",
    "company_revenue",
    "company_description",
    # naukri-specific fields
    "skills",
    "experience_range",
    "company_rating",
    "company_reviews_count",
    "vacancy_count",
    "work_from_home_type",
]


class ScraplingResponse:
    def __init__(self, scrapling_res):
        self.status_code = scrapling_res.status
        self.content = scrapling_res.body
        self.headers = scrapling_res.headers
        self.url = scrapling_res.url
        self._scrapling_res = scrapling_res

    @property
    def text(self):
        return self.content.decode('utf-8', errors='ignore')

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        import json
        return json.loads(self.text)

    def raise_for_status(self):
        if not self.ok:
            raise Exception(f"HTTP Error: {self.status_code}")


class ScraplingSession:
    def __init__(self, proxies=None, headers=None):
        self.proxies = proxies
        self.headers = headers or {}

    def get(self, url, params=None, headers=None, follow_redirects=True, timeout=None, **kwargs):
        from scrapling import Fetcher
        from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
        
        if "allow_redirects" in kwargs:
            follow_redirects = kwargs["allow_redirects"]
            
        if timeout is None and "timeout_seconds" in kwargs:
            timeout = kwargs["timeout_seconds"]
            
        req_headers = {**self.headers, **(headers or {})}
        proxy = self._format_proxy()
        
        if params:
            url_parts = list(urlparse(url))
            query = dict(parse_qsl(url_parts[4]))
            query.update(params)
            url_parts[4] = urlencode(query)
            url = urlunparse(url_parts)
            
        res = Fetcher.get(url, headers=req_headers, proxy=proxy, follow_redirects=follow_redirects, timeout=timeout)
        return ScraplingResponse(res)

    def post(self, url, data=None, json=None, headers=None, timeout=None, **kwargs):
        from scrapling import Fetcher
        if timeout is None and "timeout_seconds" in kwargs:
            timeout = kwargs["timeout_seconds"]
            
        req_headers = {**self.headers, **(headers or {})}
        proxy = self._format_proxy()
        
        res = Fetcher.post(url, headers=req_headers, proxy=proxy, data=data, json=json, timeout=timeout)
        return ScraplingResponse(res)

    def _format_proxy(self):
        if not self.proxies:
            return None
        if isinstance(self.proxies, dict):
            p = self.proxies.get("https") or self.proxies.get("http")
            return p
        return self.proxies


class ScraplingStealthSession:
    def __init__(self, proxies=None, headers=None, capture_xhr=None):
        self.proxies = proxies
        self.headers = headers or {}
        self.capture_xhr = capture_xhr
        self._session = None

    def __enter__(self):
        from scrapling.fetchers import StealthySession
        proxy = self._format_proxy()
        self._session = StealthySession(
            proxy=proxy,
            extra_headers=self.headers,
            capture_xhr=self.capture_xhr,
            solve_cloudflare=True,
            headless=True
        )
        self._session.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            self._session.__exit__(exc_type, exc_val, exc_tb)

    def get(self, url, **kwargs):
        res = self._session.fetch(url)
        return ScraplingResponse(res)

    def fetch(self, url, **kwargs):
        res = self._session.fetch(url)
        return ScraplingResponse(res)

    def _format_proxy(self):
        if not self.proxies:
            return None
        if isinstance(self.proxies, dict):
            p = self.proxies.get("https") or self.proxies.get("http")
            return p
        return self.proxies

