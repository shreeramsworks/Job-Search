# Project Documentation: Job-Search Aggregator & API Service

This document provides a comprehensive technical overview, deployment guide, API specification, and troubleshooting manual for the **Job-Search** application.

---

## 📖 1. System Overview & Architecture

The **Job-Search** application is a self-hosted API gateway that performs real-time job scraping across multiple job boards concurrently. It wraps raw scraper engines inside a clean, modern RESTful FastAPI service suitable for automation workflows (like n8n, Zapier, or custom dashboards).

### Directory & Component Structure
```text
Job-Search/
├── .gitignore                  # Standard Python & environment Git exclusions
├── README.md                   # Quick Start guide
├── project_documentation.md    # This detailed system documentation
├── JobSpy-main/                # Customized JobSpy library source
│   ├── jobspy/                 # Core scraping logic
│   │   ├── google/             # Google Jobs scraper implementation
│   │   ├── naukri/             # Naukri scraper implementation
│   │   ├── indeed/             # Indeed scraper implementation
│   │   ├── linkedin/           # LinkedIn scraper implementation
│   │   ├── glassdoor/          # Glassdoor scraper implementation
│   │   ├── ziprecruiter/       # ZipRecruiter scraper implementation
│   │   └── util.py             # Helper utilities and session managers
│   └── pyproject.toml          # Library configurations
├── Scrapling-main/             # Customized Scrapling engine source
│   └── Scrapling-main/
│       └── scrapling/          # Underlying stealth browser, fetchers, & request modules
└── jobscraper-actor-main/      # FastAPI Server API layer
    ├── main.py                 # FastAPI application routes, schemas, and endpoints
    ├── requirements.txt        # Server dependency list
    └── vercel.json             # Vercel Serverless hosting config
```

### Execution Flow
1. **Request Intake**: An external client (e.g. n8n) sends a POST request with parameters (like search terms, location, job type) to the FastAPI server `/api/scrape`.
2. **Path Resolution**: `main.py` prepends the local `JobSpy-main` and `Scrapling-main` directories to `sys.path` to load the customized local versions instead of vanilla packages.
3. **Execution**: The server calls the `scrape_jobs()` function inside `jobspy`.
4. **Stealth Requesting**: `jobspy` utilizes `scrapling`'s `StealthySession` to bypass anti-bot check walls (like Cloudflare, cookies, and fingerprinting).
5. **Data Wrangling**: Scraped jobs are loaded into a Pandas DataFrame, converted into clean dictionaries, and returned as a JSON structure (or CSV/Excel format).

---

## 📡 2. API Endpoint Specifications

All endpoints are hosted locally by default on port `5001`.

### A. Health Check
* **Route**: `GET /api/health`
* **Description**: Verifies if the FastAPI application is alive and responding.
* **Example curl**:
  ```bash
  curl http://127.0.0.1:5001/api/health
  ```
* **Success Response (200 OK)**:
  ```json
  {
    "status": "healthy",
    "service": "JobSpy API",
    "timestamp": "2026-07-05T07:26:29.941685",
    "version": "2.0.0"
  }
  ```

---

### B. Aggregate Scrape (Main Endpoint)
* **Route**: `POST /api/scrape`
* **Description**: Queries chosen job boards concurrently and aggregates the data.
* **Headers**: `Content-Type: application/json`
* **Request JSON Schema**:
  ```json
  {
    "site_name": [],
    "search_term": "ai engineer",
    "google_search_term": "automation",
    "hours_old": 48,
    "results_wanted": 20,
    "country_indeed": "USA",
    "is_remote": true,
    "enforce_annual_salary": true,
    "easy_apply": true,
    "description_format": "markdown",
    "output_format": "json"
  }
  ```
  
  #### Request Parameter Definitions:
  * `site_name` (*Array of Strings*, Optional): Target sites to scrape. Supported: `["indeed", "linkedin", "zip_recruiter", "glassdoor", "google", "bayt", "naukri", "bdjobs"]`. If `null` or `[]` (empty list), the engine defaults to querying **all supported job boards**.
  * `search_term` (*String*, Optional): Search query keyword (e.g. `"python developer"`).
  * `google_search_term` (*String*, Optional): Specific custom search query for the Google Jobs scraper node.
  * `location` (*String*, Optional): Location filter (e.g. `"San Francisco, CA"`, `"Remote"`).
  * `is_remote` (*Boolean*, Default: `false`): Filter for remote jobs only.
  * `easy_apply` (*Boolean*, Optional): Filter for jobs with the easy apply option.
  * `job_type` (*String*, Optional): Employment type. Options: `"fulltime"`, `"parttime"`, `"internship"`, `"contract"`.
  * `results_wanted` (*Integer*, Default: `20`): Max results to fetch per board (Range: `1-100`).
  * `country_indeed` (*String*, Default: `"USA"`): Target country code for Indeed/Glassdoor.
  * `linkedin_fetch_description` (*Boolean*, Default: `true`): Set to `false` to speed up requests (does not pull the full description body).
  * `enforce_annual_salary` (*Boolean*, Default: `false`): Normalize all salaries to an annual format.
  * `output_format` (*String*, Default: `"json"`): Supported: `"json"`, `"csv"`, `"excel"`.

