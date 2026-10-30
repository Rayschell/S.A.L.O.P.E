from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/salope"
    SECRET_KEY: str = "CHANGEME-generate-a-secure-random-key-at-least-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_EMAIL_DOMAIN: str = "lateb.eu"
    FUZZY_MATCH_THRESHOLD: int = 90
    CORS_ORIGINS: str = "http://localhost:3000"
    COOKIE_SECURE: bool = False  # True en prod (HTTPS)

    # Google OIDC
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # URL publique du callback (passe par le proxy front en dev)
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/api/auth/google/callback"
    # Emails (séparés par des virgules) qui reçoivent le rôle bureau à la connexion
    BUREAU_EMAILS: str = "zachee.descamps@lateb.eu"

    # Serveur MCP (/api/mcp) + serveur d'autorisation OAuth associé
    # URL publique du site : issuer OAuth et base de la ressource MCP
    PUBLIC_BASE_URL: str = "http://localhost:3000"
    MCP_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    MCP_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Redirect URIs acceptées à l'enregistrement dynamique des clients (virgules).
    # "*" = port libre, uniquement pour le loopback.
    MCP_ALLOWED_REDIRECT_URIS: str = (
        "http://localhost:*,http://127.0.0.1:*,http://[::1]:*,"
        "https://claude.ai/api/mcp/auth_callback,"
        "https://claude.com/api/mcp/auth_callback,"
        "https://vscode.dev/redirect"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
