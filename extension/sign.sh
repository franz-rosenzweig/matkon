#!/bin/sh
# Has Mozilla sign the Firefox/Zen build ("unlisted": signed for you to hand out yourself, never listed
# on addons.mozilla.org) and keeps it in signed/, where Matkon's Settings hands it out from.
#
#   extension/sign.sh
#
# Needs AMO_JWT_ISSUER and AMO_JWT_SECRET (make them at https://addons.mozilla.org/developers/addon/api/key/)
# in the environment, or in the file AMO_ENV_FILE names (in the environment or in Matkon's env file).
# Mozilla signs each version once, so bump "version" in manifest.json before signing a change. Node
# needn't be installed: web-ext runs in the node:22 image. The key goes in the environment, never on a
# command line.
set -eu
cd "$(dirname "$0")"
MENV=${MATKON_ENV:-../private/matkon.env}
[ -f "$MENV" ] || MENV=../matkon.env
ENV_FILE=${AMO_ENV_FILE:-$(sed -n "s/^AMO_ENV_FILE=//p" "$MENV" 2>/dev/null | tail -1)}
get(){ [ -n "$ENV_FILE" ] && sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | tail -1 | sed "s/^['\"]//; s/['\"]$//"; }
AMO_JWT_ISSUER=${AMO_JWT_ISSUER:-$(get AMO_JWT_ISSUER || true)}
AMO_JWT_SECRET=${AMO_JWT_SECRET:-$(get AMO_JWT_SECRET || true)}
if [ -z "$AMO_JWT_ISSUER" ] || [ -z "$AMO_JWT_SECRET" ]; then
  echo "No AMO_JWT_ISSUER / AMO_JWT_SECRET. Make them at https://addons.mozilla.org/developers/addon/api/key/" >&2
  exit 1
fi
./build.sh
VERSION=$(python3 -c 'import json; print(json.load(open("manifest.json"))["version"])')
mkdir -p signed
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e WEB_EXT_API_KEY="$AMO_JWT_ISSUER" -e WEB_EXT_API_SECRET="$AMO_JWT_SECRET" \
  -v "$PWD/dist:/dist" -v "$PWD/signed:/signed" -w /dist node:22 \
  npx --yes web-ext@8 sign --channel=unlisted --source-dir=/dist/firefox --artifacts-dir=/signed --approval-timeout=900000
SIGNED=$(ls -t signed/*.xpi 2>/dev/null | head -1)
if [ -z "$SIGNED" ]; then echo "Mozilla didn't send a signed file back (see above)." >&2; exit 1; fi
echo "Signed $VERSION: $SIGNED. Matkon's Settings hands it out now (Firefox or Zen)."
