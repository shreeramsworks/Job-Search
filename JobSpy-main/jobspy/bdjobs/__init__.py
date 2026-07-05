# __init__.py
from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

from jobspy.exception import BDJobsException
from jobspy.model import (
    JobPost,
    Location,
    JobResponse,
    Country,
    Scraper,
    ScraperInput,
    Site,
    DescriptionFormat,
    JobType,
)
from jobspy.bdjobs.util import (
    parse_location,
    parse_date,
)
from jobspy.util import (
    create_logger,
    markdown_converter,
)

log = create_logger("BDJobs")

class BDJobs(Scraper):
    base_url = "https://jobs.bdjobs.com"
    list_url = "https://gateway.bdjobs.com/recruitment-account-test/api/JobSearch/GetJobSearch"
    details_url = "https://gateway.bdjobs.com/ActtivejobsTest/api/JobSubsystem/jobDetails"
    delay = 1
    band_delay = 2

    def __init__(
        self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None
    ):
        super().__init__(Site.BDJOBS, proxies=proxies, ca_cert=ca_cert)
        from jobspy.util import ScraplingSession
        self.session = ScraplingSession(
            proxies=self.proxies
        )
        self.scraper_input = None
        self.country = "bangladesh"

    def map_job_type(self, job_nature_str: str) -> list[JobType] | None:
        if not job_nature_str:
            return None
        val = job_nature_str.lower().replace(" ", "").replace("-", "")
        if "fulltime" in val:
            return [JobType.FULL_TIME]
        elif "parttime" in val:
            return [JobType.PART_TIME]
        elif "contract" in val:
            return [JobType.CONTRACT]
        elif "internship" in val:
            return [JobType.INTERNSHIP]
        elif "temporary" in val:
            return [JobType.TEMPORARY]
        return None

    def strip_html(self, html_text: str) -> str:
        if not html_text:
            return ""
        soup = BeautifulSoup(html_text, 'html.parser')
        return soup.get_text(separator='\n', strip=True)

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        self.scraper_input = scraper_input
        job_list: list[JobPost] = []
        seen_ids = set()
        page = 1
        request_count = 0

        # We request 50 results per page (max supported)
        params = {
            "isPro": "1",
            "rpp": "50",
        }
        if scraper_input.search_term:
            params["keyword"] = scraper_input.search_term

        continue_search = lambda: len(job_list) < scraper_input.results_wanted

        while continue_search():
            request_count += 1
            log.info(f"Searching BDJobs page: {page}")

            try:
                params["pg"] = str(page)
                response = self.session.get(
                    self.list_url,
                    params=params,
                    timeout=getattr(scraper_input, "request_timeout", 60),
                )

                if response.status_code != 200:
                    log.error(f"BDJobs list API status code {response.status_code}")
                    break

                data = response.json()
                if not data or data.get("statuscode") != "1":
                    log.warning("BDJobs list API returned non-success code or empty response")
                    break

                job_data_list = data.get("data", [])
                # Also include premium jobs if they exist
                premium_jobs = data.get("premiumData", [])
                all_jobs = job_data_list + premium_jobs

                if not all_jobs:
                    log.info("No more job listings found")
                    break

                log.info(f"Found {len(all_jobs)} jobs in list page {page}")

                for job in all_jobs:
                    job_id = job.get("Jobid")
                    if not job_id or job_id in seen_ids:
                        continue
                        
                    # Fetch details for the job
                    try:
                        detail_url = f"{self.details_url}?jobId={job_id}"
                        detail_resp = self.session.get(
                            detail_url,
                            timeout=getattr(scraper_input, "request_timeout", 60),
                        )
                        if detail_resp.status_code != 200:
                            log.error(f"Failed to fetch details for job {job_id}")
                            continue

                        detail_data_outer = detail_resp.json()
                        if not detail_data_outer or not detail_data_outer.get("data"):
                            log.warning(f"No detail data found for job {job_id}")
                            continue

                        detail = detail_data_outer["data"][0]

                        # Parse fields
                        location = parse_location(detail.get("JobLocation"), self.country)
                        date_posted = parse_date(detail.get("PostedOn"))

                        min_salary = detail.get("JobSalaryMinSalary")
                        max_salary = detail.get("JobSalaryMaxSalary")
                        min_amount = int(min_salary) if min_salary else None
                        max_amount = int(max_salary) if max_salary else None

                        desc_parts = []
                        if detail.get("JobDescription"):
                            desc_parts.append(self.strip_html(detail.get("JobDescription")))
                        if detail.get("EducationRequirements"):
                            desc_parts.append("Education Requirements:\n" + self.strip_html(detail.get("EducationRequirements")))
                        if detail.get("AdditionJobRequirements"):
                            desc_parts.append("Additional Requirements:\n" + self.strip_html(detail.get("AdditionJobRequirements")))
                        description = "\n\n".join(desc_parts)

                        if description and scraper_input.description_format == DescriptionFormat.MARKDOWN:
                            description = markdown_converter(description)

                        job_type = self.map_job_type(detail.get("JobNature"))

                        job_post = JobPost(
                            id=str(job_id),
                            title=detail.get("JobTitle"),
                            company_name=detail.get("CompnayName"),
                            location=location,
                            date_posted=date_posted,
                            job_url=f"https://jobs.bdjobs.com/jobdetail.asp?id={job_id}",
                            is_remote=False,
                            site=self.site,
                            description=description,
                            job_type=job_type,
                            min_amount=min_amount,
                            max_amount=max_amount,
                            currency="BDT"
                        )
                        
                        seen_ids.add(job_id)
                        job_list.append(job_post)

                        if not continue_search():
                            break
                    except Exception as e:
                        log.error(f"Error processing job {job_id}: {str(e)}")

                    # Small delay between detail requests
                    time.sleep(random.uniform(0.1, 0.3))

                page += 1
                # Delay between page list requests
                time.sleep(random.uniform(self.delay, self.delay + self.band_delay))

            except Exception as e:
                log.error(f"Error during scraping: {str(e)}")
                break

        job_list = job_list[: scraper_input.results_wanted]
        return JobResponse(jobs=job_list)
