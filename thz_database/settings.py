# thz_database/settings.py (relevant parts)
from pathlib import Path
import os

from dotenv import dotenv_values

env_values = dotenv_values("spectra/backend.env")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env_values['SECRET_KEY']
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True  # Set to False in production

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = ["https://linusleo.synology.me"]
# If Nginx is handling SSL termination, Django needs to know it can trust
# the X-Forwarded-Proto header from the proxy.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True # If Nginx sets X-Forwarded-Host

TIME_ZONE = 'Europe/Berlin'

USE_I18N = True

USE_TZ = True

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'spectra.apps.SpectraConfig',  # Your app

    # Add 'crispy_forms' if you decide to use it for form styling
]

MIDDLEWARE = [
    # ... other middleware ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # ...
]

ROOT_URLCONF = 'thz_database.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # Required for admin nav sidebar and other things
                'django.contrib.auth.context_processors.auth',  # Required for admin
                'django.contrib.messages.context_processors.messages',  # Required for admin
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# mysql
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'your_mysql_db_name',
#         'USER': 'your_mysql_user',
#         'PASSWORD': 'your_mysql_password',
#         'HOST': 'your_mysql_host',  # e.g., 'db' if using Docker Compose, or an IP/hostname
#         'PORT': '3306',             # Default MySQL port
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         },
#     }
# }

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# # Add STATICFILES_DIRS to tell Django where to find project-level static files
STATICFILES_DIRS = [
    BASE_DIR / "static",  # If 'static' is in your project root (BASE_DIR)
]

# STATICFILES_FINDERS = [
#     'django.contrib.staticfiles.finders.FileSystemFinder',
#     'django.contrib.staticfiles.finders.AppDirectoriesFinder',
# ]

# Authentication
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'spectra:home'
LOGOUT_REDIRECT_URL = 'spectra:home'

# Database: Ensure your database supports JSONField (e.g., PostgreSQL, SQLite 3.38+ with Django 4.1+)
# DATABASES = { ... }
