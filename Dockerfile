FROM python:3.10-slim

# install system requirements
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -qq update \
    && apt-get -qq install --no-install-recommends \
    ffmpeg gcc git supervisor nginx

# install python requirements
RUN pip install -U pip setuptools
COPY requirements.txt .
RUN python -V && pip install --no-cache-dir -r requirements.txt

# copy application files
COPY forecastio forecastio/
COPY modules modules/
COPY templates templates/
COPY airports.dat acro.json __init__.py pythabot.py pywx.py transcribe_alerts.py webscanner.py ./

# setup supervisord
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY nginx.conf /etc/nginx/sites-available/default

CMD ["/usr/bin/supervisord"]