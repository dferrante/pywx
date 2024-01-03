FROM python:3.10-slim

# install system requirements
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -qq update \
    && apt-get -qq install --no-install-recommends \
    ffmpeg gcc git supervisor nginx curl

# install python requirements
RUN pip install -U pip setuptools
COPY requirements.txt .
RUN python -V && pip install --no-cache-dir -r requirements.txt

# copy application files
COPY forecastio forecastio/
COPY modules modules/
COPY templates templates/
COPY static static/
COPY airports.dat acro.json __init__.py pythabot.py pywx.py transcribe_alerts.py webscanner.py spelling_correct.py ./

# setup supervisord
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /supervisord.conf
COPY nginx.conf /etc/nginx/sites-available/default

# Latest releases available at https://github.com/aptible/supercronic/releases
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.28/supercronic-linux-amd64 \
    SUPERCRONIC=supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=fe1a81a8a5809deebebbd7a209a3b97e542e2bcd

RUN curl -fsSLO "$SUPERCRONIC_URL" \
 && echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - \
 && chmod +x "$SUPERCRONIC" \
 && mv "$SUPERCRONIC" "/usr/sbin/${SUPERCRONIC}" \
 && ln -s "/usr/sbin/${SUPERCRONIC}" /usr/sbin/supercronic

RUN echo '*/5 * * * * python transcribe_alerts.py ' > /crontab
RUN supercronic -test /crontab

CMD ["/usr/bin/supervisord", "-c", "/supervisord.conf"]