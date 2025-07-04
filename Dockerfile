FROM python:3.9

# Instalacja zależności
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    ffmpeg \
    libnss3 \
    libgconf-2-4 \
    libxi6 \
    libxcursor1 \
    libxcomposite1 \
    libasound2 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    libgtk-3-0 \
    libgbm1 \
    libxshmfence1 \
    libxdamage1 \
    libxfixes3 \
    libxext6 \
    libx11-6 \
    libxrender1 \
    libxin
