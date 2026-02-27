# Use an official, lightweight Python image
FROM python:3.11-slim-bookworm

# Set the working directory inside the container
WORKDIR /app

# Copy system package requirements and install them
COPY packages.txt .
RUN apt-get update && \
    xargs -a packages.txt apt-get install -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies and install them
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
    
# Copy the rest of your application code
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Define the command to run your app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]