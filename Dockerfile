# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# libhdf5-dev is already there from your previous version
# Add MySQL client development libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev \
    default-libmysqlclient-dev \
    gcc \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app/

# Apply database migrations
RUN python manage.py migrate

RUN mkdir -p /app/staticfiles && python manage.py collectstatic --noinput

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose the port Gunicorn will run on
EXPOSE 8001

# Define the command to run your application using Gunicorn
# Ensure 'thz_database.wsgi:application' matches your project structure
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "thz_database.wsgi:application"]