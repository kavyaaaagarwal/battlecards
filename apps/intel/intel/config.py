"""Loads everything from .env so the agent is fully company-independent."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Company:
    name: str
    domain: str | None = None

    @property
    def slug(self) -> str:
        return slugify(self.name)


@dataclass
class Config:
    company: Company
    competitors: list[Company]
    category: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    openrouter_api_key: str = ""
    search_provider: str = "auto"
    tavily_api_key: str = ""
    results_per_query: int = 3
    max_chars_per_source: int = 4000
    cache_ttl_hours: float = 24
    output_dir: Path = field(default_factory=lambda: Path("reports"))
    cache_dir: Path = field(default_factory=lambda: Path(".cache"))
    notes_dir: Path = field(default_factory=lambda: Path("notes"))
    runs_per_day: int = 30
    tavily_calls_per_day: int = 150
    run_mode: str = "inline"  # "inline" (thread, local dev) | "queue" (Vercel Queues)

    @property
    def all_companies(self) -> list[Company]:
        return [self.company, *self.competitors]

    @property
    def resolved_search_provider(self) -> str:
        if self.search_provider in ("tavily", "ddg"):
            return self.search_provider
        return "tavily" if self.tavily_api_key else "ddg"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def clean_domain(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0]
    return d.removeprefix("www.") or None


def parse_company(token: str) -> Company:
    """'HubSpot:hubspot.com' -> Company('HubSpot', 'hubspot.com')."""
    token = token.strip()
    # Only split on a colon that is not part of a URL scheme
    m = re.match(r"^(.*?)\s*:\s*((?:https?://)?[\w.-]+\.[a-z]{2,}.*)$", token, re.I)
    if m:
        return Company(m.group(1).strip(), clean_domain(m.group(2)))
    return Company(token)


def _int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    return int(v) if v else default


def _float(name: str, default: float) -> float:
    v = os.getenv(name, "").strip()
    return float(v) if v else default


def default_env_file() -> Path:
    """Repo-root .env (apps/intel/intel/config.py -> repo root), overridable by INTEL_ENV_FILE."""
    return Path(os.getenv("INTEL_ENV_FILE") or Path(__file__).resolve().parents[3] / ".env")


def load_settings(env_file: str | Path | None = None) -> Config:
    """API keys and tuning only - no companies, no validation (the API reports problems per request)."""
    path = Path(env_file) if env_file else default_env_file()
    if path.exists():
        load_dotenv(path, override=False)
    return Config(
        company=Company(""),
        competitors=[],
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        search_provider=os.getenv("SEARCH_PROVIDER", "auto").strip().lower(),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        results_per_query=_int("RESULTS_PER_QUERY", 3),
        max_chars_per_source=_int("MAX_CHARS_PER_SOURCE", 4000),
        cache_ttl_hours=_float("CACHE_TTL_HOURS", 24),
        output_dir=Path(os.getenv("OUTPUT_DIR", "reports").strip() or "reports"),
        runs_per_day=_int("RUNS_PER_DAY", 30),
        tavily_calls_per_day=_int("TAVILY_CALLS_PER_DAY", 150),
        run_mode=os.getenv("RUN_MODE", "inline").strip().lower() or "inline",
    )


def with_companies(settings: Config, company: Company, competitors: list[Company], category: str = "") -> Config:
    return replace(
        settings,
        company=Company(company.name, company.domain),
        competitors=[Company(c.name, c.domain) for c in competitors],
        category=category,
    )


def load_config(env_file: str | None = ".env") -> Config:
    """CLI entry: settings + companies from .env, validated (raises SystemExit with a friendly message)."""
    settings = load_settings(env_file)
    company_name = os.getenv("COMPANY", "").strip()
    competitors_raw = os.getenv("COMPETITORS", "").strip()
    if not company_name:
        raise SystemExit("COMPANY is not set. Copy .env.example to .env and fill it in.")
    if not competitors_raw:
        raise SystemExit("COMPETITORS is not set (comma-separated list).")
    cfg = with_companies(
        settings,
        Company(company_name, clean_domain(os.getenv("COMPANY_DOMAIN"))),
        [parse_company(t) for t in competitors_raw.split(",") if t.strip()],
        os.getenv("CATEGORY", "").strip(),
    )
    if problem := settings_problem(cfg):
        raise SystemExit(problem)
    return cfg


def settings_problem(cfg: Config) -> str | None:
    if cfg.llm_provider not in ("anthropic", "openai", "openrouter"):
        return f"LLM_PROVIDER must be 'openrouter', 'anthropic' or 'openai', got '{cfg.llm_provider}'."
    if cfg.llm_provider == "openrouter" and not cfg.openrouter_api_key:
        return "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is empty (get one free at openrouter.ai/keys)."
    if cfg.llm_provider == "anthropic" and not cfg.anthropic_api_key:
        hint = (
            " You've set OPENAI_API_KEY - if that's your Gemini/OpenAI/Groq key, set LLM_PROVIDER=openai."
            if cfg.openai_api_key else ""
        )
        return f"LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty.{hint}"
    if cfg.llm_provider == "openai" and not cfg.openai_api_key:
        return ("LLM_PROVIDER=openai but OPENAI_API_KEY is empty. "
                "(For Gemini/Groq, put that service's key in OPENAI_API_KEY.)")
    if cfg.llm_provider == "openai" and not cfg.openai_base_url and not cfg.openai_api_key.startswith("sk-"):
        return ("OPENAI_API_KEY doesn't look like an OpenAI key, and OPENAI_BASE_URL is empty, so the "
                "request would go to OpenAI and fail. For Gemini set:\n"
                "  OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/")
    if cfg.search_provider == "tavily" and not cfg.tavily_api_key:
        return "SEARCH_PROVIDER=tavily but TAVILY_API_KEY is empty."
    return None
