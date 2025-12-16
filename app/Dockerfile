# Use official Python image
FROM python:3.12


# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt \
    && playwright install --with-deps



# Command to run the app with Uvicorn
CMD ["python3", "main.py"]