# The VHS image plus flaky-hunt, so `make gif` records the real CLI. The VHS
# image's Debian release is too old for its apt sources, so Python and
# flaky-hunt come from the official bookworm image, copied in whole.
FROM python:3.12-slim-bookworm AS py
COPY pyproject.toml README.md /src/
COPY src /src/src
RUN pip install --no-cache-dir /src

FROM ghcr.io/charmbracelet/vhs:v0.10.0
COPY --from=py /usr/local/lib /usr/local/lib
COPY --from=py /usr/local/bin /usr/local/bin
ENV PATH=/usr/local/bin:$PATH LD_LIBRARY_PATH=/usr/local/lib PYTHONDONTWRITEBYTECODE=1
