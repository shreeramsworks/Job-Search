"""
JobSpy API - Job Scraping Service
Vercel-ready deployment with comprehensive job scraping endpoints
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import datetime
import pandas as pd
import io
import json
import sys
import os
# Ensure the local bypassed JobSpy and Scrapling packages are used
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "JobSpy-main")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Scrapling-main", "Scrapling-main")))

from enum import Enum
from jobspy import scrape_jobs

# Initialize FastAPI app
app = FastAPI(
    title="JobSpy API - Job Scraper ",
    description="Powerful job scraping API that aggregates jobs from LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, and more",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class JobSite(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    ZIP_RECRUITER = "zip_recruiter"
    GLASSDOOR = "glassdoor"
    GOOGLE = "google"
    BAYT = "bayt"
    NAUKRI = "naukri"
    BDJOBS = "bdjobs"


class JobTypeEnum(str, Enum):
    FULLTIME = "fulltime"
    PARTTIME = "parttime"
    INTERNSHIP = "internship"
    CONTRACT = "contract"


class DescriptionFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"


class OutputFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"


class JobSearchRequest(BaseModel):
    """Request model for job search"""
    site_name: Optional[List[JobSite]] = Field(
        default=None,
        description="List of job sites to scrape. If not provided, searches all sites."
    )
    search_term: Optional[str] = Field(
        default=None,
        description="Job search term (e.g., 'software engineer', 'data scientist')"
    )
    google_search_term: Optional[str] = Field(
        default=None,
        description="Specific search term for Google Jobs (e.g., 'software engineer jobs near San Francisco, CA since yesterday')"
    )
    location: Optional[str] = Field(
        default=None,
        description="Job location (e.g., 'San Francisco, CA', 'New York, NY')"
    )
    distance: Optional[int] = Field(
        default=50,
        ge=0,
        le=200,
        description="Search radius in miles (0-200)"
    )
    is_remote: bool = Field(
        default=False,
        description="Filter for remote jobs only"
    )
    job_type: Optional[JobTypeEnum] = Field(
        default=None,
        description="Type of job (fulltime, parttime, internship, contract)"
    )
    easy_apply: Optional[bool] = Field(
        default=None,
        description="Filter for jobs with easy apply option"
    )
    results_wanted: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of results to return per site (1-100)"
    )
    country_indeed: Optional[Union[str, List[str]]] = Field(
        default="USA",
        description="Country for Indeed/Glassdoor (e.g., 'USA', 'Canada', 'UK', 'India', or list/comma-separated)"
    )
    description_format: DescriptionFormat = Field(
        default=DescriptionFormat.MARKDOWN,
        description="Format for job descriptions (markdown or html)"
    )
    linkedin_fetch_description: bool = Field(
        default=True,
        description="Fetch full descriptions from LinkedIn/Naukri (slower but more detailed)"
    )
    linkedin_company_ids: Optional[List[int]] = Field(
        default=None,
        description="Filter LinkedIn jobs by specific company IDs"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset for search results"
    )
    hours_old: Optional[int] = Field(
        default=None,
        ge=1,
        description="Filter jobs posted within the last N hours"
    )
    enforce_annual_salary: bool = Field(
        default=False,
        description="Convert all salaries to annual format"
    )
    verbose: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Verbosity level (0=errors only, 1=warnings, 2=all logs)"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.JSON,
        description="Output format (json, csv, or excel)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "site_name": ["indeed", "linkedin"],
                "search_term": "software engineer",
                "location": "San Francisco, CA",
                "distance": 50,
                "is_remote": False,
                "job_type": "fulltime",
                "results_wanted": 20,
                "country_indeed": "USA",
                "hours_old": 72,
                "description_format": "markdown",
                "output_format": "json"
            }
        }


class JobSearchResponse(BaseModel):
    """Response model for job search"""
    success: bool
    message: str
    total_results: int
    search_parameters: dict
    timestamp: str
    jobs: Optional[List[dict]] = None
    error: Optional[str] = None


# Helper functions
def dataframe_to_dict_list(df: pd.DataFrame) -> List[dict]:
    """Convert DataFrame to list of dictionaries with proper JSON serialization"""
    return json.loads(df.to_json(orient='records', date_format='iso'))


def create_csv_response(df: pd.DataFrame, filename: str = "jobs.csv"):
    """Create CSV streaming response"""
    stream = io.StringIO()
    df.to_csv(stream, index=False, encoding='utf-8')
    response = StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
    return response


def create_excel_response(df: pd.DataFrame, filename: str = "jobs.xlsx"):
    """Create Excel streaming response"""
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Jobs')
    stream.seek(0)
    response = StreamingResponse(
        iter([stream.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
    return response


# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - Premium Interactive Job Search Dashboard"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JobSpy Aggregator - Advanced Search Hub</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #030303;
            --bg-surface: #0a0a0c;
            --bg-card: #111115;
            --border-base: #1f1f25;
            --border-hover: #2e2e38;
            --text-primary: #f8f9fa;
            --text-secondary: #a0a0b0;
            --text-tertiary: #6b6b7b;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --accent-glow: rgba(59, 130, 246, 0.15);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --font-main: 'Plus Jakarta Sans', sans-serif;
            --font-display: 'Outfit', sans-serif;
            
            /* Site colors */
            --color-linkedin: #0a66c2;
            --color-indeed: #2557a7;
            --color-glassdoor: #0caa41;
            --color-ziprecruiter: #00a29a;
            --color-google: #4285f4;
            --color-bayt: #4a154b;
            --color-naukri: #ff6f61;
            --color-bdjobs: #fd5d14;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        body {
            font-family: var(--font-main);
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-base);
        }
        ::-webkit-scrollbar-thumb {
            background: var(--border-base);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: var(--border-hover);
        }

        /* App Layout */
        .app-container {
            display: flex;
            width: 100%;
            height: 100vh;
            overflow: hidden;
            position: relative;
        }

        /* Glowing background spots */
        .ambient-glow-1 {
            position: absolute;
            top: -200px;
            right: -200px;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.08) 0%, rgba(3, 3, 3, 0) 70%);
            z-index: 0;
            pointer-events: none;
        }

        .ambient-glow-2 {
            position: absolute;
            bottom: -200px;
            left: -200px;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(16, 185, 129, 0.04) 0%, rgba(3, 3, 3, 0) 70%);
            z-index: 0;
            pointer-events: none;
        }

        /* Sidebar - Search Inputs */
        .sidebar {
            width: 380px;
            min-width: 380px;
            background-color: var(--bg-surface);
            border-right: 1px solid var(--border-base);
            display: flex;
            flex-direction: column;
            height: 100%;
            z-index: 10;
            position: relative;
        }

        .sidebar-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border-base);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .sidebar-header h1 {
            font-family: var(--font-display);
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #fff 0%, #a0a0b0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .sidebar-header h1 span {
            color: var(--accent);
            -webkit-text-fill-color: var(--accent);
        }

        .api-badge {
            background-color: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: var(--success);
            padding: 0.25rem 0.6rem;
            border-radius: 99px;
            font-size: 0.75rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        .api-badge .dot {
            width: 6px;
            height: 6px;
            background-color: var(--success);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--success);
        }

        .sidebar-scrollable {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .form-group label {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .input-wrapper {
            position: relative;
            display: flex;
            align-items: center;
        }

        .input-wrapper svg {
            position: absolute;
            left: 0.85rem;
            width: 1.1rem;
            height: 1.1rem;
            color: var(--text-tertiary);
            pointer-events: none;
            transition: color 0.2s ease;
        }

        .input-wrapper input, 
        .input-wrapper select {
            width: 100%;
            background-color: var(--bg-card);
            border: 1px solid var(--border-base);
            color: var(--text-primary);
            padding: 0.8rem 1rem 0.8rem 2.5rem;
            border-radius: 10px;
            font-family: var(--font-main);
            font-size: 0.9rem;
            transition: all 0.2s ease;
            outline: none;
        }

        .input-wrapper input:focus, 
        .input-wrapper select:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }

        .input-wrapper input:focus + svg,
        .input-wrapper select:focus + svg {
            color: var(--accent);
        }

        /* Site Selector Grid */
        .site-selector-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.6rem;
        }

        .site-chip {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background-color: var(--bg-card);
            border: 1px solid var(--border-base);
            padding: 0.65rem 0.8rem;
            border-radius: 10px;
            cursor: pointer;
            user-select: none;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .site-chip:hover {
            border-color: var(--border-hover);
        }

        .site-chip.selected {
            background-color: rgba(59, 130, 246, 0.05);
            border-color: var(--accent);
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.1);
        }

        .site-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--border-hover);
            transition: all 0.2s ease;
        }

        .site-chip.selected .site-indicator {
            box-shadow: 0 0 6px currentColor;
            background-color: currentColor;
        }

        /* Toggle switches */
        .toggle-container {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.8rem;
            background-color: var(--bg-card);
            border: 1px solid var(--border-base);
            padding: 1rem;
            border-radius: 12px;
        }

        .toggle-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            user-select: none;
        }

        .toggle-label {
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }

        .toggle-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .toggle-desc {
            font-size: 0.75rem;
            color: var(--text-tertiary);
        }

        .switch {
            position: relative;
            display: inline-block;
            width: 44px;
            height: 24px;
        }

        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: var(--border-base);
            transition: .3s;
            border-radius: 34px;
            border: 1px solid var(--border-base);
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 16px;
            width: 16px;
            left: 3px;
            bottom: 3px;
            background-color: var(--text-primary);
            transition: .3s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--accent);
            border-color: var(--accent);
        }

        input:focus + .slider {
            box-shadow: 0 0 1px var(--accent);
        }

        input:checked + .slider:before {
            transform: translateX(20px);
        }

        /* Sidebar Footer / CTA */
        .sidebar-footer {
            padding: 1.5rem;
            border-top: 1px solid var(--border-base);
            background-color: var(--bg-surface);
        }

        .search-btn {
            width: 100%;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
            border: none;
            color: white;
            padding: 1rem;
            border-radius: 12px;
            font-family: var(--font-main);
            font-weight: 700;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.25);
        }

        .search-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.35);
        }

        .search-btn:active {
            transform: translateY(0);
        }

        .search-btn:disabled {
            background: var(--border-base);
            color: var(--text-tertiary);
            box-shadow: none;
            cursor: not-allowed;
            transform: none;
        }

        /* Main Workspace Container */
        .workspace {
            flex: 1;
            display: flex;
            flex-direction: column;
            height: 100%;
            position: relative;
            background-color: var(--bg-base);
            z-index: 1;
        }

        /* Workspace Header */
        .workspace-header {
            height: 70px;
            min-height: 70px;
            padding: 0 2rem;
            border-bottom: 1px solid var(--border-base);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background-color: rgba(3, 3, 3, 0.5);
            backdrop-filter: blur(8px);
            z-index: 5;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .header-tab {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-primary);
            position: relative;
            cursor: pointer;
            padding: 0.5rem 0;
        }

        .header-tab::after {
            content: '';
            position: absolute;
            bottom: -10px;
            left: 0;
            width: 100%;
            height: 2px;
            background-color: var(--accent);
            border-radius: 99px;
            box-shadow: 0 0 8px var(--accent);
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .docs-link {
            text-decoration: none;
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-weight: 500;
            padding: 0.4rem 0.8rem;
            border-radius: 8px;
            border: 1px solid var(--border-base);
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .docs-link:hover {
            color: var(--text-primary);
            border-color: var(--border-hover);
            background-color: var(--bg-surface);
        }

        /* Workspace Content scrollable */
        .workspace-content {
            flex: 1;
            overflow-y: auto;
            padding: 2rem;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        /* Hero / Stats Panel */
        .stats-panel {
            background-color: var(--bg-surface);
            border: 1px solid var(--border-base);
            border-radius: 16px;
            padding: 1.5rem;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.5rem;
            position: relative;
            overflow: hidden;
        }

        .stat-item {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            position: relative;
        }

        .stat-item:not(:last-child)::after {
            content: '';
            position: absolute;
            right: -0.75rem;
            top: 15%;
            height: 70%;
            width: 1px;
            background-color: var(--border-base);
        }

        .stat-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-tertiary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stat-value {
            font-family: var(--font-display);
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        /* Filter & Export Row */
        .control-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }

        .search-filter-wrapper {
            flex: 1;
            max-width: 450px;
            position: relative;
            display: flex;
            align-items: center;
        }

        .search-filter-wrapper svg {
            position: absolute;
            left: 1rem;
            width: 1.1rem;
            height: 1.1rem;
            color: var(--text-tertiary);
            pointer-events: none;
        }

        .search-filter-input {
            width: 100%;
            background-color: var(--bg-surface);
            border: 1px solid var(--border-base);
            color: var(--text-primary);
            padding: 0.75rem 1rem 0.75rem 2.6rem;
            border-radius: 10px;
            font-family: var(--font-main);
            font-size: 0.875rem;
            outline: none;
            transition: all 0.2s ease;
        }

        .search-filter-input:focus {
            border-color: var(--border-hover);
            box-shadow: 0 0 10px rgba(255, 255, 255, 0.02);
        }

        .export-group {
            display: flex;
            align-items: center;
            gap: 0.65rem;
        }

        .export-btn {
            background-color: var(--bg-surface);
            border: 1px solid var(--border-base);
            color: var(--text-secondary);
            padding: 0.7rem 1.1rem;
            border-radius: 10px;
            font-family: var(--font-main);
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .export-btn:hover:not(:disabled) {
            color: var(--text-primary);
            border-color: var(--border-hover);
            background-color: var(--bg-card);
        }

        .export-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }

        /* Results / Cards Area */
        .results-container {
            flex: 1;
            min-height: 250px;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .no-results {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 1rem;
            color: var(--text-tertiary);
            padding: 5rem 0;
            border: 2px dashed var(--border-base);
            border-radius: 16px;
        }

        .no-results svg {
            width: 3rem;
            height: 3rem;
            stroke-width: 1.5;
        }

        .no-results p {
            font-size: 0.95rem;
            font-weight: 500;
        }

        /* Job Cards Grid */
        .jobs-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 1.25rem;
        }

        .job-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-base);
            border-radius: 14px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            position: relative;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
        }

        .job-card:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 0 1px 1px rgba(255, 255, 255, 0.05) inset;
        }

        .job-card-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
        }

        .job-title-group {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            flex: 1;
        }

        .job-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .job-company {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .source-badge {
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.25rem 0.5rem;
            border-radius: 6px;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            color: #fff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.25);
        }

        /* Source Badge Colors */
        .source-linkedin { background-color: var(--color-linkedin); }
        .source-indeed { background-color: var(--color-indeed); }
        .source-glassdoor { background-color: var(--color-glassdoor); }
        .source-zip_recruiter { background-color: var(--color-ziprecruiter); }
        .source-google { background-color: var(--color-google); }
        .source-bayt { background-color: var(--color-bayt); }
        .source-naukri { background-color: var(--color-naukri); }
        .source-bdjobs { background-color: var(--color-bdjobs); }

        .job-card-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .meta-tag {
            background-color: var(--bg-surface);
            border: 1px solid var(--border-base);
            color: var(--text-secondary);
            padding: 0.35rem 0.65rem;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        .meta-tag svg {
            width: 0.85rem;
            height: 0.85rem;
            color: var(--text-tertiary);
        }

        .job-desc-snippet {
            font-size: 0.825rem;
            color: var(--text-secondary);
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            border-top: 1px solid var(--border-base);
            padding-top: 0.85rem;
        }

        .job-card-footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: auto;
            padding-top: 0.5rem;
        }

        .post-date {
            font-size: 0.75rem;
            color: var(--text-tertiary);
            font-weight: 500;
        }

        .view-btn {
            background-color: transparent;
            border: 1px solid var(--border-base);
            color: var(--text-primary);
            padding: 0.45rem 0.85rem;
            border-radius: 8px;
            font-family: var(--font-main);
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .job-card:hover .view-btn {
            background-color: var(--accent);
            border-color: var(--accent);
            color: white;
            box-shadow: 0 4px 10px rgba(59, 130, 246, 0.2);
        }

        /* Loading Spinner Overlay */
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(3, 3, 3, 0.8);
            backdrop-filter: blur(4px);
            z-index: 15;
            display: none;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 1.5rem;
        }

        .spinner-container {
            position: relative;
            width: 70px;
            height: 70px;
        }

        .spinner-ring {
            position: absolute;
            width: 100%;
            height: 100%;
            border: 4px solid var(--border-base);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        .spinner-ring-inner {
            position: absolute;
            top: 8px;
            left: 8px;
            right: 8px;
            bottom: 8px;
            border: 3px solid var(--border-base);
            border-top-color: var(--success);
            border-radius: 50%;
            animation: spin 1.5s linear infinite reverse;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .loading-logs {
            background-color: var(--bg-card);
            border: 1px solid var(--border-base);
            padding: 1rem 1.5rem;
            border-radius: 12px;
            width: 100%;
            max-width: 450px;
            height: 150px;
            font-family: monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }

        .loading-title {
            font-family: var(--font-display);
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        /* Detail Slide-out Drawer */
        .drawer {
            position: fixed;
            top: 0;
            right: -600px;
            width: 600px;
            height: 100%;
            background-color: var(--bg-surface);
            border-left: 1px solid var(--border-base);
            box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
            z-index: 100;
            transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            flex-direction: column;
        }

        .drawer.open {
            right: 0;
        }

        .drawer-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            z-index: 99;
            display: none;
        }

        .drawer-backdrop.open {
            display: block;
        }

        .drawer-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border-base);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .close-btn {
            background: none;
            border: none;
            color: var(--text-tertiary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.35rem;
            border-radius: 8px;
            border: 1px solid transparent;
            transition: all 0.2s ease;
        }

        .close-btn:hover {
            color: var(--text-primary);
            border-color: var(--border-base);
            background-color: var(--bg-card);
        }

        .drawer-header-title {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            flex: 1;
            padding-right: 1.5rem;
        }

        .drawer-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
            font-family: var(--font-display);
        }

        .drawer-company {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .drawer-body {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .drawer-meta-section {
            background-color: var(--bg-card);
            border: 1px solid var(--border-base);
            padding: 1rem;
            border-radius: 12px;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }

        .drawer-meta-item {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .drawer-meta-label {
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--text-tertiary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .drawer-meta-value {
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-primary);
        }

        .drawer-desc-title {
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--text-primary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border-base);
            padding-bottom: 0.5rem;
        }

        .drawer-desc-content {
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.6;
            white-space: pre-wrap;
        }

        .drawer-footer {
            padding: 1.5rem;
            border-top: 1px solid var(--border-base);
            background-color: var(--bg-surface);
        }

        .apply-btn {
            width: 100%;
            background-color: var(--accent);
            color: white;
            padding: 0.95rem;
            border-radius: 10px;
            font-family: var(--font-main);
            font-weight: 700;
            font-size: 0.9rem;
            text-align: center;
            text-decoration: none;
            display: block;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
            transition: all 0.2s ease;
        }

        .apply-btn:hover {
            background-color: var(--accent-hover);
            transform: translateY(-1px);
            box-shadow: 0 6px 15px rgba(59, 130, 246, 0.3);
        }

        /* Responsive */
        @media (max-width: 1024px) {
            .app-container {
                flex-direction: column;
                height: auto;
                overflow: visible;
            }
            .sidebar {
                width: 100%;
                min-width: 100%;
                height: auto;
            }
            .workspace {
                height: auto;
                overflow: visible;
            }
            .workspace-header {
                position: sticky;
                top: 0;
            }
            .workspace-content {
                overflow-y: visible;
            }
            .drawer {
                width: 100%;
                right: -100%;
            }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Ambient Background Lights -->
        <div class="ambient-glow-1"></div>
        <div class="ambient-glow-2"></div>

        <!-- Left Sidebar Controls -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h1>Job<span>Spy</span></h1>
                <div class="api-badge">
                    <span class="dot"></span>
                    API Active
                </div>
            </div>

            <div class="sidebar-scrollable">
                <!-- Search term -->
                <div class="form-group">
                    <label for="search-term">Search Term</label>
                    <div class="input-wrapper">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        <input type="text" id="search-term" placeholder="e.g. Software Engineer, React Developer">
                    </div>
                </div>

                <!-- Custom Google search -->
                <div class="form-group">
                    <label for="google-search-term">Google Custom Query (Optional)</label>
                    <div class="input-wrapper">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                        <input type="text" id="google-search-term" placeholder="e.g. software engineer jobs near SF since yesterday">
                    </div>
                </div>

                <!-- Job Type -->
                <div class="form-group">
                    <label for="job-type">Job Type</label>
                    <div class="input-wrapper">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                        <select id="job-type">
                            <option value="">All Job Types</option>
                            <option value="fulltime">Full Time</option>
                            <option value="parttime">Part Time</option>
                            <option value="internship">Internship</option>
                            <option value="contract">Contract</option>
                        </select>
                    </div>
                </div>

                <!-- Hours Old -->
                <div class="form-group">
                    <label for="hours-old">Date Posted</label>
                    <div class="input-wrapper">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        <select id="hours-old">
                            <option value="">Any Time</option>
                            <option value="24">Last 24 Hours</option>
                            <option value="48">Last 48 Hours</option>
                            <option value="72">Last 3 Days</option>
                            <option value="168">Last Week</option>
                        </select>
                    </div>
                </div>

                <!-- Results Wanted -->
                <div class="form-group">
                    <label for="results-wanted">Results Per Site</label>
                    <div class="input-wrapper">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"></path></svg>
                        <input type="number" id="results-wanted" value="20" min="5" max="100">
                    </div>
                </div>

                <!-- Country for Indeed/Glassdoor -->
                <div class="form-group">
                    <label for="country-indeed">Indeed Country</label>
                    <div class="input-wrapper">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 002 2h2m-4-3.5a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"></path></svg>
                        <select id="country-indeed">
                            <option value="USA">United States</option>
                            <option value="">All Countries</option>
                            <option value="India">India</option>
                            <option value="Canada">Canada</option>
                            <option value="UK">United Kingdom</option>
                            <option value="Australia">Australia</option>
                            <option value="Bangladesh">Bangladesh</option>
                        </select>
                    </div>
                </div>

                <!-- Toggles -->
                <div class="toggle-container">
                    <!-- Remote -->
                    <div class="toggle-item" id="toggle-remote-parent">
                        <div class="toggle-label">
                            <span class="toggle-title">Remote Only</span>
                            <span class="toggle-desc">Exclude on-site roles</span>
                        </div>
                        <label class="switch">
                            <input type="checkbox" id="is-remote">
                            <span class="slider"></span>
                        </label>
                    </div>

                    <!-- Enforce Salary -->
                    <div class="toggle-item" id="toggle-salary-parent">
                        <div class="toggle-label">
                            <span class="toggle-title">Enforce Salary</span>
                            <span class="toggle-desc">Convert to annual rates</span>
                        </div>
                        <label class="switch">
                            <input type="checkbox" id="enforce-salary">
                            <span class="slider"></span>
                        </label>
                    </div>

                    <!-- Easy Apply -->
                    <div class="toggle-item" id="toggle-easy-parent">
                        <div class="toggle-label">
                            <span class="toggle-title">Easy Apply Only</span>
                            <span class="toggle-desc">Filter by quick application</span>
                        </div>
                        <label class="switch">
                            <input type="checkbox" id="easy-apply">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>

                <!-- Site Selector -->
                <div class="form-group">
                    <label>Select Job Boards</label>
                    <div class="site-selector-grid">
                        <div class="site-chip selected" data-site="linkedin" style="color: var(--color-linkedin)">
                            <span class="site-indicator"></span>
                            LinkedIn
                        </div>
                        <div class="site-chip selected" data-site="indeed" style="color: var(--color-indeed)">
                            <span class="site-indicator"></span>
                            Indeed
                        </div>
                        <div class="site-chip" data-site="glassdoor" style="color: var(--color-glassdoor)">
                            <span class="site-indicator"></span>
                            Glassdoor
                        </div>
                        <div class="site-chip" data-site="zip_recruiter" style="color: var(--color-ziprecruiter)">
                            <span class="site-indicator"></span>
                            ZipRecruiter
                        </div>
                        <div class="site-chip" data-site="google" style="color: var(--color-google)">
                            <span class="site-indicator"></span>
                            Google Jobs
                        </div>
                        <div class="site-chip" data-site="bayt" style="color: var(--color-bayt)">
                            <span class="site-indicator"></span>
                            Bayt
                        </div>
                        <div class="site-chip" data-site="naukri" style="color: var(--color-naukri)">
                            <span class="site-indicator"></span>
                            Naukri
                        </div>
                        <div class="site-chip" data-site="bdjobs" style="color: var(--color-bdjobs)">
                            <span class="site-indicator"></span>
                            BDJobs
                        </div>
                    </div>
                </div>
            </div>

            <div class="sidebar-footer">
                <button class="search-btn" id="search-btn">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                    Search Aggregated Jobs
                </button>
            </div>
        </div>

        <!-- Main Workspace Area -->
        <div class="workspace">
            <header class="workspace-header">
                <div class="header-left">
                    <div class="header-tab">Job Aggregator Dashboard</div>
                </div>
                <div class="header-right">
                    <a href="/docs" target="_blank" class="docs-link">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        API Documentation
                    </a>
                </div>
            </header>

            <div class="workspace-content">
                <!-- Status & KPI Stats Grid -->
                <div class="stats-panel">
                    <div class="stat-item">
                        <span class="stat-label">Total Jobs Found</span>
                        <span class="stat-value" id="stat-total">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Remote Roles</span>
                        <span class="stat-value" id="stat-remote">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Boards Queried</span>
                        <span class="stat-value" id="stat-boards">0</span>
                    </div>
                    <div class="stat-item" style="border-right: none;">
                        <span class="stat-label">Average Salary</span>
                        <span class="stat-value" id="stat-salary">$0</span>
                    </div>
                </div>

                <!-- Controls & Filtering Row -->
                <div class="control-row">
                    <div class="search-filter-wrapper">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path></svg>
                        <input type="text" id="filter-input" class="search-filter-input" placeholder="Quick filter by title, company, location, or source..." disabled>
                    </div>

                    <div class="export-group">
                        <button class="export-btn" id="export-csv-btn" disabled>
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                            Export CSV
                        </button>
                        <button class="export-btn" id="export-xlsx-btn" disabled>
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                            Export Excel
                        </button>
                    </div>
                </div>

                <!-- Results Section -->
                <div class="results-container">
                    <div class="no-results" id="no-results-view">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="48" height="48"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        <p>No search conducted. Select options in the panel and click search.</p>
                    </div>

                    <div class="jobs-grid" id="jobs-grid" style="display: none;">
                        <!-- Cards injected by JS -->
                    </div>
                </div>
            </div>

            <!-- Loading Spinner & Terminal-like Overlay -->
            <div class="loading-overlay" id="loading-overlay">
                <div class="spinner-container">
                    <div class="spinner-ring"></div>
                    <div class="spinner-ring-inner"></div>
                </div>
                <div class="loading-title">Aggregating Job Openings...</div>
                <div class="loading-logs" id="loading-logs">
                    <div>[INFO] Initializing search criteria adapters...</div>
                </div>
            </div>
        </div>

        <!-- Detail Slide-out Drawer -->
        <div class="drawer-backdrop" id="drawer-backdrop"></div>
        <div class="drawer" id="drawer">
            <div class="drawer-header">
                <div class="drawer-header-title">
                    <h2 class="drawer-title" id="drawer-title">Job Title</h2>
                    <div class="drawer-company" id="drawer-company">Company Name</div>
                </div>
                <button class="close-btn" id="drawer-close">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="drawer-body">
                <div class="drawer-meta-section">
                    <div class="drawer-meta-item">
                        <span class="drawer-meta-label">Location</span>
                        <span class="drawer-meta-value" id="drawer-location">-</span>
                    </div>
                    <div class="drawer-meta-item">
                        <span class="drawer-meta-label">Source Board</span>
                        <span class="drawer-meta-value" id="drawer-source">-</span>
                    </div>
                    <div class="drawer-meta-item">
                        <span class="drawer-meta-label">Job Type</span>
                        <span class="drawer-meta-value" id="drawer-type">-</span>
                    </div>
                    <div class="drawer-meta-item">
                        <span class="drawer-meta-label">Salary Rate</span>
                        <span class="drawer-meta-value" id="drawer-salary">-</span>
                    </div>
                </div>

                <div class="drawer-meta-section" id="drawer-contact-section" style="display: none; grid-template-columns: 1fr;">
                    <div class="drawer-meta-item">
                        <span class="drawer-meta-label">Parsed Contact Emails</span>
                        <span class="drawer-meta-value" id="drawer-emails" style="font-family: monospace; color: var(--accent);">-</span>
                    </div>
                </div>

                <div class="drawer-desc-title">Job Description</div>
                <div class="drawer-desc-content" id="drawer-description">
                    Job Description text goes here...
                </div>
            </div>
            <div class="drawer-footer">
                <a href="#" target="_blank" rel="noopener noreferrer" class="apply-btn" id="drawer-apply-link">Apply Now on Official Site</a>
            </div>
        </div>
    </div>

    <!-- Script logic -->
    <script>
        // DOM Elements
        const siteChips = document.querySelectorAll('.site-chip');
        const searchBtn = document.getElementById('search-btn');
        const filterInput = document.getElementById('filter-input');
        const exportCsvBtn = document.getElementById('export-csv-btn');
        const exportXlsxBtn = document.getElementById('export-xlsx-btn');
        const noResultsView = document.getElementById('no-results-view');
        const jobsGrid = document.getElementById('jobs-grid');
        const loadingOverlay = document.getElementById('loading-overlay');
        const loadingLogs = document.getElementById('loading-logs');
        
        // Form inputs
        const searchTermInput = document.getElementById('search-term');
        const locationInput = null;
        const distanceInput = null;
        const googleSearchTermInput = document.getElementById('google-search-term');
        const jobTypeSelect = document.getElementById('job-type');
        const hoursOldSelect = document.getElementById('hours-old');
        const resultsWantedInput = document.getElementById('results-wanted');
        const countryIndeedSelect = document.getElementById('country-indeed');
        const isRemoteInput = document.getElementById('is-remote');
        const enforceSalaryInput = document.getElementById('enforce-salary');
        const easyApplyInput = document.getElementById('easy-apply');

        // KPI element tags
        const statTotal = document.getElementById('stat-total');
        const statRemote = document.getElementById('stat-remote');
        const statBoards = document.getElementById('stat-boards');
        const statSalary = document.getElementById('stat-salary');

        // Drawer Elements
        const drawer = document.getElementById('drawer');
        const drawerBackdrop = document.getElementById('drawer-backdrop');
        const drawerClose = document.getElementById('drawer-close');
        const drawerTitle = document.getElementById('drawer-title');
        const drawerCompany = document.getElementById('drawer-company');
        const drawerLocation = document.getElementById('drawer-location');
        const drawerSource = document.getElementById('drawer-source');
        const drawerType = document.getElementById('drawer-type');
        const drawerSalary = document.getElementById('drawer-salary');
        const drawerEmails = document.getElementById('drawer-emails');
        const drawerContactSection = document.getElementById('drawer-contact-section');
        const drawerDescription = document.getElementById('drawer-description');
        const drawerApplyLink = document.getElementById('drawer-apply-link');

        // State variables
        let loadedJobs = [];

        // Toggle Chip Selection
        siteChips.forEach(chip => {
            chip.addEventListener('click', () => {
                chip.classList.toggle('selected');
            });
        });

        // Toggle switches parent clicks
        document.getElementById('toggle-remote-parent').addEventListener('click', (e) => {
            if (e.target !== isRemoteInput) {
                isRemoteInput.checked = !isRemoteInput.checked;
            }
        });
        document.getElementById('toggle-salary-parent').addEventListener('click', (e) => {
            if (e.target !== enforceSalaryInput) {
                enforceSalaryInput.checked = !enforceSalaryInput.checked;
            }
        });
        document.getElementById('toggle-easy-parent').addEventListener('click', (e) => {
            if (e.target !== easyApplyInput) {
                easyApplyInput.checked = !easyApplyInput.checked;
            }
        });

        // Logs writer helper
        function addLog(message, type = 'info') {
            const time = new Date().toLocaleTimeString();
            const logDiv = document.createElement('div');
            logDiv.innerHTML = `<span style="color: var(--text-tertiary)">[${time}]</span> <span style="color: ${type === 'error' ? 'var(--danger)' : 'var(--text-secondary)'}">${message}</span>`;
            loadingLogs.appendChild(logDiv);
            loadingLogs.scrollTop = loadingLogs.scrollHeight;
        }

        // Get selected site list
        function getSelectedSites() {
            const selected = [];
            siteChips.forEach(chip => {
                if (chip.classList.contains('selected')) {
                    selected.push(chip.getAttribute('data-site'));
                }
            });
            return selected;
        }

        // Click handler to trigger scraper search
        searchBtn.addEventListener('click', async () => {
            const selectedSites = getSelectedSites();
            if (selectedSites.length === 0) {
                alert("Please select at least one job board to query!");
                return;
            }

            const search_term = searchTermInput.value.trim();
            const location = null;
            const google_search_term = googleSearchTermInput.value.trim();

            if (!search_term && !google_search_term) {
                alert("Please supply either a Search Term or a Google Custom Query!");
                return;
            }

            // Display loading overlay and reset logs
            loadingLogs.innerHTML = "";
            loadingOverlay.style.display = 'flex';
            
            addLog("Preparing aggregated crawler configurations...", 'info');
            addLog(`Selected boards: ${selectedSites.join(', ')}`, 'info');
            addLog("Opening background stealth-fetcher sandbox nodes...", 'info');

            // Format body payload
            const payload = {
                site_name: selectedSites,
                search_term: search_term || null,
                location: null,
                google_search_term: google_search_term || null,
                distance: null,
                is_remote: isRemoteInput.checked,
                job_type: jobTypeSelect.value || null,
                hours_old: parseInt(hoursOldSelect.value) || null,
                results_wanted: parseInt(resultsWantedInput.value) || 20,
                country_indeed: countryIndeedSelect.value,
                enforce_annual_salary: enforceSalaryInput.checked,
                easy_apply: easyApplyInput.checked || null,
                description_format: "markdown",
                output_format: "json"
            };

            // Remove null properties
            Object.keys(payload).forEach(key => payload[key] === null && delete payload[key]);

            try {
                addLog(`Executing search POST request to Vercel/local backend API...`, 'info');
                
                const response = await fetch('/api/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.detail?.error || response.statusText);
                }

                const result = await response.json();
                addLog(`Aggregator fetch returned status: SUCCESS`, 'info');
                addLog(`Processing raw JSON response: aggregated ${result.total_results || 0} items...`, 'info');

                loadedJobs = result.jobs || [];
                renderJobs(loadedJobs);
                updateStats(loadedJobs, selectedSites.length);
                
                // Enable controls
                filterInput.disabled = false;
                exportCsvBtn.disabled = loadedJobs.length === 0;
                exportXlsxBtn.disabled = loadedJobs.length === 0;

            } catch (e) {
                addLog(`CRITICAL API ERROR: ${e.message}`, 'error');
                console.error(e);
                alert(`Search failed: ${e.message}`);
            } finally {
                setTimeout(() => {
                    loadingOverlay.style.display = 'none';
                }, 800);
            }
        });

        // Render KPI dashboard metrics
        function updateStats(jobs, boardsCount) {
            statTotal.textContent = jobs.length;
            
            const remoteCount = jobs.filter(j => j.is_remote).length;
            statRemote.textContent = remoteCount;
            
            statBoards.textContent = boardsCount;

            // Compute Average Salary
            let salaries = [];
            jobs.forEach(j => {
                let s = null;
                if (j.min_amount) {
                    s = j.min_amount;
                } else if (j.max_amount) {
                    s = j.max_amount;
                }
                if (s) {
                    // Check interval
                    if (j.salary_interval === 'yearly' || enforceSalaryInput.checked) {
                        salaries.push(s);
                    } else if (j.salary_interval === 'hourly') {
                        salaries.push(s * 40 * 52); // Approx annual
                    }
                }
            });

            if (salaries.length > 0) {
                const avg = salaries.reduce((a,b) => a+b, 0) / salaries.length;
                statSalary.textContent = `$${Math.round(avg/1000)}k`;
            } else {
                statSalary.textContent = "N/A";
            }
        }

        // Clean values formatting
        function formatSalary(job) {
            if (!job.min_amount && !job.max_amount) return "Not Mentioned";
            const cur = job.currency === 'USD' ? '$' : (job.currency || '');
            const interval = job.salary_interval ? ` / ${job.salary_interval}` : '';
            if (job.min_amount && job.max_amount) {
                return `${cur}${job.min_amount.toLocaleString()} - ${cur}${job.max_amount.toLocaleString()}${interval}`;
            }
            const amt = job.min_amount || job.max_amount;
            return `${cur}${amt.toLocaleString()}${interval}`;
        }

        // Safe Date formatter to avoid timezone shifting
        function safeFormatDate(dateStr) {
            if (!dateStr) return 'Date Not Listed';
            const datePart = dateStr.split('T')[0];
            const parts = datePart.split('-');
            if (parts.length === 3) {
                const year = parseInt(parts[0], 10);
                const month = parseInt(parts[1], 10) - 1;
                const day = parseInt(parts[2], 10);
                const dateObj = new Date(year, month, day);
                return dateObj.toLocaleDateString();
            }
            return dateStr;
        }

        // Render Job Cards into Grid
        function renderJobs(jobs) {
            jobsGrid.innerHTML = "";
            if (jobs.length === 0) {
                noResultsView.style.display = 'flex';
                noResultsView.querySelector('p').textContent = "No job postings matched your specifications. Adjust parameters.";
                jobsGrid.style.display = 'none';
                return;
            }

            noResultsView.style.display = 'none';
            jobsGrid.style.display = 'grid';

            jobs.forEach(job => {
                const card = document.createElement('div');
                card.className = 'job-card';
                card.innerHTML = `
                    <div class="job-card-header">
                        <div class="job-title-group">
                            <div class="job-title" title="${job.title || 'Not Mentioned'}">${job.title || 'Not Mentioned'}</div>
                            <div class="job-company">${job.company || job.company_name || 'Not Mentioned'}</div>
                        </div>
                        <span class="source-badge source-${job.site}">${job.site}</span>
                    </div>

                    <div class="job-card-meta">
                        <div class="meta-tag">
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                            ${job.location || 'Not Mentioned'}
                        </div>
                        <div class="meta-tag">
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                            ${job.job_type || 'Not Mentioned'}
                        </div>
                        ${job.is_remote ? `
                            <div class="meta-tag" style="border-color: rgba(16, 185, 129, 0.2); color: var(--success)">
                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
                                Remote
                            </div>
                        ` : ''}
                    </div>

                    <div class="job-desc-snippet">${job.description || 'Not Mentioned'}</div>

                    <div class="job-card-footer">
                        <span class="post-date">${job.date_posted ? `Posted: ${safeFormatDate(job.date_posted)}` : 'Not Mentioned'}</span>
                        <button class="view-btn">View Details</button>
                    </div>
                `;

                card.addEventListener('click', (e) => {
                    openDrawer(job);
                });

                jobsGrid.appendChild(card);
            });
        }

        // Live filtering within card lists
        filterInput.addEventListener('input', (e) => {
            const val = e.target.value.toLowerCase().trim();
            if (!val) {
                renderJobs(loadedJobs);
                return;
            }
            const filtered = loadedJobs.filter(job => {
                return (job.title || '').toLowerCase().includes(val) ||
                       (job.company || job.company_name || '').toLowerCase().includes(val) ||
                       (job.location || '').toLowerCase().includes(val) ||
                       (job.site || '').toLowerCase().includes(val) ||
                       (job.description || '').toLowerCase().includes(val);
            });
            renderJobs(filtered);
        });

        // Open Side Drawer Detail Panel
        function openDrawer(job) {
            drawerTitle.textContent = job.title || 'Not Mentioned';
            drawerCompany.textContent = job.company || job.company_name || 'Not Mentioned';
            drawerLocation.textContent = job.location || 'Not Mentioned';
            drawerSource.textContent = job.site || 'Not Mentioned';
            drawerType.textContent = job.job_type || 'Not Mentioned';
            drawerSalary.textContent = formatSalary(job);
            
            // Always display contact section and show emails or 'Not Mentioned'
            drawerContactSection.style.display = 'block';
            drawerEmails.textContent = (job.emails && job.emails.length > 0) ? job.emails.join(', ') : 'Not Mentioned';

            drawerDescription.textContent = job.description || 'Not Mentioned';
            drawerApplyLink.href = job.job_url || '#';

            drawer.classList.add('open');
            drawerBackdrop.classList.add('open');
        }

        // Close Side Drawer
        function closeDrawer() {
            drawer.classList.remove('open');
            drawerBackdrop.classList.remove('open');
        }

        drawerClose.addEventListener('click', closeDrawer);
        drawerBackdrop.addEventListener('click', closeDrawer);

        // Export data triggers
        async function handleExport(format) {
            const selectedSites = getSelectedSites();
            const payload = {
                site_name: selectedSites,
                search_term: searchTermInput.value.trim() || null,
                location: null,
                google_search_term: googleSearchTermInput.value.trim() || null,
                distance: null,
                is_remote: isRemoteInput.checked,
                job_type: jobTypeSelect.value || null,
                hours_old: parseInt(hoursOldSelect.value) || null,
                results_wanted: parseInt(resultsWantedInput.value) || 20,
                country_indeed: countryIndeedSelect.value,
                enforce_annual_salary: enforceSalaryInput.checked,
                easy_apply: easyApplyInput.checked || null,
                description_format: "markdown",
                output_format: format
            };
            Object.keys(payload).forEach(key => payload[key] === null && delete payload[key]);

            try {
                const response = await fetch('/api/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if (!response.ok) throw new Error("Export request failed.");

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `jobs_${new Date().toISOString().slice(0,10)}.${format}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            } catch (e) {
                alert(`Export failed: ${e.message}`);
            }
        }

        exportCsvBtn.addEventListener('click', () => handleExport('csv'));
        exportXlsxBtn.addEventListener('click', () => handleExport('excel'));

    </script>
</body>
</html>"""


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "JobSpy API",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.get("/api/sites")
async def get_supported_sites():
    """Get list of supported job sites"""
    return {
        "supported_sites": [site.value for site in JobSite],
        "descriptions": {
            "linkedin": "LinkedIn - Professional network with quality job postings",
            "indeed": "Indeed - Large job aggregator with extensive listings",
            "zip_recruiter": "ZipRecruiter - US/Canada focused job board",
            "glassdoor": "Glassdoor - Jobs with company reviews and salary data",
            "google": "Google Jobs - Aggregated job listings from Google",
            "bayt": "Bayt - Middle East focused job portal",
            "naukri": "Naukri - India's leading job portal",
            "bdjobs": "BDJobs - Bangladesh's leading job portal"
        }
    }


