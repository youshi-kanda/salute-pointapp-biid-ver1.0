import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = config('DEBUG', default=False, cast=bool)

# 本番環境用ホスト設定
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,testserver', cast=lambda v: [s.strip() for s in v.split(',')])

# 本番環境セキュリティ設定
if not DEBUG:
    # HTTPS強制設定
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # セキュアクッキー設定
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    
    # セキュリティヘッダー設定
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    
    # セッション設定
    SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=3600, cast=int)  # 1時間
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
    
    # 本番環境用ログ設定
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'file': {
                'level': 'WARNING',
                'class': 'logging.FileHandler',
                'filename': BASE_DIR / 'logs' / 'django.log',
                'formatter': 'verbose',
            },
            'security_file': {
                'level': 'WARNING',
                'class': 'logging.FileHandler', 
                'filename': BASE_DIR / 'logs' / 'security.log',
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': True,
            },
            'django.security': {
                'handlers': ['security_file'],
                'level': 'WARNING',
                'propagate': False,
            },
            'core.security': {
                'handlers': ['security_file'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    
    # 本番環境用セキュリティミドルウェア（本番優先）
    'core.production_middleware.ProductionSecurityMiddleware',
    'core.production_middleware.APIAuthenticationMiddleware',
    
    # 既存のセキュリティミドルウェア
    'core.partner_auth.PartnerAPIMiddleware',
    'core.security_middleware.SecurityMiddleware',
    'core.security_middleware.FraudDetectionMiddleware',
    
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # 監査ログミドルウェア（最後に実行）
    'core.production_middleware.AuditLogMiddleware',
]

ROOT_URLCONF = 'pointapp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pointapp.wsgi.application'

# Database configuration with PostgreSQL support
import os

if config('USE_POSTGRESQL', default=False, cast=bool):
    # PostgreSQL configuration
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='biid_production'),
            'USER': config('DB_USER', default='biid_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=600, cast=int),
            'CONN_HEALTH_CHECKS': config('DB_CONN_HEALTH_CHECKS', default=True, cast=bool),
            'OPTIONS': {
                'MAX_CONNS': config('DB_MAX_CONNS', default=20, cast=int),
                'connect_timeout': 10,
            },
        }
    }
else:
    # SQLite fallback
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'core.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

if DEBUG:
    # 開発環境では全てのオリジンを許可
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_HEADERS = [
        'accept',
        'accept-encoding',
        'authorization',
        'content-type',
        'dnt',
        'origin',
        'user-agent',
        'x-csrftoken',
        'x-requested-with',
        'x-client-version',
        'x-terminal-request',
    ]
else:
    # 本番環境では特定のオリジンのみ許可
    CORS_ALLOWED_ORIGINS = [
        'https://extending-guys-chess-prescribed.trycloudflare.com',
    ]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_HEADERS = [
        'accept',
        'accept-encoding',
        'authorization',
        'content-type',
        'dnt',
        'origin',
        'user-agent',
        'x-csrftoken',
        'x-requested-with',
        'x-client-version',
        'x-terminal-request',
    ]

JWT_SECRET_KEY = config('JWT_SECRET_KEY', default='dev-jwt-key-change-in-production')
JWT_ALGORITHM = config('JWT_ALGORITHM', default='HS256')

# セキュリティ設定
SECURITY_SETTINGS = {
    'MAX_LOGIN_ATTEMPTS': 5,
    'LOGIN_LOCKOUT_DURATION': 7200,  # 2時間
    'RATE_LIMIT_WINDOW': 300,        # 5分
    'RATE_LIMIT_REQUESTS': 50,       # 5分間に50回
    'ANOMALY_THRESHOLD': 20,         # 1分間に20回
    'EXCESSIVE_POINTS_THRESHOLD': 100000,  # 10万ポイント
    'GIFT_EXCHANGE_LIMIT': 5,        # 1時間に5回
}

# ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'django.log',
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': 'security.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'core.security_middleware': {
            'handlers': ['security_file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# キャッシュ設定（Redis対応）
if config('USE_REDIS', default=False, cast=bool):
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': config('REDIS_MAX_CONNECTIONS', default=50, cast=int),
                    'retry_on_timeout': True,
                    'socket_connect_timeout': 5,
                    'socket_timeout': 5,
                },
                'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
                'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            },
            'KEY_PREFIX': config('REDIS_KEY_PREFIX', default='biid_prod'),
            'TIMEOUT': config('CACHE_TIMEOUT', default=300, cast=int),
            'VERSION': 1,
        }
    }
    
    # セッションをRedisに保存
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
    
else:
    # 開発環境用のローカルメモリキャッシュ
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'biid-dev-cache',
            'TIMEOUT': 300,
        }
    }

# URL末尾スラッシュ問題を解消
APPEND_SLASH = False

# 決済ゲートウェイ設定
import os


# GMO FINCODE設定（新規）
FINCODE_MOCK = os.getenv("FINCODE_MOCK", "false").lower() == "true"  # テストAPIキー提供でfalseに変更
FINCODE_API_KEY = os.getenv("FINCODE_API_KEY", "p_test_YTY3YTRkZDMtOWIzNS00ODlhLTkzZDYtMzQzYWE5ZDQyMDQ5ZDdmZjIyYzgtNGNlZi00ODRhLWE0OTQtMzY3NTk2NTc4ZmZmc18yNTA4MjEwODQyOQ")
FINCODE_SECRET_KEY = os.getenv("FINCODE_SECRET_KEY", "")
FINCODE_SHOP_ID = os.getenv("FINCODE_SHOP_ID", "")
FINCODE_API_BASE_URL = os.getenv("FINCODE_API_BASE_URL", "https://api.test.fincode.jp")  # テスト環境URL
FINCODE_IS_PRODUCTION = os.getenv("FINCODE_IS_PRODUCTION", "false").lower() == "true"

# 決済ゲートウェイ設定（FINCODE統一）
PAYMENT_GATEWAY = "fincode"

# MELTY API連携設定（既存API活用版）
MELTY_API_BASE_URL = os.getenv('MELTY_API_BASE_URL', 'http://app-melty.com/melty-app_system/api')
# APIキー不要（既存ログインAPIを直接使用）
