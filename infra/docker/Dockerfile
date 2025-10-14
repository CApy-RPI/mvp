FROM python:3.13-slim

# Set working directory
WORKDIR /capy_app

# Copy everything into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set PYTHONPATH so the app works
ENV PYTHONPATH=/capy_app/src

# Run the bot
CMD ["python", "src/capy_app/main.py"]