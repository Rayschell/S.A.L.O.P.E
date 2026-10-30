"""Google OIDC : client authlib + provisioning des membres."""
from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import Member

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def bureau_emails() -> set[str]:
    return {e.strip().lower() for e in settings.BUREAU_EMAILS.split(",") if e.strip()}


def email_allowed(email: str) -> bool:
    return email.lower().rsplit("@", 1)[-1] == settings.ALLOWED_EMAIL_DOMAIN.lower()


def provision_member(
    db: Session, email: str, prenom: str | None, nom: str | None
) -> Member:
    """Retrouve le membre par email ou le crée (staff). Garantit le rôle bureau
    pour les emails de BUREAU_EMAILS. Ne retire jamais de rôle."""
    email = email.lower()
    member = db.query(Member).filter(Member.email == email).first()
    if member is None:
        local = email.split("@")[0]
        member = Member(
            email=email,
            prenom=prenom or local,
            nom=nom or "",
            roles=["staff"],
        )
        db.add(member)

    roles = list(member.roles or [])
    if "staff" not in roles:
        roles.append("staff")
    if email in bureau_emails() and "bureau" not in roles:
        roles.append("bureau")
    member.roles = roles

    db.commit()
    db.refresh(member)
    return member
