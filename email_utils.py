import smtplib
import socket
import os
from email.message import EmailMessage

socket.setdefaulttimeout(5)  # 🔥 VERY IMPORTANT

def send_otp_email(to_email, otp):
    msg = EmailMessage()
    msg["Subject"] = "Your OTP Verification Code"
    msg["From"] = os.getenv("SMTP_EMAIL")
    msg["To"] = to_email
    msg.set_content(f"Your OTP is: {otp}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as server:
        server.login(
            os.getenv("SMTP_EMAIL"),
            os.getenv("SMTP_PASSWORD")
        )
        server.send_message(msg)
