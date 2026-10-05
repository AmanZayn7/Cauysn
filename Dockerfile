FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    CAUSYN_BIND=0.0.0.0 PORT=8765 CAUSYN_RUNTIME_DIR=/runtime
WORKDIR /app
# Run capture_dependencies.py in the tested Mac venv before the first build.
COPY requirements.runtime.txt /app/requirements.runtime.txt
RUN pip install --no-cache-dir -r requirements.runtime.txt \
    && groupadd --gid 10001 causyn \
    && useradd --uid 10001 --gid causyn --no-create-home causyn \
    && mkdir /runtime && chown causyn:causyn /runtime
COPY --chown=causyn:causyn *.py /app/
COPY --chown=causyn:causyn docs /app/docs
COPY --chown=causyn:causyn ui /app/ui
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8765')+'/healthz',timeout=3)"
CMD ["python", "web_app.py"]
