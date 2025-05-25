import streamlit as st
import requests
import json
from imagine import ImagineClient, ModelType
from datetime import datetime, timedelta

from typing import List, Dict, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import threading
import time
import sqlite3
import os
from dataclasses import dataclass
import re
os.environ['IMAGINE_API_KEY'] = "2d8c76a5-8c44-4b4e-8d85-07850f51ff2a"
os.environ['IMAGINE_API_ENDPOINT'] = "https://aisuite.cirrascale.com/apis/v2"
os.environ['SERP_API_KEY'] ="db518d1638534c7453826aff15ba9170a3d231f63bf459e329f99dabae03c4f8"
# Initialize the Qualcomm AI client
@st.cache_resource
def initialize_ai_client():
    client = ImagineClient(timeout=240)
    return client


@dataclass
class UserSubscription:
    email: str
    job_title: str
    location: str
    created_at: str
    is_active: bool = True

class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, email: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = email
        self.password = password
    
    def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send HTML email"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email, self.password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            st.error(f"Email sending failed: {str(e)}")
            return False

class DatabaseManager:
    def __init__(self, db_path: str = "job_subscriptions.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                job_title TEXT NOT NULL,
                location TEXT,
                created_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_subscription(self, subscription: UserSubscription) -> bool:
        """Add new subscription"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO subscriptions (email, job_title, location, created_at, is_active)
                VALUES (?, ?, ?, ?, ?)
            ''', (subscription.email, subscription.job_title, subscription.location, 
                  subscription.created_at, subscription.is_active))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Database error: {str(e)}")
            return False
    
    def get_active_subscriptions(self) -> List[UserSubscription]:
        """Get all active subscriptions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT email, job_title, location, created_at FROM subscriptions WHERE is_active = 1')
        rows = cursor.fetchall()
        
        conn.close()
        
        return [UserSubscription(email=row[0], job_title=row[1], location=row[2], created_at=row[3]) 
                for row in rows]
    
    def deactivate_subscription(self, email: str, job_title: str) -> bool:
        """Deactivate subscription"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE subscriptions SET is_active = 0 
                WHERE email = ? AND job_title = ?
            ''', (email, job_title))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Database error: {str(e)}")
            return False

class JobSearchAgent:
    def __init__(self, serp_api_key: str, imagine_api_key: str, email_service: EmailService = None,model:str="Llama-3.1-8B" ):
        self.serp_api_key = serp_api_key
        self.imagine_api_key = imagine_api_key
        self.email_service = email_service
        self.db_manager = DatabaseManager()
        
        # Configure LLM
        
        self.model = model
    
    def search_jobs(self, job_title: str, location: str = "", num_results: int = 10) -> List[Dict]:
        """Search for jobs using SerpAPI"""
        url = "https://serpapi.com/search"
        
        params = {
            "engine": "google_jobs",
            "q": job_title,
            "api_key": self.serp_api_key,
            "num": num_results,
            "date_posted": "today"
        }
        
        if location:
            params["location"] = location
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            jobs = data.get("jobs_results", [])
            return jobs
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching jobs: {str(e)}")
            return []
    
    def analyze_job_with_gemini(self, job_data: Dict, user_profile: str = "") -> str:
        """Analyze job posting using  AI"""
        try:
            job_title = job_data.get('title', 'N/A')
            company = job_data.get('company_name', 'N/A')
            location = job_data.get('location', 'N/A')
            description = job_data.get('description', 'N/A')
            
            prompt = f"""
            Analyze this job posting and provide insights:
            
            Job Title: {job_title}
            Company: {company}
            Location: {location}
            Description: {description[:500]}...
            
            User Profile: {user_profile}
            
            Please provide:
            1. A brief summary of the role
            2. Key requirements and skills needed
            3. Match percentage with user profile (if provided)
            4. Pros and cons of this opportunity
            5. Salary expectations (if mentioned)
            
            Keep the analysis concise and actionable.
            """
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            return f"Error analyzing job: {str(e)}"
    
    def generate_email_content(self, jobs: List[Dict], job_title: str, user_email: str) -> str:
        """Generate HTML email content with job listings"""
        if not jobs:
            return f"""
            <html>
            <body>
                <h2>Daily Job Alert - {job_title}</h2>
                <p>Hello,</p>
                <p>No new jobs were found for "{job_title}" in the last 24 hours.</p>
                <p>We'll keep monitoring for you!</p>
                <br>
                <p>Best regards,<br>AI Job Search Agent</p>
            </body>
            </html>
            """
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .job-card {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; }}
                .job-title {{ color: #2c5aa0; font-size: 18px; font-weight: bold; }}
                .company {{ color: #666; font-size: 16px; margin: 5px 0; }}
                .location {{ color: #888; font-size: 14px; }}
                .description {{ margin: 10px 0; line-height: 1.4; }}
                .apply-btn {{ background-color: #4CAF50; color: white; padding: 8px 16px; 
                            text-decoration: none; border-radius: 4px; display: inline-block; margin-top: 10px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; text-align: center; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔍 Daily Job Alert</h1>
                <h2>Top {min(len(jobs), 10)} jobs for "{job_title}"</h2>
                <p>Found {len(jobs)} new opportunities in the last 24 hours</p>
            </div>
        """
        
        for i, job in enumerate(jobs[:10], 1):
            title = job.get('title', 'N/A')
            company = job.get('company_name', 'N/A')
            location = job.get('location', 'N/A')
            description = job.get('description', 'No description available')
            apply_link = job.get('apply_link', '#')
            salary = job.get('salary', '')
            
            # Truncate description
            if len(description) > 200:
                description = description[:200] + "..."
            
            html_content += f"""
            <div class="job-card">
                <div class="job-title">{i}. {title}</div>
                <div class="company">🏢 {company}</div>
                <div class="location">📍 {location}</div>
                {f'<div style="color: #2e7d32; font-weight: bold;">💰 {salary}</div>' if salary else ''}
                <div class="description">{description}</div>
                {f'<a href="{apply_link}" class="apply-btn">Apply Now</a>' if apply_link != '#' else ''}
            </div>
            """
        
        html_content += """
            <div style="margin-top: 30px; padding: 20px; background-color: #f8f9fa; text-align: center;">
                <p>This is your daily job alert. You're receiving this because you subscribed to job notifications.</p>
                <p>Happy job hunting! 🚀</p>
                <hr>
                <small>AI Job Search Agent | Powered by Qualcomm AI 100 & SerpAPI</small>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def send_daily_job_alert(self, subscription: UserSubscription):
        """Send daily job alert to subscriber"""
        if not self.email_service:
            return False
        
        jobs = self.search_jobs(subscription.job_title, subscription.location, 15)
        
        if jobs:
            # Filter and rank top 10 jobs 
            top_jobs = jobs[:10]  # For now, take first 10. Can enhance with AI ranking
        else:
            top_jobs = []
        
        email_content = self.generate_email_content(top_jobs, subscription.job_title, subscription.email)
        subject = f"🔍 Daily Job Alert: {len(top_jobs)} new {subscription.job_title} positions"
        
        return self.email_service.send_email(subscription.email, subject, email_content)
    
    def setup_daily_scheduler(self):
        """Setup daily job alert scheduler"""
        def send_alerts():
            try:
                subscriptions = self.db_manager.get_active_subscriptions()
                for subscription in subscriptions:
                    self.send_daily_job_alert(subscription)
                    time.sleep(2)  # Rate limiting
            except Exception as e:
                print(f"Scheduler error: {str(e)}")
        
        schedule.every().day.at("09:00").do(send_alerts)
        
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def main():
    st.set_page_config(
        page_title="AI Job Search Agent with Email Alerts",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 AI Job Search Agent with Daily Email Alerts")
    st.markdown("Find recent job postings and get daily email notifications with top matches")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ API Configuration")
        
        serp_api_key = st.text_input(
            "SerpAPI Key",
            value=os.environ.get('SERP_API_KEY', 'db518d1638534c7453826aff15ba9170a3d231f63bf459e329f99dabae03c4f8'),
          
            type="password",
            help="Get your free API key from serpapi.com"
        )
        
        # IMAGINE API configuration
        imagine_api_key = st.text_input(
            "IMAGINE API Key",
            value=os.environ.get('IMAGINE_API_KEY', '2d8c76a5-8c44-4b4e-8d85-07850f51ff2a'),
            type="password",
            help="Qualcomm AI Playground API Key"
        )

        imagine_endpoint = st.text_input(
            "IMAGINE API Endpoint",
            value=os.environ.get('IMAGINE_API_ENDPOINT', 'https://aisuite.cirrascale.com/apis/v2'),
            help="Qualcomm AI API Endpoint"
        )
        
        
        # Initialize IMAGINE client and get models
        imagine_client = None
        llm_models = ["Llama-3.1-8B"]  # Default fallback
        
        
        if imagine_api_key and imagine_endpoint:
            imagine_client = initialize_ai_client()
            llm_models = imagine_client.get_available_models(model_type=ModelType.LLM)
        
       
        st.markdown("---")
        st.header("📧 Email Configuration")
        
        email_provider = st.selectbox(
            "Email Provider",
            ["Gmail", "Outlook", "Custom SMTP"]
        )
        
        if email_provider == "Gmail":
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
        elif email_provider == "Outlook":
            smtp_server = "smtp-mail.outlook.com"
            smtp_port = 587
        else:
            smtp_server = st.text_input("SMTP Server", "smtp.gmail.com")
            smtp_port = st.number_input("SMTP Port", value=587)
        
        sender_email = st.text_input("Sender Email")
        sender_password = st.text_input("Email Password/App Password", type="password")
        
        st.markdown("---")
        st.header("🎯 Search Parameters")
        
        job_title = st.text_input(
            "Job Title/Designation",
            placeholder="e.g., Software Engineer, Data Scientist"
        )
        
        location = st.text_input(
            "Location (Optional)",
            placeholder="e.g., New York, Remote"
        )
        
        num_results = st.slider("Number of Results", 5, 20, 10)
        
        st.markdown("---")
        st.header("👤 Your Profile (Optional)")
        user_profile = st.text_area(
            "Brief description of your skills",
            placeholder="e.g., 3 years of Python development...",
            height=80
        )
    
    # Initialize services
    email_service = None
    if sender_email and sender_password:
        email_service = EmailService(smtp_server, smtp_port, sender_email, sender_password)
    
    if not serp_api_key or not imagine_api_key:
        st.warning("⚠️ Please enter your SerpAPI and Imagine API keys in the sidebar.")
        return
    

    # AI Model selection
    default_model_name = "Llama-3.1-8B"
    if llm_models:
        model = st.selectbox("Select AI Model", llm_models, index=llm_models.index(default_model_name) if default_model_name in llm_models else 0)
    else:
        st.sidebar.error("No AI models available")
        return
    # Initialize agent
    agent = JobSearchAgent(serp_api_key, imagine_api_key, email_service,model)
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Job Search", "📧 Email Alerts", "⚙️ Manage Subscriptions"])
    
    with tab1:
        st.header("Search Recent Job Postings")
        
        if not job_title:
            st.info("💡 Enter a job title in the sidebar to start searching!")
            return
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_button = st.button("🔍 Search Jobs", type="primary", use_container_width=True)
        
        with col2:
            if st.button("💡 Get Search Tips", use_container_width=True):
                with st.spinner("Getting AI tips..."):
                    try:
                        prompt = f"Provide job search tips for {job_title} positions. Include related job titles, key skills, and market insights."
                        response = agent.model.generate_content(prompt)
                        st.markdown("## 💡 Job Search Tips")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Error getting tips: {str(e)}")
        
        if search_button:
            with st.spinner(f"Searching for {job_title} positions..."):
                jobs = agent.search_jobs(job_title, location, num_results)
            
            if not jobs:
                st.warning("No jobs found. Try adjusting your search criteria.")
                return
            
            st.success(f"Found {len(jobs)} recent job postings!")
            
            for i, job in enumerate(jobs, 1):
                with st.expander(f"{i}. {job.get('title', 'N/A')} at {job.get('company_name', 'N/A')}", expanded=i <= 3):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Company:** {job.get('company_name', 'N/A')}")
                        st.markdown(f"**Location:** {job.get('location', 'N/A')}")
                        if job.get('salary'):
                            st.markdown(f"**Salary:** {job.get('salary')}")
                        
                        description = job.get('description', 'No description available')
                        if len(description) > 300:
                            description = description[:300] + "..."
                        st.markdown(f"**Description:** {description}")
                        
                        if job.get('apply_link'):
                            st.markdown(f"[🔗 Apply Here]({job.get('apply_link')})")
                    
                    with col2:
                        if st.button(f"🤖 AI Analysis", key=f"analyze_{i}"):
                            with st.spinner("Analyzing..."):
                                analysis = agent.analyze_job_with_gemini(job, user_profile)
                            st.markdown("### 🤖 AI Analysis")
                            st.markdown(analysis)
    
    with tab2:
        st.header("📧 Setup Daily Email Alerts")
        
        if not email_service:
            st.warning("⚠️ Please configure email settings in the sidebar to enable alerts.")
            return
        
        if not job_title:
            st.info("💡 Enter a job title in the sidebar first.")
            return
        
        st.markdown("Get daily email notifications with the top 10 job matches for your criteria.")
        
        user_email = st.text_input(
            "Your Email Address",
            placeholder="your.email@example.com",
            help="You'll receive daily job alerts at this email"
        )
        
        if st.button("📧 Setup Daily Email Alert", type="primary"):
            if not user_email or not validate_email(user_email):
                st.error("Please enter a valid email address.")
                return
            
            # Create subscription
            subscription = UserSubscription(
                email=user_email,
                job_title=job_title,
                location=location,
                created_at=datetime.now().isoformat()
            )
            
            if agent.db_manager.add_subscription(subscription):
                st.success("✅ Email alert setup successfully!")
                st.info(f"You'll receive daily emails at 9:00 AM with top {job_title} opportunities.")
                
                # Send test email
                with st.spinner("Sending test email..."):
                    test_jobs = agent.search_jobs(job_title, location, 5)
                    email_content = agent.generate_email_content(test_jobs, job_title, user_email)
                    if agent.email_service.send_email(
                        user_email, 
                        f"🔍 Test: Your {job_title} Job Alert Setup", 
                        email_content
                    ):
                        st.success("📧 Test email sent successfully!")
                    else:
                        st.warning("Email setup saved, but test email failed. Check your email configuration.")
            else:
                st.error("Failed to setup email alert. Please try again.")
    
    with tab3:
        st.header("⚙️ Manage Your Subscriptions")
        
        if not email_service:
            st.warning("⚠️ Email service not configured.")
            return
        
        subscriptions = agent.db_manager.get_active_subscriptions()
        
        if not subscriptions:
            st.info("No active subscriptions found.")
            return
        
        st.markdown(f"**Active Subscriptions:** {len(subscriptions)}")
        
        for i, sub in enumerate(subscriptions, 1):
            with st.expander(f"{i}. {sub.job_title} alerts for {sub.email}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Email:** {sub.email}")
                    st.markdown(f"**Job Title:** {sub.job_title}")
                    st.markdown(f"**Location:** {sub.location or 'Any'}")
                    st.markdown(f"**Created:** {sub.created_at[:10]}")
                
                with col2:
                    if st.button("🗑️ Unsubscribe", key=f"unsub_{i}"):
                        if agent.db_manager.deactivate_subscription(sub.email, sub.job_title):
                            st.success("Unsubscribed successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to unsubscribe.")
    
    # Start scheduler on first run
    if 'scheduler_started' not in st.session_state:
        if email_service:
            agent.setup_daily_scheduler()
            st.session_state.scheduler_started = True
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🔍 AI Job Search Agent with Daily Email Alerts</p>
        <p>Built with Streamlit, Qualcomm AI 100 Playground, and SerpAPI</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()