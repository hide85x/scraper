FROM python:3.9

# Instalacja zależności systemowych
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    ffmpeg \
    libnss3 \
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
    libxinerama1 \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    libpango1.0-0 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    **ca-certificates** \
    && rm -rf /var/lib/apt/lists/*

# Pobranie i instalacja Google Chrome
RUN wget -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i /tmp/google-chrome.deb || apt-get -fy install \
    && rm /tmp/google-chrome.deb

# Ustawienie zmiennej środowiskowej dla Chrome
ENV PATH="/usr/bin/google-chrome:${PATH}"

# Ustawienie katalogu roboczego
WORKDIR /app

# Skopiowanie plików projektu
COPY . /app

# Instalacja zależności Pythona
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Uruchomienie aplikacji
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 300 server:app
