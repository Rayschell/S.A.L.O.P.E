"""Provisioning des membres lors d'un login Google."""
from __future__ import annotations

from app.models.models import Member
from app.services.google_auth import email_allowed, provision_member


def test_new_member_is_staff(db_session):
    m = provision_member(db_session, "Jean.Dupont@lateb.eu", "Jean", "Dupont")
    assert m.email == "jean.dupont@lateb.eu"
    assert m.roles == ["staff"]
    assert (m.prenom, m.nom) == ("Jean", "Dupont")


def test_bureau_email_gets_bureau(db_session):
    m = provision_member(db_session, "zachee.descamps@lateb.eu", "Zachée", "Descamps")
    assert set(m.roles) == {"staff", "bureau"}


def test_existing_member_keeps_roles_and_is_not_duplicated(db_session):
    db_session.add(Member(nom="X", prenom="Y", email="a@lateb.eu", roles=["bureau"]))
    db_session.commit()
    m = provision_member(db_session, "a@lateb.eu", "Z", "W")
    assert set(m.roles) == {"staff", "bureau"}
    assert m.prenom == "Y"
    assert db_session.query(Member).filter(Member.email == "a@lateb.eu").count() == 1


def test_email_allowed():
    assert email_allowed("x@lateb.eu")
    assert not email_allowed("x@gmail.com")
    assert not email_allowed("x@evil-lateb.eu")
