#!/usr/bin/env bash
# Hunt real projects' test suites, each in a fresh python:3.12-slim container.
# Results land in docs/real/<name>.{txt,json}. Takes tens of minutes.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p docs/real
WORKERS=${WORKERS:-3}

hunt() {  # name repo tag install-command [test paths]
  local name=$1 repo=$2 tag=$3 install=$4 paths=${5:-}
  echo "== $name $tag" >&2
  docker run --rm -v "$PWD":/fh:ro -v "$PWD/docs/real":/out python:3.12-slim bash -c "
    set -e
    apt-get update -qq && apt-get install -y -qq git >/dev/null
    pip install -q /fh 2>&1 | grep -v 'root user' || true
    git clone -q --depth 1 -b $tag $repo /p && cd /p
    $install 2>&1 | grep -v 'root user' || true
    start=\$(date +%s)
    flaky-hunt run --workers $WORKERS --json /out/$name.json $paths > /out/$name.txt || true
    echo \"wall time: \$(( \$(date +%s) - start )) s on $WORKERS workers ($(nproc) cores)\" >> /out/$name.txt
    pip freeze | grep -iE '^(pytest|$name)' >> /out/$name.txt || true
  "
  tail -n 4 "docs/real/$name.txt" >&2
}

hunt click https://github.com/pallets/click 8.1.7 "pip install -q -e . pytest"
hunt python-dateutil https://github.com/dateutil/dateutil 2.9.0.post0 \
  "pip install -q -e . pytest freezegun hypothesis"
hunt humanize https://github.com/python-humanize/humanize 4.10.0 "pip install -q -e .[tests]"
hunt arrow https://github.com/arrow-py/arrow 1.3.0 \
  "pip install -q -e . -r requirements/requirements-tests.txt"
