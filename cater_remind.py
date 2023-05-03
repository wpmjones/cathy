import creds
import gspread
import requests
import sys

from datetime import datetime, timedelta

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)
spreadsheet = gc.open_by_key(creds.cater_id)
sheet1 = spreadsheet.worksheet("Sheet1")

now = datetime.today().strftime("%m/%d/%Y")
maps_url_base = "https://www.google.com/maps/search/?api=1&query="
webhook_url = creds.webhook_cater


def morning():
    """Notification of catering orders for each day (details)"""
    list_of_orders = sheet1.findall(now, in_column=1)
    list_of_rows = [x.row for x in list_of_orders]
    print(list_of_orders)
    print(list_of_rows)
    blocks = []
    for row in list_of_rows:
        values_list = sheet1.row_values(row)
        if values_list[2] == "PICKUP":
            blocks.append(
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Pickup"}
                }
            )
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:*\n{values_list[1]}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Customer:*\n{values_list[3]}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Phone:*\n{values_list[5]}"
                        }
                    ]
                }
            )
            blocks.append(
                {
                    "type": "divider"
                }
            )
        else:
            sheet2 = spreadsheet.worksheet("Sheet2")
            driver_list = sheet2.get_all_values()
            driver_name = values_list[2].strip()
            for driver in driver_list:
                if driver[0] == driver_name:
                    driver_tag = f"<@{driver[1]}>"
                    break
            else:
                driver_tag = driver_name
            blocks.append(
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Delivery"}
                }
            )
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:*\n{values_list[1]}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Driver:*\n{driver_tag}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Customer:*\n{values_list[3]}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Phone:*\n{values_list[5]}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Address:*\n<{maps_url_base + values_list[4].replace(' ', '%20')}|{values_list[4]}>"
                        }
                    ]
                }
            )
            blocks.append(
                {
                    "type": "divider"
                }
            )
    blocks = blocks[:-1]

    payload = {
        "text": "Catering Orders for Today",
        "blocks": blocks
    }

    # r = requests.post(webhook_url, json=payload)
    # if r.status_code != 200:
    #     raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
    #                      f"The response is: {r.text}")


def evening():
    """Notification of catering orders for upcoming days (summary)"""
    list_of_orders = sheet1.get_values()
    blocks = []


    payload = {
        "text": "Catering Orders for Today",
        "blocks": blocks
    }

    # r = requests.post(webhook_url, json=payload)
    # if r.status_code != 200:
    #     raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
    #                      f"The response is: {r.text}")


if __name__ == "__main__":
    if sys.argv[1] == "morning":
        morning()
    else:
        evening()
