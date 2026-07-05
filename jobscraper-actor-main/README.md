# 🔍 JobSpy API - Job Scraping Service

[![API Status](https://img.shields.io/badge/API-Live-success)](https://jobscrape-actor.vercel.app)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-blue)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.8+-yellow)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> **Powerful job scraping API that aggregates jobs from LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, and more. Search millions of jobs in seconds.**

🌐 **Live API:** [https://jobscrape-actor.vercel.app](https://jobscrape-actor.vercel.app)  
📖 **API Documentation:** [https://jobscrape-actor.vercel.app/docs](https://jobscrape-actor.vercel.app/docs)

---

## ✨ Features

- 🌍 **Multi-Platform Support** - Scrape from 8+ major job boards simultaneously
- 🚀 **Fast & Reliable** - Built on FastAPI for high performance
- 📊 **Multiple Formats** - Export results as JSON, CSV, or Excel
- 🔍 **Advanced Filtering** - Filter by location, remote, job type, salary, and more
- 🌐 **Global Coverage** - Support for 40+ countries
- 📝 **Rich Data** - Get job titles, descriptions, salaries, companies, and more
- 🔒 **CORS Enabled** - Ready for frontend integration
- 📚 **Interactive Docs** - Swagger UI for easy API exploration

---

## 🎯 Supported Job Boards

| Platform | Description |
|----------|-------------|
| **LinkedIn** | Professional network with quality job postings |
| **Indeed** | Large job aggregator with extensive listings |
| **ZipRecruiter** | US/Canada focused job board |
| **Glassdoor** | Jobs with company reviews and salary data |
| **Google Jobs** | Aggregated job listings from Google |
| **Bayt** | Middle East focused job portal |
| **Naukri** | India's leading job portal |
| **BDJobs** | Bangladesh job portal |

---

## 🚀 Quick Start

### Try it Now (No Setup Required)

```bash
curl -X POST "https://jobscrape-actor.vercel.app/api/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "site_name": ["indeed", "linkedin"],
    "search_term": "python developer",
    "location": "San Francisco, CA",
    "results_wanted": 20
  }'
```

### Python Example

```python
import requests

response = requests.post(
    "https://jobscrape-actor.vercel.app/api/scrape",
    json={
        "site_name": ["indeed", "linkedin", "glassdoor"],
        "search_term": "software engineer",
        "location": "New York, NY",
        "results_wanted": 50,
        "hours_old": 72,
        "job_type": "fulltime"
    }
)

jobs = response.json()
print(f"Found {jobs['total_results']} jobs")

# Access job details
for job in jobs['jobs']:
    print(f"{job['title']} at {job['company']}")
```

### JavaScript/Node.js Example

```javascript
const response = await fetch('https://jobscrape-actor.vercel.app/api/scrape', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    site_name: ['indeed', 'linkedin'],
    search_term: 'react developer',
    location: 'Remote',
    results_wanted: 30,
    is_remote: true
  })
});

const data = await response.json();
console.log(`Found ${data.total_results} jobs!`);
```

---

## 📡 API Endpoints

### Main Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scrape` | POST | Main job scraping endpoint with full options |
| `/api/scrape/simple` | GET | Simplified endpoint for quick searches |
| `/api/sites` | GET | List all supported job sites |
| `/api/countries` | GET | List all supported countries |
| `/api/examples` | GET | Get example API requests |
| `/api/health` | GET | API health check |
| `/docs` | GET | Interactive API documentation (Swagger UI) |

### Quick GET Request

```bash
# Simple search - just use URL parameters
https://jobscrape-actor.vercel.app/api/scrape/simple?search_term=developer&site_name=indeed&results_wanted=5
```

---

## 📋 Request Parameters

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `site_name` | array | all | Job sites to scrape (e.g., ["indeed", "linkedin"]) |
| `search_term` | string | null | Job search term (e.g., "software engineer") |
| `location` | string | null | Job location (e.g., "San Francisco, CA") |
| `results_wanted` | integer | 20 | Number of results per site (1-100) |
| `is_remote` | boolean | false | Filter for remote jobs only |
| `job_type` | string | null | Job type: fulltime, parttime, internship, contract |
| `distance` | integer | 50 | Search radius in miles (0-200) |
| `hours_old` | integer | null | Filter jobs posted within N hours |

### Advanced Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `country_indeed` | string | "USA" | Country for Indeed/Glassdoor searches |
| `easy_apply` | boolean | null | Filter for easy apply jobs (LinkedIn) |
| `linkedin_company_ids` | array | null | Filter by specific LinkedIn company IDs |
| `description_format` | string | "markdown" | Format: markdown or html |
| `enforce_annual_salary` | boolean | false | Convert all salaries to annual format |
| `output_format` | string | "json" | Output format: json, csv, or excel |
| `offset` | integer | 0 | Pagination offset |

---

## 📊 Response Format

```json
{
  "success": true,
  "message": "Successfully scraped 42 jobs",
  "total_results": 42,
  "timestamp": "2025-10-09T12:00:00.000Z",
  "search_parameters": {
    "site_name": ["indeed", "linkedin"],
    "search_term": "python developer",
    "location": "San Francisco, CA"
  },
  "jobs": [
    {
      "site": "indeed",
      "title": "Senior Python Developer",
      "company": "Tech Corp",
      "location": "San Francisco, CA",
      "job_type": "fulltime",
      "date_posted": "2025-10-08",
      "salary_source": "indeed",
      "interval": "yearly",
      "min_amount": 120000,
      "max_amount": 160000,
      "currency": "USD",
      "is_remote": false,
      "job_url": "https://...",
      "description": "We are looking for...",
      "benefits": "Health insurance, 401k, Remote work options",
      "company_url": "https://www.techcorp.com",
      "company_industry": "Technology",
      "company_num_employees": "1000-5000"
    }
  ]
}
```

---

## 🌍 Supported Countries

USA, Canada, UK, Australia, India, Germany, France, Spain, Italy, Netherlands, Belgium, Switzerland, Austria, Sweden, Norway, Denmark, Finland, Ireland, Poland, Brazil, Mexico, Argentina, Chile, Colombia, Singapore, Hong Kong, Japan, South Korea, UAE, Saudi Arabia, Egypt, South Africa, New Zealand, Philippines, Malaysia, Indonesia, Thailand, Vietnam, Pakistan, Bangladesh, Turkey, Israel

---

## 🛠️ Use Cases & Integrations

### 1. 🤖 **AI Agents & LangChain**

Integrate JobSpy API as a tool for AI agents to search and analyze job market data:

```python
from langchain.tools import Tool
from langchain.agents import initialize_agent
import requests

def search_jobs(query: str) -> str:
    """Search for jobs using JobSpy API"""
    response = requests.post(
        "https://jobscrape-actor.vercel.app/api/scrape",
        json={
            "search_term": query,
            "results_wanted": 10,
            "site_name": ["indeed", "linkedin"]
        }
    )
    return response.json()

job_search_tool = Tool(
    name="JobSearch",
    func=search_jobs,
    description="Search for job listings across multiple platforms"
)

# Add to your LangChain agent
agent = initialize_agent([job_search_tool], llm, agent="zero-shot-react-description")
```

### 2. 🔄 **N8N Workflow Automation**

Create powerful job search automation workflows:

1. **HTTP Request Node** → JobSpy API
2. **Filter Node** → Filter by salary/requirements
3. **Slack/Email Node** → Send notifications
4. **Google Sheets Node** → Save results

**N8N Configuration:**

```json
{
  "method": "POST",
  "url": "https://jobscrape-actor.vercel.app/api/scrape",
  "body": {
    "site_name": ["indeed", "linkedin"],
    "search_term": "{{ $json.job_title }}",
    "location": "{{ $json.location }}",
    "results_wanted": 50
  }
}
```

### 3. 📊 **Job Market Analytics Dashboard**

Build real-time job market dashboards with:
- **Streamlit** - Quick data visualization
- **Tableau** - Advanced analytics
- **Power BI** - Business intelligence
- **Grafana** - Monitoring job trends

### 4. 🔔 **Job Alert Systems**

Create personalized job alert systems:

```python
# Schedule this with cron/celery
def daily_job_alert():
    jobs = search_jobs("senior python developer", remote=True)
    new_jobs = filter_new_jobs(jobs)
    if new_jobs:
        send_email_notification(new_jobs)
```

### 5. 🤝 **Recruitment CRM Integration**

Integrate with recruitment platforms:
- **Bullhorn**
- **Greenhouse**
- **Lever**
- **Workable**

### 6. 📱 **Mobile Apps & Chrome Extensions**

Build job search applications:
- React Native mobile apps
- Chrome extensions for job tracking
- Progressive Web Apps (PWA)

### 7. 🔬 **Research & Data Analysis**

Perfect for:
- Job market research
- Salary trend analysis
- Skills demand analysis
- Company hiring patterns
- Geographic job distribution

### 8. 🎓 **Career Counseling Platforms**

Help students and job seekers:
- Career path recommendations
- Market demand analysis
- Skill gap identification
- Salary expectations

### 9. ⚡ **Zapier & Make.com Automations**

Connect with 5000+ apps:
- Trigger job searches based on events
- Auto-apply to matching positions
- Send Slack notifications for new jobs
- Update Airtable with job data

### 10. 🎯 **Competitor Analysis Tools**

Monitor competitor hiring:
- Track companies hiring patterns
- Analyze job requirements
- Identify market trends
- Plan competitive strategies

---

## 🔧 Local Development

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/Amon20044/jobscraper-actor.git
cd jobscraper-actor

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --port 5001
```

The API will be available at `http://localhost:5001`

### Dependencies

```txt
fastapi
uvicorn[standard]
pandas
openpyxl
python-jobspy
python-multipart
pydantic
```

---

## 🚀 Deployment

### Vercel (Recommended)

1. Fork this repository
2. Import to Vercel
3. Deploy automatically

### Other Platforms

- **Railway** - One-click deploy
- **Render** - Free tier available
- **Heroku** - Classic PaaS
- **AWS Lambda** - Serverless
- **Google Cloud Run** - Container-based
- **Docker** - Containerized deployment

---

## 📝 Example Use Cases

### 1. Remote Job Finder

```python
response = requests.post(
    "https://jobscrape-actor.vercel.app/api/scrape",
    json={
        "search_term": "python developer",
        "is_remote": True,
        "hours_old": 24,
        "results_wanted": 50,
        "site_name": ["indeed", "linkedin", "zip_recruiter"]
    }
)
```

### 2. Salary Research

```python
response = requests.post(
    "https://jobscrape-actor.vercel.app/api/scrape",
    json={
        "search_term": "data scientist",
        "location": "New York, NY",
        "enforce_annual_salary": True,
        "results_wanted": 100,
        "output_format": "csv"  # Export to CSV for analysis
    }
)
```

### 3. International Job Search

```python
response = requests.post(
    "https://jobscrape-actor.vercel.app/api/scrape",
    json={
        "site_name": ["naukri", "indeed"],
        "search_term": "software engineer",
        "location": "Bangalore",
        "country_indeed": "India",
        "results_wanted": 30
    }
)
```

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [python-jobspy](https://github.com/speedyapply/JobSpy) by [@cullenwatson](https://pypi.org/user/cullenwatson)
- Powered by [FastAPI](https://fastapi.tiangolo.com/)
- Deployed on [Vercel](https://vercel.com/)

---

## 👤 Maintainer

**Amon Sharma**
- GitHub: [@Amon20044](https://github.com/Amon20044)
- LinkedIn: [Amon Sharma](https://www.linkedin.com/in/amon-sharma/)

---

## 🌟 Support

If you find this project useful, please consider:
- ⭐ Starring the repository
- 🍴 Forking and contributing
- 🐛 Reporting issues
- 📢 Sharing with others

---

## 📞 Contact & Support

- 🌐 Website: [https://jobscrape-actor.vercel.app](https://jobscrape-actor.vercel.app)
- 📖 Documentation: [https://jobscrape-actor.vercel.app/docs](https://jobscrape-actor.vercel.app/docs)
- 🐛 Issues: [GitHub Issues](https://github.com/Amon20044/jobscraper-actor/issues)

---

<div align="center">

**Made with ❤️ by [Amon Sharma](https://github.com/Amon20044)**

[![API Status](https://img.shields.io/badge/API-Live-success)](https://jobscrape-actor.vercel.app)

</div>