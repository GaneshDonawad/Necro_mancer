FROM php:8.3-cli
WORKDIR /app
COPY src/ /app/src/
USER www-data
ENTRYPOINT ["php", "/app/src/invoice.php"]