@app.get("/api/countries")
async def get_supported_countries():
    """Get list of supported countries for Indeed/Glassdoor"""
    countries = [
        "USA", "Canada", "UK", "Australia", "India", "Germany", "France",
        "Spain", "Italy", "Netherlands", "Belgium", "Switzerland", "Austria",
        "Sweden", "Norway", "Denmark", "Finland", "Ireland", "Poland",
        "Brazil", "Mexico", "Argentina", "Chile", "Colombia", "Singapore",
        "Hong Kong", "Japan", "South Korea", "UAE", "Saudi Arabia", "Egypt",
        "South Africa", "New Zealand", "Philippines", "Malaysia", "Indonesia",
        "Thailand", "Vietnam", "Pakistan", "Bangladesh", "Turkey", "Israel"
    ]
    return {
        "supported_countries": countries,
        "note": "Use exact spelling for country_indeed parameter. LinkedIn and ZipRecruiter use location parameter only."
    }


def detect_country(location: Optional[str]) -> str:
    if not location:
        return "USA"
    loc_lower = location.lower().strip()
    
    # Common synonyms mapping
    synonyms = {
        "united states": "USA",
        "usa": "USA",
        "u.s.a.": "USA",
        "u.s.": "USA",
        "united kingdom": "UK",
        "uk": "UK",
        "u.k.": "UK",
        "great britain": "UK",
        "england": "UK",
        "london": "UK",
    }
    
    for syn, target in synonyms.items():
        if syn in loc_lower:
            return target
            
    # List of supported countries (case-insensitive search)
    supported_countries = [
        "Canada", "Australia", "India", "Germany", "France",
        "Spain", "Italy", "Netherlands", "Belgium", "Switzerland", "Austria",
        "Sweden", "Norway", "Denmark", "Finland", "Ireland", "Poland",
        "Brazil", "Mexico", "Argentina", "Chile", "Colombia", "Singapore",
        "Hong Kong", "Japan", "South Korea", "UAE", "Saudi Arabia", "Egypt",
        "South Africa", "New Zealand", "Philippines", "Malaysia", "Indonesia",
        "Thailand", "Vietnam", "Pakistan", "Bangladesh", "Turkey", "Israel"
    ]
    
    for country in supported_countries:
        if country.lower() in loc_lower:
            return country
            
    # Common cities mapping to identify the country
    india_cities = ["pune", "mumbai", "bangalore", "bengaluru", "delhi", "noida", "gurgaon", "hyderabad", "chennai", "kolkata", "ahmedabad", "surat"]
    for city in india_cities:
        if city in loc_lower:
            return "India"
            
    canada_cities = ["toronto", "vancouver", "montreal", "ottawa", "calgary", "edmonton"]
    for city in canada_cities:
        if city in loc_lower:
            return "Canada"
            
    germany_cities = ["berlin", "munich", "frankfurt", "hamburg", "cologne"]
    for city in germany_cities:
        if city in loc_lower:
            return "Germany"
            
    return "USA"


