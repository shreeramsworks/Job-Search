from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

from jobspy.util import (
    extract_emails_from_text,
    markdown_converter,
    remove_attributes,
    create_logger,
)
from jobspy.model import (
    JobPost,
    Compensation,
    Location,
    JobResponse,
    Country,
    DescriptionFormat,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.ziprecruiter.util import get_job_type_enum

log = create_logger("ZipRecruiter")


class ZipRecruiter(Scraper):
    base_url = "https://www.ziprecruiter.com"

    def __init__(
        self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None
    ):
        """
        Initializes ZipRecruiterScraper with the ZipRecruiter job search url
        """
        super().__init__(Site.ZIP_RECRUITER, proxies=proxies)

        self.scraper_input = None
        self.delay = 5
        self.jobs_per_page = 20
        self.seen_urls = set()

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes ZipRecruiter for jobs with scraper_input criteria.
        :param scraper_input: Information about job search criteria.
        :return: JobResponse containing a list of jobs.
        """
        self.scraper_input = scraper_input
        job_list: list[JobPost] = []

        max_pages = math.ceil(scraper_input.results_wanted / self.jobs_per_page)
        for page in range(1, max_pages + 1):
            if len(job_list) >= scraper_input.results_wanted:
                break
            if page > 1:
                time.sleep(self.delay)
            log.info(f"search page: {page} / {max_pages}")
            jobs_on_page = self._find_jobs_in_page(scraper_input, page)
            if jobs_on_page:
                job_list.extend(jobs_on_page)
            else:
                break
        return JobResponse(jobs=job_list[: scraper_input.results_wanted])

    def _find_jobs_in_page(
        self, scraper_input: ScraperInput, page: int
    ) -> list[JobPost]:
        """
        Scrapes a page of ZipRecruiter for jobs with scraper_input criteria
        """
        from scrapling.fetchers import StealthySession
        
        search_term = scraper_input.search_term or ""
        location = scraper_input.location or ""
        
        # Build URL
        params = {
            "search": search_term,
            "location": location,
            "page": page
        }
        url = f"{self.base_url}/jobs-search?{urllib.parse.urlencode(params)}"
        
        jobs_list = []
        try:
            with StealthySession(solve_cloudflare=True, headless=True) as session:
                res = session.fetch(url)
                if res.status != 200:
                    log.error(f"ZipRecruiter search page status code {res.status}")
                    return []
                
                html = res.body.decode('utf-8', errors='ignore')
                soup = BeautifulSoup(html, "html.parser")
                
                # Find and parse JSON-LD
                ldjson_tags = soup.find_all("script", type="application/ld+json")
                item_list_tag = None
                for tag in ldjson_tags:
                    try:
                        data = json.loads(tag.string)
                        if data.get("@type") == "ItemList":
                            item_list_tag = data
                            break
                    except:
                        pass
                
                if not item_list_tag:
                    log.warning("No ItemList JSON-LD tag found on ZipRecruiter page")
                    return []
                    
                items = item_list_tag.get("itemListElement", [])
                
                # Process each job URL
                for item in items:
                    if len(jobs_list) >= scraper_input.results_wanted:
                        break
                    name = item.get("name")
                    job_url = item.get("url")
                    if not job_url:
                        continue
                    job_post = self._process_job_html(name, job_url, session)
                    if job_post:
                        jobs_list.append(job_post)
                        
        except Exception as e:
            log.error(f"ZipRecruiter page parsing error: {e}")
            
        return jobs_list

    def _process_job_html(self, name: str, job_url: str, session) -> JobPost | None:
        """
        Processes a single job and fetches its description & direct details.
        """
        
        if job_url in self.seen_urls:
            return None
        self.seen_urls.add(job_url)
        
        # 1. Parse details from URL as defaults
        parsed_url = urllib.parse.urlparse(job_url)
        path_parts = parsed_url.path.strip("/").split("/")
        
        company_name = None
        title = name
        city = None
        state = None
        country = Country.from_string("usa")
        job_id = None
        
        try:
            if len(path_parts) >= 2 and path_parts[0] == "c":
                company_name = urllib.parse.unquote(path_parts[1].replace("-", " "))
            if len(path_parts) >= 4 and path_parts[2] == "Job":
                title = urllib.parse.unquote(path_parts[3].replace("-", " "))
            
            for part in path_parts:
                if part.startswith("-in-"):
                    loc_part = part[4:]
                    if "," in loc_part:
                        city, state = [*map(lambda x: urllib.parse.unquote(x.strip()), loc_part.split(","))]
                    else:
                        city = urllib.parse.unquote(loc_part)
        except:
            pass
            
        try:
            q_params = urllib.parse.parse_qs(parsed_url.query)
            if "jid" in q_params:
                job_id = q_params["jid"][0]
        except:
            pass
            
        if not job_id:
            job_id = str(abs(hash(job_url)))

        description_full = ""
        job_url_direct = None
        date_posted = None
        comp_min = None
        comp_max = None
        comp_currency = "USD"
        comp_interval = None
        job_type = None
        company_logo = None
        
        try:
            res = session.fetch(job_url)
            if res.status == 200:
                html = res.body.decode('utf-8', errors='ignore')
                soup = BeautifulSoup(html, "html.parser")
                
                # Parse application/ld+json of type JobPosting
                ldjson_tags = soup.find_all("script", type="application/ld+json")
                job_posting_data = None
                for tag in ldjson_tags:
                    try:
                        data = json.loads(tag.string)
                        if data.get("@type") == "JobPosting":
                            job_posting_data = data
                            break
                    except:
                        pass
                
                if job_posting_data:
                    title = job_posting_data.get("title") or title
                    description_full = job_posting_data.get("description") or ""
                    
                    org = job_posting_data.get("hiringOrganization")
                    if isinstance(org, dict):
                        company_name = org.get("name") or company_name
                        company_logo = org.get("logo") or company_logo
                        
                    loc = job_posting_data.get("jobLocation")
                    if isinstance(loc, dict):
                        addr = loc.get("address")
                        if isinstance(addr, dict):
                            city = addr.get("addressLocality") or city
                            state = addr.get("addressRegion") or state
                            
                    dp_str = job_posting_data.get("datePosted")
                    if dp_str:
                        try:
                            date_posted = datetime.fromisoformat(dp_str.rstrip("Z")).date()
                        except:
                            pass
                            
                    et_str = job_posting_data.get("employmentType")
                    if et_str:
                        job_type = get_job_type_enum(et_str.lower().replace("_", ""))
                        
                    salary = job_posting_data.get("baseSalary")
                    if isinstance(salary, dict):
                        val = salary.get("value")
                        if isinstance(val, dict):
                            comp_min = val.get("minValue") or val.get("value")
                            comp_max = val.get("maxValue") or val.get("value")
                            comp_currency = val.get("currency") or "USD"
                            comp_interval = salary.get("unitText") or "yearly"
                            comp_interval = comp_interval.lower()
                            if comp_interval in ["annually", "annual", "year"]:
                                comp_interval = "yearly"
                            elif comp_interval == "hour":
                                comp_interval = "hourly"
                            elif comp_interval == "month":
                                comp_interval = "monthly"
                else:
                    job_descr_div = soup.find("div", class_="job_description")
                    company_descr_section = soup.find("section", class_="company_description")
                    job_description_clean = (
                        remove_attributes(job_descr_div).prettify(formatter="html")
                        if job_descr_div
                        else ""
                    )
                    company_description_clean = (
                        remove_attributes(company_descr_section).prettify(formatter="html")
                        if company_descr_section
                        else ""
                    )
                    description_full = job_description_clean + company_description_clean
                
                try:
                    script_tag = soup.find("script", type="application/json")
                    if script_tag:
                        job_json = json.loads(script_tag.string)
                        job_url_val = job_json["model"].get("saveJobURL", "")
                        m = re.search(r"job_url=(.+)", job_url_val)
                        if m:
                            job_url_direct = m.group(1)
                except:
                    pass
        except Exception as e:
            log.error(f"Error fetching job description for {job_url}: {e}")
            
        if description_full and self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
            description_full = markdown_converter(description_full)
            
        compensation = None
        if comp_min or comp_max:
            # Clean and convert to int
            try:
                comp_min = int(comp_min) if comp_min else None
                comp_max = int(comp_max) if comp_max else None
            except:
                pass
            compensation = Compensation(
                interval=comp_interval,
                min_amount=comp_min,
                max_amount=comp_max,
                currency=comp_currency
            )
            
        return JobPost(
            id=f"zr-{job_id}",
            title=title,
            company_name=company_name,
            location=Location(city=city, state=state, country=country),
            job_type=job_type,
            compensation=compensation,
            date_posted=date_posted,
            job_url=job_url,
            description=description_full,
            emails=extract_emails_from_text(description_full) if description_full else None,
            job_url_direct=job_url_direct,
            company_logo=company_logo,
            listing_type="direct" if job_url_direct else "board"
        )
