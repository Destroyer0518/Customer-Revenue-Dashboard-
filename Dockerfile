# Use the official Python slim image
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirement file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app code
COPY . .

# Expose the port used by Streamlit
EXPOSE 7860

# Command to run the Streamlit app
CMD ["streamlit", "run", "customer.py", "--server.address=0.0.0.0", "--server.port=7860"]
