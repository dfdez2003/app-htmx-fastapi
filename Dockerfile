FROM python:3.13-slim

WORKDIR /code

COPY pyproject.toml ./
COPY app ./app
# Datos versionados (fuente de verdad). Se hornean como respaldo; en uso normal
# se monta ./datos para que los cambios queden en el repo del host.
COPY datos ./datos

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
