from __future__ import annotations

import math
import re
import json
import tempfile
import shutil
import urllib.parse
from typing import Tuple
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from jobspy.google.constant import headers_jobs, headers_initial, async_param
from jobspy.model import (
    Scraper,
    ScraperInput,
    Site,
    JobPost,
    JobResponse,
    Location,
    JobType,
)
from jobspy.util import extract_emails_from_text, extract_job_type
from jobspy.google.util import log

def find_all_lists_in_string(s):
    decoder = json.JSONDecoder()
    pos = 0
    matches = []
    while True:
        pos = s.find('[', pos)
        if pos == -1:
            break
        try:
            val, end = decoder.raw_decode(s, pos)
            matches.append(val)
            pos = end
        except json.JSONDecodeError:
            pos += 1
    return matches

def clean_html(html_text):
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, 'html.parser')
    return soup.get_text(separator='\n', strip=True)

def parse_post_date(metadata_text):
    if not metadata_text:
        return None
    match = re.search(r"(\d+)\s+(day|hour|week|month)s?\s+ago", metadata_text, re.IGNORECASE)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        now = datetime.now()
        if "hour" in unit:
            return now.date()
        elif "day" in unit:
            return (now - timedelta(days=amount)).date()
        elif "week" in unit:
            return (now - timedelta(weeks=amount)).date()
        elif "month" in unit:
            return (now - timedelta(days=amount*30)).date()
    return None

def clean_location_part(s):
    if not s:
        return None
    s = s.strip()
    s = re.sub(r'[^a-zA-Z0-9\s,]', '', s)
    return s.strip()

