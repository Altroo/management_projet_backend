from pathlib import Path
from uuid import uuid4

from django.db import models
from django.utils.translation import gettext_lazy as _


def company_logo_upload_to(_instance, filename):
    suffix = Path(filename).suffix.lower() or ".png"
    return f"company_images/{uuid4().hex}{suffix}"


class CompanyProfile(models.Model):
    """The single company identity used on generated reports."""

    singleton_key = models.BooleanField(default=True, unique=True, editable=False)
    raison_sociale = models.CharField(
        max_length=255,
        default="E.B.H Gestion Projet",
        verbose_name=_("Raison sociale"),
    )
    logo = models.ImageField(
        upload_to=company_logo_upload_to,
        blank=True,
        null=True,
        max_length=1000,
        verbose_name=_("Logo"),
    )
    adresse = models.TextField(blank=True, null=True, verbose_name=_("Adresse"))
    telephone = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Téléphone")
    )
    email = models.EmailField(blank=True, null=True, verbose_name=_("E-mail"))
    site_web = models.URLField(blank=True, null=True, verbose_name=_("Site web"))
    ICE = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("ICE"))
    registre_de_commerce = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Registre de commerce"),
    )
    identifiant_fiscal = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Identifiant fiscal"),
    )
    CNSS = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("CNSS")
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Profil société")
        verbose_name_plural = _("Profil société")

    def __str__(self):
        return self.raison_sociale
