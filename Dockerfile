# Imagem base oficial leve do Python
FROM python:3.11-slim

# Otimizações de runtime para contêineres Google Cloud Run
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Copia todos os arquivos da aplicação
COPY . .

# Expõe a porta padrão do Cloud Run
EXPOSE 8080

# Comando de inicialização
CMD ["python", "server.py"]
