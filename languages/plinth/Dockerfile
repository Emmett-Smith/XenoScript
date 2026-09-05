# PLINTH toolchain image. Tag: ashlar/plinth:latest
# (00_ARCHITECTURE.md Sec 4's meta.yaml example, 01_LANGUAGE.md Sec 10).
#
# NOT TESTED: there is no Docker on the machine this was built on tonight
# (00_ARCHITECTURE.md Sec 12 / TASKS.md sandbox.mode is "subprocess" for
# this session). This Dockerfile is believed correct by inspection --
# stdlib-only Python, no build step, no network needed at build or run
# time -- but the language agent could not `docker build` it. Please
# build + smoke-test before relying on it for the container sandbox path.
#
# Expected run invocation, matching 00_ARCHITECTURE.md Sec 12's security
# posture (no network, read-only rootfs, tmpfs workdir, non-root, capped
# resources):
#
#   docker run --rm \
#     --network=none \
#     --read-only \
#     --tmpfs /tmp \
#     --memory=512m \
#     --user plinth \
#     -v "$(pwd)/candidate.plth:/work/candidate.plth:ro" \
#     ashlar/plinth:latest parse --json /work/candidate.plth
#
# This mirrors the subprocess-mode command arrays in corpora/plinth/meta.yaml
# (["python3", "languages/plinth/plinth/cli.py", "parse", "--json", "{file}"])
# via the /usr/local/bin/plinth wrapper below, so a future container-mode
# meta.yaml can use the bare ["plinth", "parse", "--json", "{file}"] form
# shown as the illustrative example in 00_ARCHITECTURE.md Sec 4 unchanged.

FROM python:3.13-slim

# PLINTH is stdlib-only (01_LANGUAGE.md Sec 7); no pip install needed.
RUN useradd --create-home --shell /usr/sbin/nologin plinth

WORKDIR /app
COPY plinth/ /app/plinth/

# Wrapper so the bare "plinth" command works from any cwd, matching the
# illustrative meta.yaml in 00_ARCHITECTURE.md Sec 4.
RUN printf '#!/bin/sh\nexec python3 /app/plinth/cli.py "$@"\n' > /usr/local/bin/plinth \
    && chmod +x /usr/local/bin/plinth

WORKDIR /work
USER plinth

ENTRYPOINT ["plinth"]
CMD ["symbols", "--json"]
