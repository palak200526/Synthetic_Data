import os
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import formataddr


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

SENDER_EMAIL = os.getenv("SMTP_EMAIL")
SENDER_PASSWORD = os.getenv("SMTP_PASSWORD")

SENDER_NAME = "DATRIXA"

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "assets",
    "datrixa_logo.png"
)


def send_otp_email(
    recipient_email: str,
    otp: str
):

    message = MIMEMultipart("related")

    message["From"] = formataddr(
        (SENDER_NAME, SENDER_EMAIL)
    )

    message["To"] = recipient_email
    message["Subject"] = "Your DATRIXA Login Verification Code"

    # ==========================================
    # Plain Text Version
    # ==========================================

    plain_text = f"""
Hello,

Your DATRIXA login verification code is:

{otp}

This code is valid for 5 minutes.

If you did not request this login, you can safely ignore this email.

Regards,
DATRIXA Team
"""

    # ==========================================
    # HTML Email
    # ==========================================

    html_content = f"""
<!DOCTYPE html>

<html>

<head>

    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>DATRIXA Login Verification</title>

</head>

<body style="
    margin:0;
    padding:0;
    background-color:#f4f6f8;
    font-family:Arial, Helvetica, sans-serif;
">

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="background-color:#f4f6f8; padding:40px 15px;"
>

<tr>

<td align="center">

<table
    width="600"
    cellpadding="0"
    cellspacing="0"
    style="
        max-width:600px;
        width:100%;
        background:#ffffff;
        border-radius:12px;
        overflow:hidden;
        box-shadow:0 2px 12px rgba(0,0,0,0.08);
    "
>

<!-- HEADER -->

<tr>

<td
    align="center"
    style="
        padding:32px 20px 20px;
        background:#ffffff;
    "
>

<img
    src="cid:datrixa_logo"
    alt="DATRIXA"
    width="150"
    style="
        display:block;
        max-width:150px;
        height:auto;
    "
>

</td>

</tr>


<!-- CONTENT -->

<tr>

<td
    style="
        padding:20px 45px 40px;
        color:#1f2937;
    "
>

<h2
    style="
        margin:0 0 18px;
        font-size:24px;
        font-weight:600;
        color:#111827;
    "
>
    Verify your login
</h2>


<p
    style="
        margin:0 0 20px;
        font-size:15px;
        line-height:1.6;
        color:#4b5563;
    "
>
    Hello,
</p>


<p
    style="
        margin:0 0 25px;
        font-size:15px;
        line-height:1.6;
        color:#4b5563;
    "
>
    We received a request to sign in to your DATRIXA account.
    Use the verification code below to continue.
</p>


<!-- OTP CARD -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="
        background:#f5f7ff;
        border:1px solid #e0e4ff;
        border-radius:10px;
    "
>

<tr>

<td align="center" style="padding:25px;">

<p
    style="
        margin:0 0 10px;
        font-size:12px;
        text-transform:uppercase;
        letter-spacing:1.5px;
        color:#6b7280;
        font-weight:600;
    "
>
    Verification Code
</p>

<div
    style="
        font-size:32px;
        font-weight:700;
        letter-spacing:8px;
        color:#2924a6;
    "
>
    {otp}
</div>

</td>

</tr>

</table>


<p
    style="
        margin:22px 0 0;
        font-size:14px;
        color:#6b7280;
        text-align:center;
    "
>
    This code is valid for <strong>5 minutes</strong>.
</p>


<!-- SECURITY NOTE -->

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    style="
        margin-top:28px;
        background:#fafafa;
        border-radius:8px;
    "
>

<tr>

<td style="padding:18px;">

<p
    style="
        margin:0;
        font-size:13px;
        line-height:1.6;
        color:#6b7280;
    "
>
    <strong style="color:#374151;">
        Security notice:
    </strong>
    Never share this verification code with anyone.
    DATRIXA will never ask you for your OTP.
</p>

</td>

</tr>

</table>


<p
    style="
        margin:28px 0 0;
        font-size:14px;
        line-height:1.6;
        color:#4b5563;
    "
>
    If you did not request this login, you can safely ignore this email.
</p>


<p
    style="
        margin:30px 0 0;
        font-size:14px;
        color:#4b5563;
        line-height:1.6;
    "
>
    Regards,<br>
    <strong>DATRIXA Team</strong>
</p>

</td>

</tr>


<!-- FOOTER -->

<tr>

<td
    align="center"
    style="
        padding:20px;
        background:#f9fafb;
        border-top:1px solid #eeeeee;
    "
>

<p
    style="
        margin:0;
        font-size:12px;
        color:#9ca3af;
    "
>
    © 2026 DATRIXA. All rights reserved.
</p>

<p
    style="
        margin:7px 0 0;
        font-size:12px;
        color:#9ca3af;
    "
>
    This is an automated security email.
</p>

</td>

</tr>

</table>

</td>

</tr>

</table>

</body>

</html>
"""

    # ==========================================
    # Attach plain text + HTML
    # ==========================================

    alternative = MIMEMultipart("alternative")

    alternative.attach(
        MIMEText(
            plain_text,
            "plain",
            "utf-8"
        )
    )

    alternative.attach(
        MIMEText(
            html_content,
            "html",
            "utf-8"
        )
    )

    message.attach(alternative)

    # ==========================================
    # Attach Logo
    # ==========================================

    with open(LOGO_PATH, "rb") as logo_file:

        logo = MIMEImage(
            logo_file.read()
        )

    logo.add_header(
        "Content-ID",
        "<datrixa_logo>"
    )

    logo.add_header(
        "Content-Disposition",
        "inline",
        filename="datrixa_logo.png"
    )

    message.attach(logo)

    # ==========================================
    # Send Email
    # ==========================================

    with smtplib.SMTP(
        SMTP_SERVER,
        SMTP_PORT
    ) as server:

        server.starttls()

        server.login(
            SENDER_EMAIL,
            SENDER_PASSWORD
        )

        server.sendmail(
            SENDER_EMAIL,
            recipient_email,
            message.as_string()
        )