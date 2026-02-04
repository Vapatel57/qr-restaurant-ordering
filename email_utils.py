import smtplib
from email.message import EmailMessage
import os

SMTP_EMAIL = os.getenv("SMTP_EMAIL")      # your gmail
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # app password

def send_otp_email(to_email, otp):
    msg = EmailMessage()
    msg["Subject"] = "Verify your login"
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    msg.set_content(f"""
Your verification code is:

{otp}

This code will expire in 10 minutes.

If you did not try to login, ignore this email.
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
