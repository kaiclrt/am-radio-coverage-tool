# Build context is the repo root (see docker-compose.yml's `context: .`),
# not api/, because the package under src/ and the digitized curve data
# under data/ both live outside this directory - see the relative path in
# src/propagation/curves.py (_DATA_PATH) for why data/'s location relative
# to src/ has to be preserved exactly.
FROM python:3.12-slim

WORKDIR /app

# rasterio's PyPI wheel bundles GDAL/PROJ themselves, but GDAL still
# dynamically links against a couple of shared libraries the *slim* base
# image doesn't include - libexpat1 (XML parsing, e.g. GML/KML drivers).
# Without it the wheel installs fine (pip never runs it) but crashes at
# import time inside the container with "ImportError: libexpat.so.1:
# cannot open shared object file" - confirmed by testing the built image,
# not by inspection, since it's exactly the kind of gap a dependency
# manifest can't catch (see CONTRIBUTING.md's "validate against real data,
# not just that it looks right").
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# Dependency-resolution inputs first, app code after, so a rebuild that
# only touches api/app.py or curve data doesn't re-run `pip install`.
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .[api,terrain]

COPY api/ ./api/
COPY data/ ./data/

# Drop root: nothing here needs it at runtime (binds 5000, not a privileged
# <1024 port; reads its own files; makes outbound HTTPS). Limits the blast
# radius of a container-escape or code-exec bug, and stops an accidental
# write from clobbering system files. pip installed the package globally as
# root above, so appuser just needs read access to /app.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Debug mode stays off by default in the image too, same as local (see
# docs/api.md's hardening notes) - only enabled by explicitly setting
# FLASK_DEBUG=1 at `docker run`/compose time.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health', timeout=2)" || exit 1

CMD ["python", "api/app.py"]
