import creds
import datetime
import email
import ftplib
import gspread
import matplotlib.pyplot as plt
import pandas as pd
import quopri
import re
import requests

from loguru import logger

logger.add("scraper.log", rotation="1 week")

today = datetime.date.today()

gc = gspread.service_account(filename=creds.gspread)

categories = [
    "Likelihood to Return",
    "Fast Service",
    "Order Accuracy",
    "Attentive/Courteous",
    "Cleanliness",
    "Taste",
    "Overall Satisfaction",
]


def check_cater():
    """Look at gmail to find catering emails and update Catering sheet"""
    search_date = datetime.date.today() - datetime.timedelta(days=1)
    tfmt = search_date.strftime('%d-%b-%Y')
    _, sdata = mail.search(None, f'(FROM "one@chick-fil-a.com" SINCE {tfmt})')
    mail_ids = sdata[0]
    id_list = mail_ids.split()
    score_dict = {}
    body = ""
    for i in id_list:
        typ, data = mail.fetch(i, "(RFC822)")
        raw = data[0][1]
        raw_str = raw.decode("utf-8")
        msg = email.message_from_string(raw_str)
        if msg.is_multipart():
            for part in msg.walk():
                part_type = part.get_content_type()
                if part_type == "text/plain" and "attachment" not in part:
                    body = part.get_payload(decode=True).decode("utf-8")
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = msg.get_payload(decode=True).decode("utf-8")
    # find percentages in body
    if body:
        re_phone = r"(\+1)?[\s]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4}"
        logger.info(f"Catering order:\n{body}")
        if "Pickup Order" in body:
            cater_type = "PICKUP"
        else:
            cater_type = "DELIVERY"
        cur_year = datetime.datetime.today().year
        start = body.find(f"{cater_type.title()} Time")
        date_start = body.find("day", start) + 4
        date_end = body.find(str(cur_year), date_start) + 4
        cater_date_str = body[date_start:date_end]
        time_start = body.find("at ", date_end) + 3
        time_end = body.find("m", time_start) + 1
        cater_time_str = body[time_start:time_end]
        if cater_type == "DELIVERY":
            add_start = body.find("Delivery Address") + 16
            add_end = body.find("Customer Information")
            cater_address = body[add_start:add_end]
            if "Las Vegas" in cater_address:
                div = cater_address.find("Las Vegas, NV")
                cater_address = cater_address[:div] + ", " + cater_address[div:]
            elif "Henderson" in cater_address:
                div = cater_address.find("Henderson")
                cater_address = cater_address[:div] + ", " + cater_address[div:]
        re_match = re.search(re_phone, body)
        cust_start = body.find("Information", time_end) + 11
        cust_end = re_match.span()[0]
        cater_guest = body[cust_start:cust_end]
        phone_start = re_match.span()[0]
        phone_end = re_match.span()[1]
        cater_phone = body[phone_start:phone_end].replace("+1", "").replace(" ", "")
        if len(cater_phone) == 10:
            cater_phone = cater_phone[:3] + "-" + cater_phone[3:6] + "-" + cater_phone[6:]
        # Prepare content for Slack
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"New {cater_type.title()} Order"}
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Guest Name:*\n{cater_guest}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Phone:*\n{cater_phone}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Date:*\n{cater_date_str}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:*\n{cater_time_str}"
                        }
                    ]
                }
            ]
        }
        if cater_type == "DELIVERY":
            payload['blocks'][1]['fields'].append(
                {
                    "type": "mrkdwn",
                    "text": f"*Address:*\n{cater_address}"
                }
            )
        r = requests.post(creds.webhook_test, json=payload)
        if r.status_code != 200:
            raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                             f"The response is: {r.text}")


def check_cem():
    """Look at gmail to find CEM email and report findings"""
    # Google Sheet work
    sh = gc.open_by_key(creds.cem_id)
    daily = sh.worksheet("Daily")
    cem_data = daily.get_all_records()[-30:]
    columns = ["Date", ]
    columns.extend(categories)
    data = pd.DataFrame(cem_data, columns=columns)
    data.plot(x="Date", y=categories, title="CEM Scores (Last 30 days)", xlabel="Date")
    plt.legend(categories, loc="upper left")
    plt.savefig(fname="plot")
    with open("plot.png", "rb") as image_file:
        files = {"file": (os.path.basename(image_file), "image/png")}  
    # post content to Slack
    content = f"*CEM Scores*\n```"
    cur_scores = cem_data[-1]
    del cur_scores["Date"]
    for key, value in cur_scores.items():
        if value < 100:
            buffer = 2
        else:
            buffer = 1
        content += f"{key}{' ' * (25 - len(key))}{' ' * buffer}{value}%\n"
    content += "```"
    r = requests.post(creds.webhook_announce, json={"text": content})
    if r.status_code == 200:
        requests.post(creds.webhook_announce, files=files, data={})
    else:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


