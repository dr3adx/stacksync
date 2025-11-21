# Use a lightweight, official Python image
FROM python:3.11-slim

# Install dependencies needed for nsjail
# nsjail requires basic build tools, which we clean up immediately.
# We also install the required Python libraries.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    autoconf \
    pkg-config \
    git \
    flex \
    bison \
    libcap2-bin \
    libprotobuf-dev \
    libnl-route-3-dev \
    libtool \
    protobuf-compiler \
    && \
    pip install --no-cache-dir \
    numpy \
    pandas \
    flask \
    && \
    rm -rf /var/lib/apt/lists/*

# Install nsjail from source to get the latest version and minimize image size
# NOTE: In a production setup, you might pre-build nsjail or use a pre-built binary
# for faster image building, but this approach keeps the dependencies minimal.
RUN git clone https://github.com/google/nsjail.git /tmp/nsjail && \
    cd /tmp/nsjail && \
    make && \
    cp nsjail /usr/bin/nsjail && \
    # Clean up the build files
    cd / && \
    rm -rf /tmp/nsjail

# Set the working directory
WORKDIR /app
# Copy the application code
COPY main.py .

# Define the port for the service
EXPOSE 8080

# Run the Flask application
# Criteria 2: only a docker run command is necessary to run the service locally
CMD ["python3", "main.py"]