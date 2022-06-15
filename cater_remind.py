import creds
import gspread
import requests

from datetime import datetime

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)
spreadsheet = gc.open_by_key(creds.cater_id)
sheet = spreadsheet.worksheet("Sheet1")

maps_url_base = "https://www.google.com/maps/search/?api=1&query="


def main():
    """Notification of catering orders for each day"""
    webhook_url = creds.webhook_test

    now = datetime.today().strftime("%m/%d/%Y")
    list_of_cells = sheet.findall(now, in_column=1)
    if list_of_cells:
        list_of_rows = [x.row for x in list_of_cells]
        blocks = []
        for row in list_of_rows:
            values_list = sheet.row_values(row)
            if values_list[2] == "PICKUP":
                blocks.append(
                    {
                        "type": "header",
                        "text": "Pickup"
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
                blocks.append(
                    {
                        "type": "header",
                        "text": "Delivery"
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
                                "text": f"*Driver:*\n{values_list[2]}"
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

        r = requests.post(webhook_url, json=payload)
        if r.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                             f"The response is: {r.text}")


if __name__ == "__main__":
    main()
