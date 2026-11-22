# PHP 5.6 is EOL. This container must NEVER be exposed or network-enabled.
FROM php:5.6-cli
WORKDIR /app
COPY src/ /app/src/
USER www-data
ENTRYPOINT ["php", "/app/src/invoice.php"]
