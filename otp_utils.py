import random

def generate_otp():
    """
    Generate a 6-digit numeric OTP
    """
    return str(random.randint(100000, 999999))
