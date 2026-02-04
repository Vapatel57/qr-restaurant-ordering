from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email
import os

def send_otp_email(to_email, otp):
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))

    message = Mail(
        from_email=Email("qr.restaurant.system@gmail.com"),
        to_emails=to_email,
        subject="Verify your email",
        html_content=f"""
            <h2>Email Verification</h2>
            <p>Your OTP is:</p>
            <h1>{otp}</h1>
            <p>This OTP expires in 10 minutes.</p>
        """
    )

    sg.send(message)
