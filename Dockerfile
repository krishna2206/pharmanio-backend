# Use a minimal Python base image
FROM python:3.9-alpine

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed by Python packages
# and then install Python packages, and finally remove the build-time dependencies.
# This is done in a single RUN command to reduce image layers.
COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# Copy the rest of the application code
COPY . .

# Initialize the database with the data from dataset.json
RUN python dataset_converter.py

# Expose the port the app will run on
EXPOSE 8091

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8091"]