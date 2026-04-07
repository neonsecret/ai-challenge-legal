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
        },
    )


async def send_corpus_deletion_warning_email(email: str, deletion_date: str) -> None:
    """Notify a user that their uploaded corpora will be deleted after a 7-day grace period."""
    _client()
    account_url = f"{settings.frontend_url}/account"
    billing_url = f"{settings.frontend_url}/billing"
    resend.Emails.send(
        {
            "from": settings.email_from,
            "to": email,
            "subject": "Your uploaded documents will be deleted on " + deletion_date,
            "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Your Vitreon Legal subscription has been cancelled</h2>
          <p>Your uploaded documents and custom corpora will be permanently deleted on
             <strong>{deletion_date}</strong>.</p>
          <p>Want to keep your documents? Resubscribe before <strong>{deletion_date}</strong>
             and your data will be fully preserved:</p>
          <p style="margin:32px 0">
            <a href="{billing_url}"
               style="background:#1a56db;color:#fff;padding:12px 28px;border-radius:6px;
                      text-decoration:none;font-weight:600">
              Resubscribe Now
            </a>
          </p>
          <p>Or export a copy of your data before the deletion date:</p>
          <p style="margin:32px 0">
            <a href="{account_url}"
               style="background:#000;color:#fff;padding:12px 28px;border-radius:6px;
                      text-decoration:none;font-weight:600">
              Export My Data
            </a>
          </p>
          <p style="color:#666;font-size:14px">
            Questions? Contact us at
            <a href="mailto:support@vitreon.app">support@vitreon.app</a>.
          </p>
        </div>
        """,
        },
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
        },
    )


async def send_payment_action_required_email(email: str, invoice_url: str) -> None:
    """Notify a user that 3D Secure authentication is required to complete their payment."""
    _client()
    resend.Emails.send(
        {
            "from": settings.email_from,
            "to": email,
            "subject": "Action required: complete payment for your Vitreon Legal subscription",
            "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Payment Authentication Required</h2>
          <p>Your bank requires additional authentication (3D Secure) to process your
             subscription payment.</p>
          <p>Your access is preserved while you complete this step. Please click the
             button below to authenticate and complete your payment.</p>
          <p style="margin:32px 0">
            <a href="{invoice_url}"
               style="background:#000;color:#fff;padding:12px 28px;border-radius:6px;
                      text-decoration:none;font-weight:600">
              Complete Payment
            </a>
          </p>
          <p style="color:#666;font-size:14px">
            If you have already completed this step or did not expect this email,
            please contact us at support@vitreon.app.
          </p>
        </div>
        """,
        },
    )
