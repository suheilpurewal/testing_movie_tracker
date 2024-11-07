# Use a Python base image directly for ease of dependency management
FROM python:3.11-slim

# Set environment variables
ENV LANG C.UTF-8

# Set working directory
WORKDIR /app

# Copy all application files into the container
COPY . .

# Install required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 5002

# Run the application directly
CMD ["python", "app.py"]
