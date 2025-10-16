# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file to the working directory
COPY requirements.txt .

# --- START OF CHANGES ---

# 1. Install PyTorch separately using its official index for a fast, pre-compiled (wheel) version
# This avoids building from source, which is extremely slow.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# 2. Install the rest of the packages from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- END OF CHANGES ---

# Copy the rest of the application's code
COPY ./app /code/app