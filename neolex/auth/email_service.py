"""Resend transactional email wrapper."""

import resend

from neolex.config import settings


def _client() -> None:
    resend.api_key = settings.resend_api_key


async def send_verification_email(email: str, token: str) -> None:
    _client()
    verify_url = f"{settings.backend_url}/auth/verify-email?token={token}"
    resend.Emails.send(
        {
            "from": settings.email_from,
            "to": email,
            "subject": "Verify your Vitreon Legal account",
            "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Welcome to Vitreon Legal</h2>
          <p>Click the button below to verify your email address and activate your account.</p>
          <p style="margin:32px 0">
            <a href="{verify_url}"
               style="background:#000;color:#fff;padding:12px 28px;border-radius:6px;
                      text-decoration:none;font-weight:600">
              Verify Email
            </a>
          </p>
          <p style="color:#666;font-size:14px">This link expires in 24 hours.<br>
          If you didn't create this account, you can ignore this email.</p>
        </div>
        """,
        }
    )


async def send_password_reset_email(email: str, token: str) -> None:
    _client()
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    resend.Emails.send(
        {
            "from": settings.email_from,
            "to": email,
            "subject": "Reset your Vitreon Legal password",
            "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Password Reset</h2>
          <p>Click the button below to reset your password. This link expires in 1 hour.</p>
          <p style="margin:32px 0">
            <a href="{reset_url}"
               style="background:#000;color:#fff;padding:12px 28px;border-radius:6px;
                      text-decoration:none;font-weight:600">
              Reset Password
            </a>
          </p>
          <p style="color:#666;font-size:14px">
            If you didn't request a password reset, you can safely ignore this email.
          </p>
        </div>
        """,
        }
    )
