import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_otp_email(email, otp):
    message = Mail(
        from_email=os.getenv("FROM_EMAIL"),
        to_emails=email,
        subject="Verify your email",
        html_content=f"""
        <h2>Email Verification</h2>
        <p>Your OTP is:</p>
        <h1>{otp}</h1>
        <p>This OTP is valid for 10 minutes.</p>
        """
    )

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        sg.send(message)
    except Exception as e:
        # IMPORTANT: don't crash signup
        print("SendGrid error:", e)
