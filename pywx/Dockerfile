FROM python:3.10-slim

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -qq update \
    && apt-get -qq install --no-install-recommends \
    ffmpeg gcc git supervisor

RUN pip install -U pip setuptools
COPY requirements.txt .
RUN python -V && pip install --no-cache-dir -r requirements.txt

COPY forecastio forecastio/
COPY modules modules/
COPY templates templates/
COPY airports.dat acro.json __init__.py pythabot.py pywx.py transcribe_alerts.py webscanner.py ./
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["/usr/bin/supervisord"]