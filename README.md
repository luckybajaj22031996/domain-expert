# 📰 Domain Expert

> A fully automated AI newsletter agent that delivers a daily insurance briefing to your inbox — every morning at 7:30am IST.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Claude](https://img.shields.io/badge/Powered%20by-Claude%20AI-blueviolet?logo=anthropic)
![GitHub Actions](https://img.shields.io/badge/Scheduled-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ What It Does

Domain Expert wakes up every day, scans the latest Indian insurance news, curates the most relevant stories, generates an insightful concept, writes a full newsletter — and sends it straight to your inbox. Zero manual effort.

Built for **insurance PMs, BAs, and domain enthusiasts** in India who want to stay sharp without spending an hour on news aggregators.

---

## 🔄 How It Works

```
📡 Research         Fetches top insurance stories from NewsAPI
      ↓              (IRDAI, LIC, health insurance, premiums)
✂️  Curation        Claude picks the 5 most relevant stories
      ↓              and writes a 2-line summary for each
💡 Concept          Claude generates a daily insurance concept
      ↓              to learn (definition + real-world example)
✍️  Writer          Claude assembles the full newsletter copy
      ↓              (60-second intro + top stories + concept)
🎨 Render           Jinja2 renders the HTML email template
      ↓
📬 Send             Delivered to your inbox via Gmail SMTP
```

---

## 🗂️ Project Structure

```
domain-expert/
├── .github/
│   └── workflows/
│       └── daily_newsletter.yml   # GitHub Actions cron (7:30am IST)
├── insurance-brief/
│   ├── agents/
│   │   ├── research.py            # NewsAPI story fetcher
│   │   ├── curation.py            # Claude story curator
│   │   ├── concept.py             # Claude concept generator
│   │   ├── writer.py              # Claude newsletter writer
│   │   └── mailer.py              # Gmail SMTP sender
│   ├── config/
│   │   └── sources.py
│   ├── templates/
│   │   └── email.html             # Jinja2 HTML email template
│   ├── main.py                    # Pipeline orchestrator
│   ├── scheduler.py               # Local daily scheduler (alt to GH Actions)
│   ├── requirements.txt
│   └── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/luckybajaj22031996/domain-expert.git
cd domain-expert/insurance-brief
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```

Fill in your `.env`:

| Key | Where to get it |
|-----|----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | [Google App Passwords](https://myaccount.google.com/apppasswords) |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) — free tier |

---

## 🚀 Running

### Run once manually
```bash
cd insurance-brief
python main.py
```

### Run with demo data (no API calls for research)
```bash
python main.py --demo
```

### Run the local scheduler (keeps process alive, fires daily at 7:30am)
```bash
python scheduler.py
```

---

## ☁️ GitHub Actions (Recommended)

The workflow at `.github/workflows/daily_newsletter.yml` runs automatically every day at **7:30am IST** (2:00am UTC).

Add these four secrets to your repo under **Settings → Secrets and variables → Actions**:

```
ANTHROPIC_API_KEY
GMAIL_ADDRESS
GMAIL_APP_PASSWORD
NEWSAPI_KEY
```

You can also trigger a run manually anytime from the **Actions** tab → **Daily Newsletter** → **Run workflow**.

---

## 🛠️ Built With

- [Anthropic Claude](https://anthropic.com) — curation, concept generation, and writing
- [NewsAPI](https://newsapi.org) — real-time news aggregation
- [Jinja2](https://jinja.palletsprojects.com) — HTML email templating
- [smtplib](https://docs.python.org/3/library/smtplib.html) — Gmail SMTP delivery
- [schedule](https://schedule.readthedocs.io) — local cron-style scheduling
- [GitHub Actions](https://github.com/features/actions) — cloud automation

---

*Built with ❤️ for the Indian insurance community.*
