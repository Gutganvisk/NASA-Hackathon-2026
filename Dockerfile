# Imagem base oficial leve do Python
FROM python:3.11-slim

# Otimizações de runtime para contêineres Google Cloud Run
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copia apenas os arquivos necessários para servir a aplicação.
COPY server.py http_transport.py nasa_power.py copernicus_sentinel2.py land_demarcation.py talhao_geometry.py supabase_client.py rotation_planner.py passaporte_biologico.py index.html ./
COPY assets/crop-rotation-logo.png assets/crop-rotation-icon.png assets/ui-icons.svg ./assets/
USER 65532

# Expõe a porta padrão do Cloud Run
EXPOSE 8080

# Comando de inicialização
CMD ["python", "server.py"]
