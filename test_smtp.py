import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# === Email Settings ===
to_email = "insanevampyr@gmail.com"  # Change to the email you want to receive the test
subject = "SMTP Test - AI Villain Generator"
body = "If you see this email, Gmail SMTP works perfectly."

# Create message
msg = MIMEText(body)
msg["Subject"] = subject
msg["From"] = SMTP_USER
msg["To"] = to_email

try:
    # Connect to Gmail SMTP server
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()  # Secure connection
    server.login(SMTP_USER, SMTP_PASS)
    server.send_message(msg)
    server.quit()

    print("✅ Email sent successfully to", to_email)
except Exception as e:
    print("❌ Email failed to send:", str(e))
