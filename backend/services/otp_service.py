import random
from datetime import datetime, timedelta


OTP_EXPIRY_MINUTES = 5

otp_store = {}


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def create_otp(email: str) -> str:
    otp = generate_otp()

    otp_store[email] = {
        "otp": otp,
        "expires_at": datetime.utcnow()
        + timedelta(minutes=OTP_EXPIRY_MINUTES),
    }

    return otp


def verify_otp(email: str, otp: str) -> bool:
    stored_data = otp_store.get(email)

    if not stored_data:
        return False

    if datetime.utcnow() > stored_data["expires_at"]:
        del otp_store[email]
        return False

    if stored_data["otp"] != otp:
        return False

    del otp_store[email]

    return True