def check_allocation():
    """Look for allocation notifications from distribution center."""
    search_date = datetime.date.today() - datetime.timedelta(days=1)
    tfmt = search_date.strftime('%d-%b-%Y')
    _, sdata = mail.search(None, f'(SUBJECT "Allocation Notification" SINCE {tfmt})')
    mail_ids = sdata[0]
    id_list = mail_ids.split()
    body = ""
    for i in id_list:
        typ, data = mail.fetch(i, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        if msg.is_multipart():
            for part in msg.walk():
                part_type = part.get_content_type()
                if part_type == "text/plain" and "attachment" not in part:
                    body = quopri.decodestring(part.get_payload())
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = quopri.decodestring(msg.get_payload())
        # body captured, search for relevant text
        if body:
            body = body.decode()
            start = body.lower().find("item #") + 1
            end = start + 14
            item_number = "I" + body[start:end].strip()
            start = end + 2
            end = body.lower().find("this item was") - 1
            item_name = body[start:end].strip()
            item = f"{item_number} - {item_name}"
            start = end
            end = body.lower().find("the product")
            truck_date = body[start:end].strip() + "."
            # post content to Slack
            content = f"*{item}*\n{truck_date}"
            logger.info(content)
            payload = {
                "text": "Allocation Notification",
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
            r = requests.post(creds.webhook_announce, json=payload)
            if r.status_code != 200:
                raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                                 f"The response is: {r.text}")


def check_oos():
    """Look for out of stock emails from distribution center"""
    search_date = datetime.date.today() - datetime.timedelta(days=1)
    tfmt = search_date.strftime('%d-%b-%Y')
    _, sdata = mail.search(None, f'(SUBJECT "OOS" SINCE {tfmt})')
    mail_ids = sdata[0]
    id_list = mail_ids.split()
    body = ""
    for i in id_list:
        typ, data = mail.fetch(i, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        if msg.is_multipart():
            for part in msg.walk():
                part_type = part.get_content_type()
                if part_type == "text/plain" and "attachment" not in part:
                    body = quopri.decodestring(part.get_payload())
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = quopri.decodestring(msg.get_payload())
        # body captured, search for relevant text
        if body:
            body = body.decode()
            logger.info(body)
            new_line = "\n"
            start = body.find("#")
            end = start + 10
            item_number = "Item" + body[start:end].strip()
            start = end + 1
            end = body.lower().find("this item was") - 1
            item_name = body[start:end].strip().replace("=", "")
            item = f"{item_number} {item_name.replace(new_line, '')}"
            start = end
            end = body.lower().find("the product")
            truck_date = body[start:end].strip().replace("=", "") + "."
            # post content to Slack
            content = f"*{item}*\n{truck_date}"
            logger.info(content)
            payload = {
                "text": "Out of Stock Notification",
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
            r = requests.post(creds.webhook_announce, json=payload)
            if r.status_code != 200:
                raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                                 f"The response is: {r.text}")


def post_symbol_goal():
    """The command /symbol reports on current stats. This post simply reports the sales target for the coming
    day (20% of same day last year."""
    logger.info("Starting post_symbol_goal")
    # Connect to Google Sheets
    sh = gc.open_by_key(creds.symbol_id)
    sheet = sh.worksheet("Daily Goals")
    current_date = datetime.date.today()
    cell = sheet.find(current_date.strftime("%Y-%m-%d"))
    logger.info(f"Date cell: {cell}")
    goal = sheet.cell(cell.row, cell.col + 6).value
    logger.info(f"Goal: {goal}")
    content = f"*Today's Symbol Goal:* {goal}"
    payload = {"text": content}
    r = requests.post(creds.webhook_announce, json=payload)
    logger.info(f"Status Code: {r.status_code}")
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    check_cem()
    # check_cater()
    # check_oos()
    # check_allocation()
