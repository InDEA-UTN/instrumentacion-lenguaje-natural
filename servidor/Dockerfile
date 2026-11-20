FROM python:3.12-slim

# libusb: pyvisa-py habla USBTMC con el osciloscopio a través de pyusb.
RUN apt-get update && apt-get install -y --no-install-recommends libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[visa]"

EXPOSE 8000
CMD ["uvicorn", "servidor.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