class Google(Scraper):
    def __init__(
        self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None
    ):
        """
        Initializes Google Scraper with the Google jobs search url
        """
        site = Site(Site.GOOGLE)
        super().__init__(site, proxies=proxies, ca_cert=ca_cert)

        self.country = None
        self.session = None
        self.scraper_input = None
        self.jobs_per_page = 10
        self.seen_urls = set()
        self.url = "https://www.google.com/search"
        self.jobs_url = "https://www.google.com/async/callback:550"

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes Google for jobs with scraper_input criteria.
        :param scraper_input: Information about job search criteria.
        :return: JobResponse containing a list of jobs.
        """
        self.scraper_input = scraper_input
        self.scraper_input.results_wanted = min(900, scraper_input.results_wanted)

        from jobspy.util import ScraplingSession
        self.session = ScraplingSession(
            proxies=self.proxies
        )
        forward_cursor, job_list = self._get_initial_cursor_and_jobs()
        if forward_cursor is None:
            log.warning(
                "initial cursor not found, try changing your query or there was at most 10 results"
            )
            return JobResponse(jobs=job_list)

        page = 1

        while (
            len(self.seen_urls) < scraper_input.results_wanted + scraper_input.offset
            and forward_cursor
        ):
            log.info(
                f"search page: {page} / {math.ceil(scraper_input.results_wanted / self.jobs_per_page)}"
            )
            try:
                jobs, forward_cursor = self._get_jobs_next_page(forward_cursor)
            except Exception as e:
                log.error(f"failed to get jobs on page: {page}, {e}")
                break
            if not jobs:
                log.info(f"found no jobs on page: {page}")
                break
            job_list += jobs
            page += 1
        return JobResponse(
            jobs=job_list[
                scraper_input.offset : scraper_input.offset
                + scraper_input.results_wanted
            ]
        )

    def _get_initial_cursor_and_jobs(self) -> Tuple[str, list[JobPost]]:
        """Gets initial cursor and jobs to paginate through job listings"""
        query = f"{self.scraper_input.search_term} jobs"

        def get_time_range(hours_old):
            if hours_old <= 24:
                return "since yesterday"
            elif hours_old <= 72:
                return "in the last 3 days"
            elif hours_old <= 168:
                return "in the last week"
            else:
                return "in the last month"

        job_type_mapping = {
            JobType.FULL_TIME: "Full time",
            JobType.PART_TIME: "Part time",
            JobType.INTERNSHIP: "Internship",
            JobType.CONTRACT: "Contract",
        }

        if self.scraper_input.job_type in job_type_mapping:
            query += f" {job_type_mapping[self.scraper_input.job_type]}"

        if self.scraper_input.location:
            query += f" near {self.scraper_input.location}"

        if self.scraper_input.hours_old:
            time_filter = get_time_range(self.scraper_input.hours_old)
            query += f" {time_filter}"

        if self.scraper_input.is_remote:
            query += " remote"

        if self.scraper_input.google_search_term:
            query = self.scraper_input.google_search_term

        params = {"q": query, "udm": "8"}
        full_url = f"{self.url}?{urllib.parse.urlencode(params)}"
        log.info(f"Fetching initial Google search via StealthyFetcher: {full_url}")
        
        from scrapling import StealthyFetcher
        temp_dir = tempfile.mkdtemp(prefix="playwright_google_")
        try:
            res = StealthyFetcher.fetch(full_url, solve_cloudflare=False, user_data_dir=temp_dir)
            response_text = res.body.decode('utf-8', errors='ignore')
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        pattern_fc = r'<div jsname="Yust4d"[^>]+data-async-fc="([^"]+)"'
        match_fc = re.search(pattern_fc, response_text)
        data_async_fc = match_fc.group(1) if match_fc else None
        
        # Find script tags containing "jobs" and having large length to speed up list extraction dramatically
        scripts_to_search = []
        for script in re.findall(r'<script[^>]*>(.*?)</script>', response_text, re.DOTALL):
            if "jobs" in script and len(script) > 5000:
                scripts_to_search.append(script)
        
        lists_initial = []
        for script in scripts_to_search:
            try:
                lists_initial.extend(find_all_lists_in_string(script))
            except Exception:
                pass
                
        # Fallback if no lists found in script tags
        if not lists_initial:
            lists_initial = find_all_lists_in_string(response_text)
            
        jobs = self._parse_html_and_lists_to_jobs(response_text, lists_initial)
        return data_async_fc, jobs

    def _get_jobs_next_page(self, forward_cursor: str) -> Tuple[list[JobPost], str]:
        params = {"fc": forward_cursor, "fcv": "3", "async": async_param}
        response = self.session.get(self.jobs_url, headers=headers_jobs, params=params)
        return self._parse_jobs(response.text)

    def _parse_jobs(self, job_data: str) -> Tuple[list[JobPost], str]:
        """
        Parses jobs on a page with next page cursor
        """
        start_idx = job_data.find("[[[")
        if start_idx == -1:
            return [], None
        end_idx = job_data.rindex("]]]") + 3
        s = job_data[start_idx:end_idx]
        parsed = json.loads(s)[0]

        pattern_fc = r'data-async-fc="([^"]+)"'
        match_fc = re.search(pattern_fc, job_data)
        data_async_fc = match_fc.group(1) if match_fc else None
        
        lists_p2 = []
        for array in parsed:
            if len(array) >= 2:
                _, job_data_str = array
                if job_data_str:
                    try:
                        job_d = json.loads(job_data_str)
                        lists_p2.append(job_d)
                    except Exception:
                        pass
                        
        jobs_on_page = self._parse_html_and_lists_to_jobs(job_data, lists_p2)
        return jobs_on_page, data_async_fc

    def _parse_html_and_lists_to_jobs(self, html_content: str, lists: list) -> list[JobPost]:
        # 1. Parse HTML Cards
        cards_data = {}
        soup = BeautifulSoup(html_content, 'html.parser')
        
        titles = soup.find_all(class_="tNxQIb")
        
        for title_elem in titles:
            parent = title_elem.parent
            company_elem = parent.find(class_="a3jPc")
            loc_src_elem = parent.find(class_="FqK3wc")
            
            if not company_elem:
                ancestor = title_elem.find_parent(class_="GoEOPd")
                if ancestor:
                    company_elem = ancestor.find(class_="a3jPc")
                    loc_src_elem = ancestor.find(class_="FqK3wc")
                    
            title = title_elem.get_text(strip=True) if title_elem else ""
            company = company_elem.get_text(strip=True) if company_elem else ""
            
            loc_src = loc_src_elem.get_text(strip=True) if loc_src_elem else ""
            location = ""
            if loc_src:
                if "via " in loc_src:
                    location, _, _ = loc_src.partition("via ")
                    location = location.strip()
                else:
                    location = loc_src
                    
            metadata_elem = None
            if ancestor := title_elem.find_parent(class_="GoEOPd"):
                metadata_elem = ancestor.find_next_sibling(class_="ApHyTb")
                if not metadata_elem:
                    metadata_elem = ancestor.find(class_="ApHyTb")
            if not metadata_elem:
                metadata_elem = parent.find_next_sibling(class_="ApHyTb")
                
            metadata_text = metadata_elem.get_text(separator=" | ", strip=True) if metadata_elem else ""
            
            key = (title.lower(), company.lower())
            cards_data[key] = {
                "location": location,
                "metadata": metadata_text
            }
            
        # 2. Extract Jobs from list structures
        jobs_list = []
        for val in lists:
            item0 = None
            if isinstance(val, list):
                if len(val) == 3 and isinstance(val[0], list):
                    item0 = val[0]
                elif len(val) >= 10:
                    item0 = val
                    
            if item0 and len(item0) >= 10 and item0[2] == "jobs" and isinstance(item0[9], list):
                metadata = {}
                for kv in item0[9]:
                    if isinstance(kv, list) and len(kv) == 2:
                        metadata[kv[0]] = kv[1]
                if "cluster_id" in metadata:
                    jobs_list.append((item0, metadata))
                            
        def find_urls_in_nested_list(l):
            urls = []
            if isinstance(l, list):
                for sub in l:
                    urls.extend(find_urls_in_nested_list(sub))
            elif isinstance(l, dict):
                for k, v in l.items():
                    urls.extend(find_urls_in_nested_list(v))
            elif isinstance(l, str):
                if l.startswith("http://") or l.startswith("https://"):
                    urls.append(l)
            return urls

        parsed_posts = []
        for item, meta in jobs_list:
            title = item[5]
            company = meta.get("organization", "")
            
            # Find the best job url (avoid aggregators like LinkedIn if direct company careers page is available)
            all_urls = find_urls_in_nested_list(item)
            apply_urls = [u for u in all_urls if "google.com" not in u]
            job_url = item[1]
            if apply_urls:
                non_aggregator = [u for u in apply_urls if "linkedin.com" not in u and "indeed.com" not in u and "ziprecruiter.com" not in u]
                if non_aggregator:
                    job_url = non_aggregator[0]
                else:
                    job_url = apply_urls[0]
            
            cluster_id = meta.get("cluster_id", "")
            desc_html = item[4]
            description = clean_html(desc_html)
            
            if job_url in self.seen_urls:
                continue
            self.seen_urls.add(job_url)
            
            key = (title.lower(), company.lower())
            card_info = cards_data.get(key, {})
            location_str = card_info.get("location", "")
            metadata_str = card_info.get("metadata", "")
            
            city = state = country = None
            if location_str:
                parts = [clean_location_part(p) for p in location_str.split(",")]
                parts = [p for p in parts if p]
                if len(parts) >= 1:
                    city = parts[0]
                if len(parts) >= 2:
                    state = parts[1]
                if len(parts) >= 3:
                    country = parts[2]
                    
            date_posted = parse_post_date(metadata_str)
            
            # Extract compensation from metadata string if present
            from jobspy.util import extract_salary
            from jobspy.model import Compensation, CompensationInterval
            comp_interval, comp_min, comp_max, comp_curr = extract_salary(metadata_str)
            compensation = None
            if comp_min:
                try:
                    compensation = Compensation(
                        interval=CompensationInterval(comp_interval) if comp_interval else None,
                        min_amount=comp_min,
                        max_amount=comp_max,
                        currency=comp_curr
                    )
                except Exception:
                    pass
            
            job_post = JobPost(
                id=f"go-{cluster_id}",
                title=title,
                company_name=company,
                location=Location(city=city, state=state, country=country),
                job_url=job_url,
                date_posted=date_posted,
                is_remote="remote" in description.lower() or "wfh" in description.lower(),
                description=description,
                emails=extract_emails_from_text(description),
                job_type=extract_job_type(description),
                compensation=compensation
            )
            parsed_posts.append(job_post)
            
        return parsed_posts