@app.post("/api/scrape", response_model=JobSearchResponse)
async def scrape_jobs_endpoint(request: JobSearchRequest):
    """
    Main endpoint to scrape jobs from multiple job boards
    
    Returns job listings based on search criteria in JSON, CSV, or Excel format.
    """
    try:
        # Prepare parameters
        site_names = [site.value for site in request.site_name] if request.site_name else None
        
        country_indeed = request.country_indeed
        if not country_indeed:
            country_indeed = None
            location = None
        else:
            if isinstance(country_indeed, list):
                country_indeed = [
                    "united arab emirates" if c.lower().strip() == "uae" else c
                    for c in country_indeed
                ]
                location = None
            elif isinstance(country_indeed, str):
                parts = [c.strip() for c in country_indeed.split(",") if c.strip()]
                normalized_parts = [
                    "united arab emirates" if c.lower() == "uae" else c
                    for c in parts
                ]
                if len(normalized_parts) > 1:
                    country_indeed = normalized_parts
                    location = None
                else:
                    country_indeed = normalized_parts[0] if normalized_parts else None
                    location = country_indeed
            else:
                location = country_indeed
            
        search_params = {
            "site_name": site_names,
            "search_term": request.search_term,
            "google_search_term": request.google_search_term,
            "location": location,
            "distance": None,
            "is_remote": request.is_remote,
            "job_type": request.job_type.value if request.job_type else None,
            "easy_apply": request.easy_apply,
            "results_wanted": request.results_wanted,
            "country_indeed": country_indeed,
            "description_format": request.description_format.value,
            "linkedin_fetch_description": request.linkedin_fetch_description,
            "linkedin_company_ids": request.linkedin_company_ids,
            "offset": request.offset,
            "hours_old": request.hours_old,
            "enforce_annual_salary": request.enforce_annual_salary,
            "verbose": request.verbose,
        }
        
        # Remove None values
        search_params = {k: v for k, v in search_params.items() if v is not None}
        
        # Scrape jobs
        jobs_df = scrape_jobs(**search_params)
        
        if jobs_df.empty:
            return JobSearchResponse(
                success=True,
                message="No jobs found matching the criteria",
                total_results=0,
                search_parameters=search_params,
                timestamp=datetime.utcnow().isoformat(),
                jobs=[]
            )
        
        # Return based on format
        if request.output_format == OutputFormat.CSV:
            return create_csv_response(jobs_df, f"jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        elif request.output_format == OutputFormat.EXCEL:
            return create_excel_response(jobs_df, f"jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        else:  # JSON
            jobs_list = dataframe_to_dict_list(jobs_df)
            return JobSearchResponse(
                success=True,
                message=f"Successfully scraped {len(jobs_list)} jobs",
                total_results=len(jobs_list),
                search_parameters=search_params,
                timestamp=datetime.utcnow().isoformat(),
                jobs=jobs_list
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": "Failed to scrape jobs. Please check your parameters and try again.",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.get("/api/scrape/simple")
async def scrape_jobs_simple(
    search_term: str = Query(..., description="Job search term (e.g., 'software engineer')"),
    location: Optional[str] = Query(None, description="Location (e.g., 'San Francisco, CA')"),
    site_name: Optional[str] = Query(None, description="Comma-separated site names (e.g., 'indeed,linkedin')"),
    results_wanted: int = Query(20, ge=1, le=100, description="Number of results per site"),
    is_remote: bool = Query(False, description="Remote jobs only"),
    hours_old: Optional[int] = Query(None, description="Jobs posted within N hours"),
    output_format: OutputFormat = Query(OutputFormat.JSON, description="Output format")
):
    """
    Simplified GET endpoint for quick job searches
    
    Example: /scrape/simple?search_term=python developer&location=New York&site_name=indeed,linkedin&results_wanted=30
    """
    try:
        sites = site_name.split(',') if site_name else None
        
        jobs_df = scrape_jobs(
            site_name=sites,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            is_remote=is_remote,
            hours_old=hours_old,
            linkedin_fetch_description=True,
            verbose=1
        )
        
        if jobs_df.empty:
            return JSONResponse(content={
                "success": True,
                "message": "No jobs found",
                "total_results": 0,
                "jobs": []
            })
        
        if output_format == OutputFormat.CSV:
            return create_csv_response(jobs_df)
        elif output_format == OutputFormat.EXCEL:
            return create_excel_response(jobs_df)
        else:
            return JSONResponse(content={
                "success": True,
                "message": f"Found {len(jobs_df)} jobs",
                "total_results": len(jobs_df),
                "jobs": dataframe_to_dict_list(jobs_df)
            })
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/examples")
async def get_example_requests():
    """Get example API requests for different use cases"""
    return {
        "examples": [
            {
                "name": "Basic Software Engineer Search",
                "description": "Search for software engineer jobs in San Francisco",
                "method": "POST",
                "endpoint": "/api/scrape",
                "body": {
                    "site_name": ["indeed", "linkedin"],
                    "search_term": "software engineer",
                    "location": "San Francisco, CA",
                    "results_wanted": 20,
                    "job_type": "fulltime"
                }
            },
            {
                "name": "Remote Python Developer Jobs",
                "description": "Find remote Python developer positions posted in last 48 hours",
                "method": "POST",
                "endpoint": "/api/scrape",
                "body": {
                    "site_name": ["indeed", "linkedin", "zip_recruiter"],
                    "search_term": "python developer",
                    "is_remote": True,
                    "hours_old": 48,
                    "results_wanted": 30,
                    "job_type": "fulltime"
                }
            },
            {
                "name": "Data Science Internships",
                "description": "Search for data science internships in New York",
                "method": "POST",
                "endpoint": "/api/scrape",
                "body": {
                    "site_name": ["linkedin", "indeed", "glassdoor"],
                    "search_term": "data science intern",
                    "location": "New York, NY",
                    "job_type": "internship",
                    "results_wanted": 25,
                    "distance": 25
                }
            },
            {
                "name": "Recent Senior Engineer Roles with Salary",
                "description": "Find senior engineer jobs posted in last 24 hours with annual salary",
                "method": "POST",
                "endpoint": "/api/scrape",
                "body": {
                    "site_name": ["indeed", "linkedin"],
                    "search_term": "senior software engineer",
                    "location": "Seattle, WA",
                    "hours_old": 24,
                    "results_wanted": 20,
                    "enforce_annual_salary": True,
                    "job_type": "fulltime"
                }
            },
            {
                "name": "Simple GET Request",
                "description": "Quick search using GET endpoint",
                "method": "GET",
                "endpoint": "/api/scrape/simple?search_term=frontend developer&location=Austin, TX&site_name=indeed,linkedin&results_wanted=15"
            },
            {
                "name": "Export to CSV",
                "description": "Get results as CSV file",
                "method": "POST",
                "endpoint": "/api/scrape",
                "body": {
                    "site_name": ["indeed"],
                    "search_term": "full stack developer",
                    "location": "Boston, MA",
                    "results_wanted": 50,
                    "output_format": "csv"
                }
            },
            {
                "name": "Google Jobs Search",
                "description": "Search using Google Jobs with custom search term",
                "method": "POST",
                "endpoint": "/api/scrape",
                "body": {
                    "site_name": ["google"],
                    "google_search_term": "machine learning engineer jobs near San Francisco, CA since yesterday",
                    "results_wanted": 30
                }
            },
            {
                "name": "International Search - India",
                "description": "Search for jobs in India using Naukri",
                "method": "POST",
                "endpoint": "/api/scrape",
                "body": {
                    "site_name": ["naukri", "indeed"],
                    "search_term": "software developer",
                    "location": "Bangalore",
                    "country_indeed": "India",
                    "results_wanted": 25
                }
            }
        ]
    }
# Root redirect (since docs is at /)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/favicon.ico", status_code=307)