* **Success Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Successfully scraped 2 jobs",
    "total_results": 2,
    "timestamp": "2026-07-06T13:48:00Z",
    "search_parameters": {
      "search_term": "ai engineer",
      "google_search_term": "automation",
      "hours_old": 48,
      "results_wanted": 20,
      "country_indeed": "USA",
      "is_remote": true,
      "enforce_annual_salary": true,
      "easy_apply": true
    },
    "jobs": [
      {
        "site": "linkedin",
        "job_url": "https://www.linkedin.com/jobs/view/4429330149",
        "title": "Machine Learning Engineer - Agentic AI",
        "company": "5V Tech",
        "location": "New York, United States",
        "date_posted": "2026-07-06T00:00:00.000",
        "posted_in_hours": 0.0,
        "job_type": "fulltime",
        "is_remote": false,
        "job_level": "mid-senior level",
        "job_function": "Engineering and Information Technology",
        "description": "...",
        "company_industry": "Software Development, Computer Hardware Manufacturing, and Artificial Intelligence"
      }
    ]
  }
  ```

---

### C. Simple Scrape (GET Request)
* **Route**: `GET /api/scrape/simple`
* **Description**: A simplified search utility for testing queries straight in web browsers or simple script queries.
* **Query Parameters**:
  * `search_term` (String, Required)
  * `location` (String, Optional)
  * `site_name` (String, Optional - comma-separated list, e.g. `indeed,linkedin`)
  * `results_wanted` (Integer, Default: `20`)
  * `is_remote` (Boolean, Default: `false`)
* **Example curl**:
  ```bash
  curl "http://127.0.0.1:5001/api/scrape/simple?search_term=python&site_name=indeed&results_wanted=5"
  ```

---

## 🛠️ 3. Installation & Run Guidelines

### Local Environment Setup (Windows/macOS/Linux)
1. **Navigate to the server directory**:
   ```bash
   cd jobscraper-actor-main
   ```
2. **Create a python virtual environment**:
   ```bash
   python3 -m venv venv
   ```
3. **Activate the environment**:
   * **Windows Powershell**: `.\venv\Scripts\Activate.ps1`
   * **Windows CMD**: `venv\Scripts\activate`
   * **Linux/macOS**: `source venv/bin/activate`
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Run the server**:
   ```bash
   python -m uvicorn main:app --reload --port 5001
   ```

---

## ☁️ 4. VPS Production Deployment (e.g. Contabo)

To host the API permanently on a remote Ubuntu/Debian server:

### Step 1: Clone Repository
```bash
cd /var/www
git clone https://github.com/shreeramsworks/Job-Search.git
cd Job-Search/jobscraper-actor-main
```

### Step 2: Install Python & Configure Virtual Env
```bash
sudo apt update
sudo apt install python3-pip python3-venv -y

# Create virtual environment
python3 -m venv venv
# Install dependencies directly using the sandbox pip
./venv/bin/pip install -r requirements.txt
```

### Step 3: Run as a background systemd service
To ensure the server starts on boot and restarts automatically if it crashes:

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/jobspy-api.service
   ```
2. Paste this configuration:
   ```ini
   [Unit]
   Description=JobSpy FastAPI Server
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/var/www/Job-Search/jobscraper-actor-main
   ExecStart=/var/www/Job-Search/jobscraper-actor-main/venv/bin/uvicorn main:app --host 0.0.0.0 --port 5001
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   *Note: `--host 0.0.0.0` is used so the API is reachable across Docker container gateways.*
3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start jobspy-api
   sudo systemctl enable jobspy-api
   ```
4. Verify the status:
   ```bash
   sudo systemctl status jobspy-api
   ```

---

## 🤖 5. n8n Workflow Integration

When integrating with n8n nodes:

1. Add an **HTTP Request** node.
2. Select **Method**: `POST`.
3. Set the **URL**:
   * **If n8n and the API run on the same VPS, but n8n is inside Docker**:
     Use the host gateway: `http://172.17.0.1:5001/api/scrape`
   * **If n8n and the API run on the same VPS, and both are native (no Docker)**:
     Use localhost: `http://127.0.0.1:5001/api/scrape`
   * **If n8n is on a different server (e.g. n8n is on server A, API is on server B)**:
     Use the public hostname: `http://vmi3318933.contaboserver.net:5001/api/scrape`
4. Toggle **Send Body** to `On`.
5. Set **Body Content Type** to `JSON`.
6. Insert the search payload in the **Body** field.

---

## 🔍 6. Troubleshooting & Common Issues

### Issue 1: `status=203/EXEC` systemd error
* **Symptom**: `Failed to start jobspy-api.service` with exit code `203/EXEC`.
* **Reason**: Systemd cannot find the `uvicorn` executable at `/var/www/Job-Search/jobscraper-actor-main/venv/bin/uvicorn`.
* **Fix**: Ensure that the `venv` directory actually exists and was created with `python3 -m venv venv` inside `/var/www/Job-Search/jobscraper-actor-main`. Re-run `pip install -r requirements.txt` inside that sandbox.

### Issue 2: `Unit jobspy-api.service is masked`
* **Symptom**: Systemd refuses to start the service, listing it as `masked`.
* **Reason**: The service file has been symlinked to `/dev/null` by systemd, blocking execution.
* **Fix**: Run `sudo systemctl unmask jobspy-api`. This will delete the block. Next, recreate the file using `sudo nano /etc/systemd/system/jobspy-api.service` and restart systemd (`sudo systemctl daemon-reload` and `sudo systemctl start jobspy-api`).

### Issue 3: `curl: (7) Failed to connect to 127.0.0.1 port 5001: Connection refused`
* **Symptom**: Checking health check endpoint fails.
* **Reason**: The FastAPI app is not running, or uvicorn crashed immediately during boot.
* **Fix**: Run `sudo journalctl -u jobspy-api --no-pager -n 50` to read the python traceback. This will tell you if you have python import errors, missing libraries, or syntax problems.
