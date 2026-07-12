from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

import pandas as pd

from jobspy.bayt import BaytScraper
from jobspy.bdjobs import BDJobs
from jobspy.glassdoor import Glassdoor
from jobspy.google import Google
from jobspy.indeed import Indeed
from jobspy.linkedin import LinkedIn
from jobspy.naukri import Naukri
from jobspy.model import JobType, Location, JobResponse, Country
from jobspy.model import SalarySource, ScraperInput, Site
from jobspy.util import (
    set_logger_level,
    extract_salary,
    create_logger,
    get_enum_from_value,
    map_str_to_site,
    convert_to_annual,
    desired_order,
    extract_company_from_description,
)
from jobspy.ziprecruiter import ZipRecruiter


# Update the SCRAPER_MAPPING dictionary in the scrape_jobs function

def scrape_jobs(
    site_name: str | list[str] | Site | list[Site] | None = None,
    search_term: str | None = None,
    google_search_term: str | None = None,
    location: str | None = None,
    distance: int | None = 50,
    is_remote: bool = False,
    job_type: str | None = None,
    easy_apply: bool | None = None,
    results_wanted: int = 15,
    country_indeed: str | list[str] | None = "usa",
    proxies: list[str] | str | None = None,
    ca_cert: str | None = None,
    description_format: str = "markdown",
    linkedin_fetch_description: bool | None = True,
    linkedin_company_ids: list[int] | None = None,
    offset: int | None = 0,
    hours_old: int = None,
    enforce_annual_salary: bool = False,
    verbose: int = 0,
    user_agent: str = None,
    concurrency_mode: str = "controlled",
    max_workers: int | None = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Scrapes job data from job boards concurrently
    :return: Pandas DataFrame containing job data
    """
    SCRAPER_MAPPING = {
        Site.LINKEDIN: LinkedIn,
        Site.INDEED: Indeed,
        Site.ZIP_RECRUITER: ZipRecruiter,
        Site.GLASSDOOR: Glassdoor,
        Site.GOOGLE: Google,
        Site.BAYT: BaytScraper,
        Site.NAUKRI: Naukri,
        Site.BDJOBS: BDJobs,  # Add BDJobs to the scraper mapping
    }
    set_logger_level(verbose)
    import sys
    import asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    job_type = get_enum_from_value(job_type) if job_type else None

    def get_site_type():
        site_types = list(Site)
        if isinstance(site_name, str):
            site_types = [map_str_to_site(site_name)]
        elif isinstance(site_name, Site):
            site_types = [site_name]
        elif isinstance(site_name, list):
            site_types = [
                map_str_to_site(site) if isinstance(site, str) else site
                for site in site_name
            ]
        return site_types

    # Parse countries from country_indeed
    countries = []
    if country_indeed:
        if isinstance(country_indeed, list):
            countries = [Country.from_string(c) if isinstance(c, str) else c for c in country_indeed]
        elif isinstance(country_indeed, str):
            countries = [Country.from_string(c.strip()) for c in country_indeed.split(",") if c.strip()]
        else:
            countries = [Country.from_string(str(country_indeed))]

    # Dynamic location parsing: if indeed country is empty but location is provided, detect country
    if not countries and location:
        loc_lower = location.lower()
        detected_country = None
        for country in Country:
            if country in (Country.US_CANADA, Country.WORLDWIDE):
                continue
            names = country.value[0].split(",")
            for name in names:
                if name in loc_lower:
                    detected_country = country
                    break
            if detected_country:
                break
        
        if not detected_country:
            india_cities = ["bangalore", "bengaluru", "mumbai", "pune", "delhi", "noida", "gurgaon", "hyderabad", "chennai", "kolkata"]
            germany_cities = ["berlin", "munich", "frankfurt", "hamburg", "cologne"]
            uk_cities = ["london", "manchester", "birmingham", "leeds", "glasgow"]
            canada_cities = ["toronto", "vancouver", "montreal", "ottawa", "calgary"]
            
            for city in india_cities:
                if city in loc_lower:
                    detected_country = Country.INDIA
                    break
            for city in germany_cities:
                if city in loc_lower:
                    detected_country = Country.GERMANY
                    break
            for city in uk_cities:
                if city in loc_lower:
                    detected_country = Country.UK
                    break
            for city in canada_cities:
                if city in loc_lower:
                    detected_country = Country.CANADA
                    break
        if detected_country:
            countries = [detected_country]

    if not countries:
        # Default major countries to search on if no country or location is specified
        countries = [
            Country.USA,
            Country.INDIA,
            Country.CANADA,
            Country.UK,
            Country.AUSTRALIA,
            Country.BANGLADESH
        ]

    scraper_input = ScraperInput(
        site_type=get_site_type(),
        country=countries[0],
        search_term=search_term,
        google_search_term=google_search_term,
        location=location,
        distance=distance,
        is_remote=is_remote,
        job_type=job_type,
        easy_apply=easy_apply,
        description_format=description_format,
        linkedin_fetch_description=linkedin_fetch_description,
        results_wanted=results_wanted,
        linkedin_company_ids=linkedin_company_ids,
        offset=offset,
        hours_old=hours_old,
    )

    def is_site_supported_for_country(site: Site, country: Country) -> bool:
        if site == Site.NAUKRI:
            return country == Country.INDIA
        elif site == Site.BDJOBS:
            return country == Country.BANGLADESH
        elif site == Site.ZIP_RECRUITER:
            return country in (Country.USA, Country.CANADA, Country.US_CANADA)
        elif site == Site.GLASSDOOR:
            return len(country.value) == 3
        return True

    tasks = []
    for site in scraper_input.site_type:
        if site in (Site.INDEED, Site.GLASSDOOR):
            for country in countries:
                if is_site_supported_for_country(site, country):
                    tasks.append((site, country))
        else:
            supported_country = None
            for country in countries:
                if is_site_supported_for_country(site, country):
                    supported_country = country
                    break
            
            if not supported_country:
                # Soft fallback for platform-specific subdomains instead of skipping
                if site == Site.NAUKRI:
                    supported_country = Country.INDIA
                elif site == Site.BDJOBS:
                    supported_country = Country.BANGLADESH
                elif site == Site.ZIP_RECRUITER:
                    supported_country = Country.USA
                else:
                    supported_country = countries[0]
                
            tasks.append((site, supported_country))


    def scrape_site(site: Site, country: Country) -> Tuple[str, JobResponse]:
        scraper_class = SCRAPER_MAPPING[site]
        scraper = scraper_class(proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        
        site_input = scraper_input.copy()
        site_input.country = country
        
        scraped_data: JobResponse = scraper.scrape(site_input)
        cap_name = site.value.capitalize()
        site_name = "ZipRecruiter" if cap_name == "Zip_recruiter" else cap_name
        site_name = "LinkedIn" if cap_name == "Linkedin" else cap_name
        create_logger(site_name).info(f"finished scraping for {country.name}")
        return site.value, scraped_data

    site_to_jobs_dict = {}

    def worker(site: Site, country: Country):
        try:
            site_val, scraped_info = scrape_site(site, country)
            return site_val, scraped_info
        except Exception as e:
            cap_name = site.value.capitalize()
            site_name = "ZipRecruiter" if cap_name == "Zip_recruiter" else cap_name
            site_name = "LinkedIn" if cap_name == "Linkedin" else cap_name
            create_logger(site_name).error(
                f"Error scraping {site_name} for {country.name}: {e}"
            )
            return site.value, JobResponse(jobs=[])

    if concurrency_mode == "series":
        for site, country in tasks:
            site_value, scraped_data = worker(site, country)
            if site_value not in site_to_jobs_dict:
                site_to_jobs_dict[site_value] = JobResponse(jobs=[])
            site_to_jobs_dict[site_value].jobs.extend(scraped_data.jobs)
    else:
        workers = max_workers
        if concurrency_mode == "controlled" and not workers:
            workers = 3
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_task = {
                executor.submit(worker, site, country): (site, country)
                for site, country in tasks
            }

            for future in as_completed(future_to_task):
                site_value, scraped_data = future.result()
                if site_value not in site_to_jobs_dict:
                    site_to_jobs_dict[site_value] = JobResponse(jobs=[])
                site_to_jobs_dict[site_value].jobs.extend(scraped_data.jobs)

    jobs_dfs: list[pd.DataFrame] = []

    for site, job_response in site_to_jobs_dict.items():
        for job in job_response.jobs:
            job_data = job.dict()
            job_url = job_data["job_url"]
            job_data["site"] = site
            job_data["company"] = job_data["company_name"]
            job_data["job_type"] = (
                ", ".join(job_type.value[0] for job_type in job_data["job_type"])
                if job_data["job_type"]
                else None
            )
            job_data["emails"] = (
                ", ".join(job_data["emails"]) if job_data["emails"] else None
            )
            if job_data["location"]:
                job_data["location"] = Location(
                    **job_data["location"]
                ).display_location()

            # Handle compensation
            compensation_obj = job_data.get("compensation")
            if compensation_obj and isinstance(compensation_obj, dict):
                job_data["interval"] = (
                    compensation_obj.get("interval").value
                    if compensation_obj.get("interval")
                    else None
                )
                job_data["min_amount"] = compensation_obj.get("min_amount")
                job_data["max_amount"] = compensation_obj.get("max_amount")
                job_data["currency"] = compensation_obj.get("currency", "USD")
                job_data["salary_source"] = SalarySource.DIRECT_DATA.value
                if enforce_annual_salary and (
                    job_data["interval"]
                    and job_data["interval"] != "yearly"
                    and job_data["min_amount"]
                    and job_data["max_amount"]
                ):
                    convert_to_annual(job_data)
            else:
                (
                    job_data["interval"],
                    job_data["min_amount"],
                    job_data["max_amount"],
                    job_data["currency"],
                ) = extract_salary(
                    job_data["description"],
                    enforce_annual_salary=enforce_annual_salary,
                )
                job_data["salary_source"] = SalarySource.DESCRIPTION.value if job_data["min_amount"] else None

            job_data["salary_source"] = (
                job_data["salary_source"]
                if "min_amount" in job_data and job_data["min_amount"]
                else None
            )

            # naukri-specific fields
            job_data["skills"] = (
                ", ".join(job_data["skills"]) if job_data["skills"] else None
            )
            job_data["experience_range"] = job_data.get("experience_range")
            job_data["company_rating"] = job_data.get("company_rating")
            job_data["company_reviews_count"] = job_data.get("company_reviews_count")
            job_data["vacancy_count"] = job_data.get("vacancy_count")
            job_data["work_from_home_type"] = job_data.get("work_from_home_type")

            # Fallback for company name if missing or N/A
            comp_name = job_data.get("company_name")
            if not comp_name or comp_name == "N/A":
                extracted_comp = extract_company_from_description(job_data.get("description"))
                if extracted_comp:
                    job_data["company"] = extracted_comp
                    job_data["company_name"] = extracted_comp

            # Calculate posted_in_hours
            if job_data.get("date_posted"):
                try:
                    post_date = pd.to_datetime(job_data["date_posted"])
                    now = pd.Timestamp.now()
                    diff = now.normalize() - post_date.normalize()
                    job_data["posted_in_hours"] = int(diff.total_seconds() / 3600)
                except:
                    job_data["posted_in_hours"] = None
            else:
                job_data["posted_in_hours"] = None

            job_df = pd.DataFrame([job_data])
            jobs_dfs.append(job_df)

    if jobs_dfs:
        # Step 1: Filter out all-NA columns from each DataFrame before concatenation
        filtered_dfs = [df.dropna(axis=1, how="all") for df in jobs_dfs]

        # Step 2: Concatenate the filtered DataFrames
        jobs_df = pd.concat(filtered_dfs, ignore_index=True)

        # Step 3: Ensure all desired columns are present, adding missing ones as empty
        for column in desired_order:
            if column not in jobs_df.columns:
                jobs_df[column] = None  # Add missing columns as empty

        # Reorder the DataFrame according to the desired order
        jobs_df = jobs_df[desired_order]

        # Post-scraping filter for hours_old
        if hours_old is not None:
            temp_dates = pd.to_datetime(jobs_df["date_posted"], errors='coerce')
            cutoff_date = pd.Timestamp.now().normalize() - pd.Timedelta(hours=hours_old)
            jobs_df = jobs_df[temp_dates >= cutoff_date]

        # Step 4: Sort the DataFrame as required (globally by date_posted descending, newest first)
        sort_dates = pd.to_datetime(jobs_df["date_posted"], errors='coerce')
        jobs_df["_sort_date"] = sort_dates
        jobs_df = jobs_df.sort_values(
            by=["_sort_date", "site"], ascending=[False, True]
        ).drop(columns=["_sort_date"]).reset_index(drop=True)
        return jobs_df
    else:
        return pd.DataFrame()


# Add BDJobs to __all__
__all__ = [
    "BDJobs",
]