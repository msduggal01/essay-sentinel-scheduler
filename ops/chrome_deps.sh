#!/bin/bash
# ffmpeg, fonts and the libraries Remotion's headless Chrome needs on ubuntu-latest.
# On 7 Oct 2026 a stuck apt mirror froze this script until the job's 30-minute limit and cost
# the day's video, so every apt call now has its own time limit and is tried three times.
set -e
apt_try() {
  for i in 1 2 3; do
    sudo timeout 300 apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 "$@" && return 0
    echo "::warning::apt-get $1 (attempt $i) failed or timed out; trying again"
    sleep $((10 * i))
  done
  return 1
}
apt_try update -qq
apt_try install -y -qq ffmpeg fonts-liberation libnss3 libdbus-1-3 libgbm1 libxrandr2 \
  libxkbcommon0 libxfixes3 libxcomposite1 libxdamage1 libpango-1.0-0 libcairo2 >/dev/null
apt_try install -y -qq libasound2t64 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 >/dev/null \
  || apt_try install -y -qq libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 >/dev/null
