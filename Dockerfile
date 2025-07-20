FROM python:3.12-slim

# Install Microsoft ODBC driver dependencies and register the Microsoft APT repository
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        apt-transport-https \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
         | gpg --dearmor \
         > /etc/apt/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] \
         https://packages.microsoft.com/debian/12/prod bookworm main" \
         > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
         msodbcsql18 \
         unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8008
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]