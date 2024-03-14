import creds
import requests

from loguru import logger

lat = "36.06302829757474"
lon = "-115.17006319892765"
weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=imperial&appid={creds.weather_key}"


def main():
    """Notify team when temps are over 100 degrees"""
    with open("temp.txt", "r") as f:
        last_temp = int(f.readline())
    webhook_url = creds.webhook_foh
    response = requests.get(weather_url)
    data = response.json()
    current_temp = data['main']['temp']
    feels_like = data['main']['feels_like']
    wind_speed = data['main']['wind_speed']
    logger.info(f"Weather\nCurrent Temp: {current_temp}\nFeels Like: {feels_like}\n"
                f"Current wind speed: {wind_speed}")
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
        r = requests.post(webhook_url, json=payload)
        if r.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                             f"The response is: {r.text}")
    if last_temp > 90 > current_temp:
        content = "The current outside temperature is below 90 degrees. Please turn off the misters."
        payload = {
            "text": "Mister Alert",
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
        with open("temp.txt", "w") as f:
            f.write(str(current_temp))
        r = requests.post(webhook_url, json=payload)
        if r.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                             f"The response is: {r.text}")
    """Notify team if temps are low enough for heaters"""
    content = ""
    with open("wind.txt", "r") as f:
        last_wind = int(f.readline())
    if last_wind < 28 and wind_speed < 28:
        if 45 < current_temp <= 55:
            content = "The current outside temperature is below 55. Please consider turning on the heaters."
        elif current_temp <= 45:
            content = "The current outside temperature is below 45. Please turn on the heaters (both switches)."
    else:
        if current_temp <= 55 and wind_speed > 28 >= last_wind:
            content = ("I know it's cold, but it's too windy to use the heaters right now. If it slows down, "
                       "I'll let you know.")
        elif current_temp <= 55 and wind_speed <= 28 < last_wind:
            content = "That crazy wind has finally slowed down if you want to think about turning the heaters on."
    with open("wind.txt", "w") as f:
        f.write(str(wind_speed))
    if content:
        payload = {
            "text": "Heater Alert",
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
        r = requests.post(webhook_url, json=payload)
        if r.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                             f"The response is: {r.text}")


if __name__ == "__main__":
    main()
