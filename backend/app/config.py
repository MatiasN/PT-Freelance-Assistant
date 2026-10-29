from decimal import Decimal
from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class VatRegime(StrEnum):
    EXEMPT_ARTICLE_53 = "exempt_article_53"
    QUARTERLY = "quarterly"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PTTAX_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/pt-tax-assistant.db"
    static_dir: str | None = None

    employment_monthly_gross_salary: Decimal = Decimal("3000")
    employment_payments_per_year: int = Field(default=14, ge=12, le=14)
    savings_pool_rate: Decimal = Field(default=Decimal("0.25"), ge=Decimal("0"), le=Decimal("1"))
    vat_regime: VatRegime = VatRegime.QUARTERLY

    client_name: str = "US Client Inc."
    client_address: str = ""
    client_country: str = "Estados Unidos"
    client_tax_id: str = ""
    service_description: str = "Prestação de serviços de desenvolvimento de software"
    vat_exemption_reason: str = "Artigo 6.º, n.º 7, al. a) do CIVA"
    vat_exemption_code: str = "M99"
    withholding_option: str = "Sem retenção - Não residente sem estabelecimento"

    caldav_url: str = ""
    caldav_calendar_url: str = ""
    caldav_username: str = ""
    caldav_password: SecretStr = SecretStr("")
    caldav_verify_tls: bool = True
    viactt_reminder_interval_days: int = Field(default=30, ge=1, le=90)

    # ECB Data Portal (euro foreign exchange reference rates); see app/ecb.py
    ecb_api_base_url: str = "https://data-api.ecb.europa.eu/service"
    ecb_timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    @property
    def caldav_configured(self) -> bool:
        return bool(self.caldav_calendar_url and self.caldav_username and self.caldav_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
