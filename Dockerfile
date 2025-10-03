FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

# Set environment variables
ENV PATH="/.venv/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive \
    SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.28/supercronic-linux-amd64 \
    SUPERCRONIC=supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=fe1a81a8a5809deebebbd7a209a3b97e542e2bcd

# Install system dependencies
RUN apt-get -qq update && \
    apt-get -qq install --no-install-recommends \
    ffmpeg \
    gcc \
    supervisor \
    nginx \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install supercronic for cron job scheduling
RUN curl -fsSLO "$SUPERCRONIC_URL" && \
    echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - && \
    chmod +x "$SUPERCRONIC" && \
    mv "$SUPERCRONIC" "/usr/sbin/${SUPERCRONIC}" && \
    ln -s "/usr/sbin/${SUPERCRONIC}" /usr/sbin/supercronic && \
    echo '*/5 * * * * python transcribe_alerts.py ' > /crontab && \
    supercronic -test /crontab

# Setup directories
RUN mkdir -p /var/log/supervisor

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --locked --compile-bytecode

# Copy configuration files
COPY supervisord.conf /supervisord.conf
COPY nginx.conf /etc/nginx/sites-available/default

# Copy application files
COPY forecastio/ forecastio/
COPY modules/ modules/
COPY templates/ templates/
COPY static/ static/
COPY airports.dat acro.json __init__.py pythabot.py pywx.py \
     transcribe_alerts.py webscanner.py spelling_correct.py logger.py ./

# Command to run services
CMD ["/usr/bin/supervisord", "-c", "/supervisord.conf"]