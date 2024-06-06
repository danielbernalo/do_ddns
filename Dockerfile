FROM python:3.12-alpine
RUN set -x \
    && apk add --no-cache supercronic shadow \
    && useradd -m app
RUN echo '*/5 * * * * ./do_ddns.py ${DOMAIN} ${RECORDS}' > ./crontab
USER app
COPY do_ddns.py .
CMD ["supercronic", "crontab"]