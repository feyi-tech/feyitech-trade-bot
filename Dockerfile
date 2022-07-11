# Make sure all layers are based on the same python
# version.
FROM python:latest

WORKDIR ./Docker

# The actual production image.
COPY . ./

RUN python -m pip install --no-cache-dir --upgrade -r requirements.txt

ENTRYPOINT ["python"]

# Assuming you want to run run.py as a script.
CMD ["run.py"]