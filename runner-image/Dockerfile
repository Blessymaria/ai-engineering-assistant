# Runner image for generated tools, for machines that can reach Docker Hub:
#   docker build -t aiea-python-base:local runner-image
# Otherwise use build-local.sh. The image only needs python3: the harness and the
# tool code are sent on stdin, and nothing is mounted.
FROM python:3.12-slim
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3
