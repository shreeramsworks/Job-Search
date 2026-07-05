# 🔍 Job-Search: High-Performance Job Scraper & API Server

A powerful, production-ready job scraping service that aggregates listings from major boards including **LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs, Bayt, and Naukri** in real-time. 

This repository contains the FastAPI server wrapper and the customized source codes for the scraper libraries (`JobSpy` and `Scrapling`) to ensure reliable local execution with maximum customization.

---

## 📂 Repository Architecture

```text
Job-Search/
├── .gitignore                  # Standard Python & environment Git exclusions
├── README.md                   # This comprehensive usage guide
├── JobSpy-main/                # Customized JobSpy scraper library source
│   └── jobspy/                 # Core scraping controllers (LinkedIn, Indeed, Glassdoor, etc.)
├── Scrapling-main/             # Customized Scrapling engine source
│   └── Scrapling-main/
│       └── scrapling/          # Underlying stealth browser & fetcher core
└── jobscraper-actor-main/      # FastAPI Server API layer
    ├── main.py                 # FastAPI application and route endpoints
    ├── requirements.txt        # Server dependency list
    └── vercel.json             # Optional configurations for Vercel deployment
```

---

## ⚡ Features

* **Multi-Platform Scraping**: Queries multiple job boards concurrently.
* **FastAPI Wrapper**: Provides clean REST API endpoints (`/api/scrape`, `/api/scrape/simple`, `/api/health`).
* **Format Flexibility**: Exports search results into **JSON**, **CSV**, or **Excel** formats dynamically.
* **n8n & Automations Ready**: Configured for webhook automation nodes.
* **Anti-Blocking**: Built-in stealth requests via customized local Scrapling fetchers.
* **Interactive API Docs**: Real-time Swagger UI at `/docs`.

---

## 🚀 Local Installation & Quick Start

### Prerequisites
* **Python 3.8 to 3.12**
* **pip** (Python package installer)

### Step 1: Clone the repository or navigate to the folder
```bash
git clone https://github.com/shreeramsworks/Job-Search.git
cd Job-Search
```

### Step 2: Set up a virtual environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate on Windows (cmd)
venv\Scripts\activate
# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Activate on Linux/macOS
source venv/bin/activate
```

### Step 3: Install dependencies
Navigate to the FastAPI server directory and install the requirements:
```bash
cd jobscraper-actor-main
pip install -r requirements.txt
```

### Step 4: Run the API Server
Start the Uvicorn development server:
```bash
python -m uvicorn main:app --reload --port 5001
```
The server will boot and run on `http://127.0.0.1:5001`. You can access the interactive API docs at [http://127.0.0.1:5001/docs](http://127.0.0.1:5001/docs).

---

## 📡 API Endpoints

### 1. Scrape Jobs (POST `/api/scrape`)
The main endpoint to scrape jobs from one or more sites.

* **Headers**: `Content-Type: application/json`
* **JSON Body Parameters**:
  
  | Parameter | Type | Default | Description |
  | :--- | :--- | :--- | :--- |
  | `site_name` | Array | `null` | Target sites. e.g. `["indeed", "linkedin", "glassdoor", "zip_recruiter", "google", "bayt", "naukri"]`. If null, searches all. |
  | `search_term` | String | `null` | Search terms (e.g. `"react developer"`). |
  | `location` | String | `null` | Geographic location (e.g. `"San Francisco, CA"`, `"Remote"`). |
  | `results_wanted` | Integer | `20` | Max results to fetch per board (1 to 100). |
  | `is_remote` | Boolean | `false` | Restrict search to remote roles only. |
  | `job_type` | String | `null` | Options: `"fulltime"`, `"parttime"`, `"internship"`, `"contract"`. |
  | `hours_old` | Integer | `null` | Posted within the last N hours (e.g., `24` or `48`). |
  | `country_indeed`| String | `"USA"` | Country selection for Indeed/Glassdoor (e.g., `"India"`, `"Canada"`, `"UK"`). |
  | `linkedin_fetch_description`| Boolean | `true` | Set to `false` to speed up requests (does not pull the full description body). |
  | `enforce_annual_salary` | Boolean | `false` | Normalize salary outputs to an annual rate. |
  | `output_format` | String | `"json"` | Outputs: `"json"`, `"csv"`, or `"excel"`. |

* **Example Request Payload**:
  ```json
  {
    "site_name": ["indeed", "linkedin", "glassdoor"],
    "search_term": "react developer",
    "location": "Remote",
    "is_remote": true,
    "job_type": "fulltime",
    "hours_old": 48,
    "results_wanted": 30,
    "country_indeed": "USA",
    "linkedin_fetch_description": false,
    "enforce_annual_salary": true
  }
  ```

* **Example JSON Response**:
  ```json
  {
    "success": true,
    "message": "Successfully scraped 30 jobs",
    "total_results": 30,
    "timestamp": "2026-07-05T07:00:00Z",
    "search_parameters": { ... },
    "jobs": [
      {
        "site": "linkedin",
        "title": "Senior React Developer",
        "company": "Tech Corp Inc",
        "location": "Remote, US",
        "job_url": "https://www.linkedin.com/jobs/view/...",
        "min_amount": 120000,
        "max_amount": 150000,
        "currency": "USD"
      }
    ]
  }
  ```

---

## 🤖 n8n Workflow Integration

### Local Testing (Using ngrok tunnel)
If n8n is running in the cloud or on a remote VPS (like Contabo) but the API is running on your local computer:

1. Start ngrok tunnel locally on port 5001:
   ```bash
   ngrok http 5001
   ```
2. Copy the public URL generated (e.g. `https://xxxx.ngrok-free.app`).
3. Set your **n8n HTTP Request node** to:
   * **Method**: `POST`
   * **URL**: `https://xxxx.ngrok-free.app/api/scrape`
   * **Body Type**: `JSON`
   * **Body**: Paste your request payload.

---

## 🛡️ VPS Deployment (Contabo / Linux VPS)

To deploy this permanently on your VPS so n8n can access it 24/7 with zero latency:

### Step 1: Upload codebase
Upload or clone the repository to `/var/www/Job-Search` on your VPS.

### Step 2: Configure System Dependencies
SSH into the server and install prerequisites:
```bash
sudo apt update
sudo apt install python3-pip python3-venv -y
```

### Step 3: Setup Virtual Environment
```bash
cd /var/www/Job-Search/jobscraper-actor-main
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Run as a background systemd service
To ensure the scraper service starts automatically when the VPS reboots and stays running:

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/jobspy-api.service
   ```
2. Paste the following configuration:
   ```ini
   [Unit]
   Description=JobSpy FastAPI Server
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/var/www/Job-Search/jobscraper-actor-main
   ExecStart=/var/www/Job-Search/jobscraper-actor-main/venv/bin/uvicorn main:app --host 127.0.0.1 --port 5001
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
3. Reload, start, and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start jobspy-api
   sudo systemctl enable jobspy-api
   ```

### Step 5: Connecting n8n
* **If n8n is running directly on the VPS (same system)**:
  Set the HTTP Request URL to `http://127.0.0.1:5001/api/scrape`.
* **If n8n is running inside Docker on the VPS**:
  Change `--host 127.0.0.1` to `--host 0.0.0.0` in the systemd configuration, restart the service, and set the n8n HTTP Node URL to `http://172.17.0.1:5001/api/scrape` (using the Docker gateway IP).

---

## 📄 License
This project is licensed under the MIT License.
