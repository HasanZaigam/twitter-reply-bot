# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install system dependencies and create a virtual environment
RUN apt-get update && apt-get install -y python3-venv && \
    python3 -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Expose the port your application runs on (if using FastAPI, Flask, etc.)
EXPOSE 8000

# Command to run the application (Replace with your script name)
CMD ["python", "twitter-reply-bot.py"]
