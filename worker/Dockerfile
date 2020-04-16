FROM researchdeezer/spleeter
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m prefetch_models

ENTRYPOINT ["python", "separator.py"]
