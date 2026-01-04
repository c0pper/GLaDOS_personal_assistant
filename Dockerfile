# Use the official Python 3.12 image as the base
FROM python:3.12-slim

# Install tzdata and set timezone
ENV TZ=Europe/Rome
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the entire bot application code into the container
COPY . .

ENV PYTHONPATH=/app

# Define an entrypoint to run the bot when the container starts
# The command runs the bot.py script.
CMD ["python", "src/main.py"]