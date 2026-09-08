FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py dem_sources.json ./
COPY regions ./regions
ENV TILE_DATA_DIR=/data PORT=3001
VOLUME /data
EXPOSE 3001
CMD ["python", "tile_service.py", "serve"]
