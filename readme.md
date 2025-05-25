A comprehensive job search agent using Streamlit that connects to Qualcomm AI Playground and uses SERP API for job searching. This will include email functionality for daily job alerts.


🔧 How to Generate a Gmail App Password
Go to your Google Account: https://myaccount.google.com

On the left, select Security.

Make sure 2-Step Verification is enabled.

Scroll to "Signing in to Google" > Click App Passwords.

Sign in again if prompted.

Under "Select app", choose Mail, and under "Select device", choose Other and name it (e.g., “Email Alert Script”).

Click Generate.

You’ll see a 16-character password – copy and use this in your email script/app.



I've created a comprehensive Job Search Agent with Streamlit UI that integrates with Qualcomm AI Playground and SERP API. Here are the key features:

## 🌟 Key Features

**Job Search & AI Analysis:**
- Searches for jobs posted in the last 24 hours using SERP API
- Uses Qualcomm AI models to analyze and rank jobs based on user requirements
- Provides relevance scores and match explanations for each job

**Email Alert System:**
- Set up daily email alerts for job matches
- HTML-formatted emails with top 10 job recommendations
- Test email functionality to verify setup

**User Interface:**
- Clean, intuitive Streamlit interface
- Configurable AI model selection
- Expandable job listings with detailed information

## 🔧 Setup Requirements

1. **SERP API Key**: Get from [serpapi.com](https://serpapi.com)
2. **Gmail App Password**: For sending email alerts (not your regular password)
3. **Qualcomm AI Playground**: Ensure `IMAGINE_API_KEY` is configured

## 📦 Required Dependencies

```bash
pip install streamlit requests imagine-ai schedule sqlite3 smtplib email
```

## 🚀 How to Run

1. Save the code as `my_job_search_agent.py`
2. Set your environment variables or configure keys in the sidebar
3. Run: `streamlit run my_job_search_agent.py`

## 🔄 How It Works

1. **Search**: Uses SERP API to find recent job postings
2. **Analyze**: Qualcomm AI ranks jobs based on user requirements
3. **Alert**: Stores user preferences and can send daily email summaries
4. **Database**: SQLite stores user alert preferences locally

The application provides both immediate job search results and the ability to set up ongoing daily alerts. The AI integration helps prioritize jobs that best match user requirements, making job hunting more efficient and targeted.

Would you like me to explain any specific part of the implementation or add additional features?
