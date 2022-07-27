import creds
import requests

from loguru import logger

lat = "36.06302829757474"
lon = "-115.17006319892765"
weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=imperial&appid={creds.weather_key}"


def main():
    """Notify team when temps are over 100 degrees"""
    webhook_url = creds.webhook_foh
    response = requests.get(weather_url)
    data = response.json()
    current_temp = data['main']['temp']
    feels_like = data['main']['feels_like']
    if current_temp > 100 or feels_like > 100:
        content = f"The current outside temperature is {current_temp} and it feels like {feels_like}."
        payload = {
            "text": "Weather Update",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": content
                    }
                }
            ]
        }
        r = requests.post(creds.webhook_url, json=payload)
        if r.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                             f"The response is: {r.text}")
      
  
if __name__ == "__main__":
    main()
