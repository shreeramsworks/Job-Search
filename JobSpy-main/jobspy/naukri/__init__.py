from __future__ import annotations

import math
import random
import time
from datetime import datetime, date, timedelta
from typing import Optional

import regex as re
import requests

from jobspy.exception import NaukriException
from jobspy.naukri.constant import headers as naukri_headers
from jobspy.naukri.util import (
    is_job_remote,
    parse_job_type,
    parse_company_industry,
)
from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Country,
    Compensation,
    DescriptionFormat,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy.util import (
    extract_emails_from_text,
    currency_parser,
    markdown_converter,
    create_session,
    create_logger,
)

log = create_logger("Naukri")

class Naukri(Scraper):
    base_url = "https://www.naukri.com/jobapi/v3/search"
    delay = 3
    band_delay = 4
    jobs_per_page = 20  

    def __init__(
        self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None
    ):
        """
        Initializes NaukriScraper with the Naukri API URL
        """
        super().__init__(Site.NAUKRI, proxies=proxies, ca_cert=ca_cert)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=False,
            has_retry=True,
            delay=5,
            clear_cookies=True,
        )
        self.session.headers.update(naukri_headers)
        self.scraper_input = None
        self.country = "India"  #naukri is india-focused by default
        log.info("Naukri scraper initialized")

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes Naukri API for jobs with scraper_input criteria
        :param scraper_input:
        :return: job_response
        """
        self.scraper_input = scraper_input
        job_list: list[JobPost] = []
        seen_ids = set()
        start = scraper_input.offset or 0
        page = (start // self.jobs_per_page) + 1
        request_count = 0
        continue_search = (
            lambda: len(job_list) < scraper_input.results_wanted and page <= 50  # Arbitrary limit
        )

        import json
        from jobspy.util import ScraplingStealthSession

        # Construct SEO URL key
        keyword_part = scraper_input.search_term.lower().replace(' ', '-')
        location_part = scraper_input.location.lower().replace(' ', '-').replace(',', '') if scraper_input.location else ""
        if location_part:
            url_key = f"{keyword_part}-jobs-in-{location_part}"
        else:
            url_key = f"{keyword_part}-jobs"

        xhr_pattern = r".*jobapi/v3/search.*"

        with ScraplingStealthSession(proxies=self.proxies, capture_xhr=xhr_pattern) as session:
            while continue_search():
                request_count += 1
                log.info(
                    f"Scraping page {request_count} / {math.ceil(scraper_input.results_wanted / self.jobs_per_page)} "
                    f"for search term: {scraper_input.search_term}"
                )
                
                if page == 1:
                    url = f"https://www.naukri.com/{url_key}"
                else:
                    url = f"https://www.naukri.com/{url_key}-{page}"

                try:
                    res = session.get(url)
                    if res.status_code not in range(200, 400):
                        log.error(f"Naukri search page response status code {res.status_code}")
                        break

                    # Look at captured XHR responses
                    xhr_res = None
                    for captured in res._scrapling_res.captured_xhr:
                        if "jobapi/v3/search" in captured.url:
                            xhr_res = captured
                            break

                    if not xhr_res:
                        log.warning("No captured jobapi XHR found for Naukri search page")
                        break

                    data = json.loads(xhr_res.body.decode('utf-8', errors='ignore'))
                    job_details = data.get("jobDetails", [])
                    log.info(f"Received {len(job_details)} job entries from captured API")
                    if not job_details:
                        log.warning("No job details found in captured API response")
                        break
                except Exception as e:
                    log.error(f"Naukri scraping failed: {e}")
                    break

                for job in job_details:
                    job_id = job.get("jobId")
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    log.debug(f"Processing job ID: {job_id}")

                    try:
                        fetch_desc = scraper_input.linkedin_fetch_description
                        job_post = self._process_job(job, job_id, fetch_desc)
                        if job_post:
                            job_list.append(job_post)
                            log.info(f"Added job: {job_post.title} (ID: {job_id})")
                        if not continue_search():
                            break
                    except Exception as e:
                        log.error(f"Error processing job ID {job_id}: {str(e)}")
                        raise NaukriException(str(e))

                if continue_search():
                    time.sleep(random.uniform(self.delay, self.delay + self.band_delay))
                    page += 1

        job_list = job_list[:scraper_input.results_wanted]
        log.info(f"Scraping completed. Total jobs collected: {len(job_list)}")
        return JobResponse(jobs=job_list)

    def _process_job(
        self, job: dict, job_id: str, full_descr: bool
    ) -> Optional[JobPost]:
        """
        Processes a single job from API response into a JobPost object
        """
        title = job.get("title", "N/A")
        company = job.get("companyName", "N/A")
        company_url = f"https://www.naukri.com/{job.get('staticUrl', '')}" if job.get("staticUrl") else None

        location = self._get_location(job.get("placeholders", []))
        compensation = self._get_compensation(job.get("placeholders", []))
        date_posted = self._parse_date(job.get("footerPlaceholderLabel"), job.get("createdDate"))

        job_url = f"https://www.naukri.com{job.get('jdURL', f'/job/{job_id}')}"
        raw_description = job.get("jobDescription")

        job_type = parse_job_type(raw_description) if raw_description else None
        company_industry = parse_company_industry(raw_description) if raw_description else None

        description = raw_description
        if description and self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
            description = markdown_converter(description)

        is_remote = is_job_remote(title, description or "", location)
        company_logo = job.get("logoPathV3") or job.get("logoPath")

        # Naukri-specific fields
        skills = job.get("tagsAndSkills", "").split(",") if job.get("tagsAndSkills") else None
        experience_range = job.get("experienceText")
        ambition_box = job.get("ambitionBoxData", {})
        company_rating = float(ambition_box.get("AggregateRating")) if ambition_box.get("AggregateRating") else None
        company_reviews_count = ambition_box.get("ReviewsCount")
        vacancy_count = job.get("vacancy")
        work_from_home_type = self._infer_work_from_home_type(job.get("placeholders", []), title, description or "")

        job_post = JobPost(
            id=f"nk-{job_id}",
            title=title,
            company_name=company,
            company_url=company_url,
            location=location,
            is_remote=is_remote,
            date_posted=date_posted,
            job_url=job_url,
            compensation=compensation,
            job_type=job_type,
            company_industry=company_industry,
            description=description,
            emails=extract_emails_from_text(description or ""),
            company_logo=company_logo,
            skills=skills,
            experience_range=experience_range,
            company_rating=company_rating,
            company_reviews_count=company_reviews_count,
            vacancy_count=vacancy_count,
            work_from_home_type=work_from_home_type,
        )
        log.debug(f"Processed job: {title} at {company}")
        return job_post

    def _get_location(self, placeholders: list[dict]) -> Location:
        """
        Extracts location data from placeholders
        """
        location = Location(country=Country.INDIA)
        for placeholder in placeholders:
            if placeholder.get("type") == "location":
                location_str = placeholder.get("label", "")
                parts = location_str.split(", ")
                city = parts[0] if parts else None
                state = parts[1] if len(parts) > 1 else None
                location = Location(city=city, state=state, country=Country.INDIA)
                log.debug(f"Parsed location: {location.display_location()}")
                break
        return location

    def _get_compensation(self, placeholders: list[dict]) -> Optional[Compensation]:
        """
        Extracts compensation data from placeholders, handling Indian salary formats (Lakhs, Crores)
        """
        for placeholder in placeholders:
            if placeholder.get("type") == "salary":
                salary_text = placeholder.get("label", "").strip()
                if salary_text == "Not disclosed":
                    log.debug("Salary not disclosed")
                    return None

                # Handle Indian salary formats (e.g., "12-16 Lacs P.A.", "1-5 Cr")
                salary_match = re.match(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(Lacs|Lakh|Cr)?\s*(P\.A\.)?", salary_text, re.IGNORECASE)
                if salary_match:
                    min_salary, max_salary, unit, _ = salary_match.groups()
                    min_salary, max_salary = float(min_salary.replace(",", "")), float(max_salary.replace(",", ""))
                    currency = "INR"

                    # Convert to base units if unit is specified or if they look like lakhs (small values)
                    if unit and unit.lower() in ("lacs", "lakh"):
                        min_salary *= 100000
                        max_salary *= 100000
                    elif unit and unit.lower() == "cr":
                        min_salary *= 10000000
                        max_salary *= 10000000
                    elif min_salary < 100:  # Fallback: if value is small, assume Lacs
                        min_salary *= 100000
                        max_salary *= 100000

                    log.debug(f"Parsed salary: {min_salary} - {max_salary} INR")
                    return Compensation(
                        min_amount=int(min_salary),
                        max_amount=int(max_salary),
                        currency=currency,
                    )
                else:
                    # Clean and try to find a number range
                    salary_clean = salary_text.replace(",", "").replace("₹", "").strip()
                    generic_match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", salary_clean)
                    if generic_match:
                        min_val = float(generic_match.group(1))
                        max_val = float(generic_match.group(2))
                        if min_val < 100 and ("lac" in salary_text.lower() or "lakh" in salary_text.lower()):
                            min_val *= 100000
                            max_val *= 100000
                        elif min_val < 50 and "cr" in salary_text.lower():
                            min_val *= 10000000
                            max_val *= 10000000
                        return Compensation(
                            min_amount=int(min_val),
                            max_amount=int(max_val),
                            currency="INR",
                        )
                    log.debug(f"Could not parse salary: {salary_text}")
                    return None
        return None

    def _parse_date(self, label: str, created_date: int) -> Optional[date]:
        """
        Parses date from footerPlaceholderLabel or createdDate, returning a date object
        """
        today = datetime.now()
        if not label:
            if created_date:
                return datetime.fromtimestamp(created_date / 1000).date()  # Convert to date
            return None
        label = label.lower()
        if "today" in label or "just now" in label or "few hours" in label:
            log.debug("Date parsed as today")
            return today.date()
        elif "ago" in label:
            match = re.search(r"(\d+)\s*day", label)
            if match:
                days = int(match.group(1))
                parsed_date = (today - timedelta(days = days)).date()
                log.debug(f"Date parsed: {days} days ago -> {parsed_date}")
                return parsed_date
        elif created_date:
            parsed_date = datetime.fromtimestamp(created_date / 1000).date()
            log.debug(f"Date parsed from timestamp: {parsed_date}")
            return parsed_date
        log.debug("No date parsed")
        return None

    def _infer_work_from_home_type(self, placeholders: list[dict], title: str, description: str) -> Optional[str]:
        """
        Infers work-from-home type from job data (e.g., 'Hybrid', 'Remote', 'Work from office')
        """
        location_str = next((p["label"] for p in placeholders if p["type"] == "location"), "").lower()
        if "hybrid" in location_str or "hybrid" in title.lower() or "hybrid" in description.lower():
            return "Hybrid"
        elif "remote" in location_str or "remote" in title.lower() or "remote" in description.lower():
            return "Remote"
        elif "work from office" in description.lower() or not ("remote" in description.lower() or "hybrid" in description.lower()):
            return "Work from office"
        return None