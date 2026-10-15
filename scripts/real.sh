#!/usr/bin/env bash
# Hunt real projects' test suites, each in a fresh python:3.12-slim container.
# Results land in docs/real/<name>.{txt,json}. Takes tens of minutes.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p docs/real
WORKERS=${WORKERS:-3}

hunt() {  # name repo tag install-command [test paths]
  local name=$1-$3 repo=$2 tag=$3 install=$4 paths=${5:-}
  echo "== $name $tag" >&2
  docker run --rm -e WORKERS -v "$PWD":/fh:ro -v "$PWD/docs/real":/out python:3.12-slim bash -c "
    set -e
    export DEBIAN_FRONTEND=noninteractive PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1
    apt-get update -qq && apt-get install -y -qq git >/dev/null
    cp -r /fh /tmp/fh && rm -rf /tmp/fh/src/*.egg-info && pip install -q /tmp/fh
    command -v flaky-hunt >/dev/null
    git clone -q --depth 1 -b $tag $repo /p && cd /p
    $install
    start=\$(date +%s)
    flaky-hunt run --workers $WORKERS --json /out/$name.json $paths > /out/$name.txt || true
    echo \"wall time: \$(( \$(date +%s) - start )) s on $WORKERS workers ($(nproc) cores)\" >> /out/$name.txt
    pip freeze | grep -iE '^(pytest|$1)' >> /out/$name.txt || true
    chown $(id -u):$(id -g) /out/$name.txt /out/$name.json
  "
  tail -n 4 "docs/real/$name.txt" >&2
}

hunt click https://github.com/pallets/click 8.1.7 "pip install -q -e . pytest"
hunt python-dateutil https://github.com/dateutil/dateutil 2.9.0.post0 \
  "pip install -q -e . pytest freezegun hypothesis"
# 4.10.0 has a test-pollution bug that upstream fixed in 4.11.0: run both.
hunt humanize https://github.com/python-humanize/humanize 4.10.0 "pip install -q -e .[tests]"
hunt humanize https://github.com/python-humanize/humanize 4.11.0 "pip install -q -e .[tests]"
hunt arrow https://github.com/arrow-py/arrow 1.4.0 \
  "pip install -q -e . -r requirements/requirements-tests.txt"
