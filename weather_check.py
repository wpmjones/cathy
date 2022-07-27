import creds
import requests

from loguru import logger

logger.add("weather.log", rotation="1 week")

lat = "36.06302829757474"
lon = "-115.17006319892765"
weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=imperial&appid={creds.weather_key}"


def main():
    """Notify team when temps are over 100 degrees"""
    response = requests.get(weather_url)
    data = response.json()
    current_temp = data['main']['temp']
    feels_like = data['main']['feels_like']
    logger.info(f"{current_temp} and {feels_like}")
  
  
if __name__ == "__main__":
    main()
