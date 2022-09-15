import creds
import datetime
import email
import ftplib
import gspread
import imaplib
import matplotlib.pyplot as plt
import pandas as pd
import requests
import time

from loguru import logger

logger.add("scraper.log", rotation="1 week")

mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(creds.gmail_u, creds.gmail_app)
mail.select("INBOX")
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


def find_nth(content, search_string, n):
    start = content.find(search_string)
    while start >= 0 and n > 1:
        start = content.find(search_string, start + len(search_string))
        n -= 1
    return start


def check_cem():
    """Look at gmail to find CEM email and report findings"""
    # Scrap email
    search_date = datetime.date.today()  # - datetime.timedelta(days=1)
    tfmt = search_date.strftime('%d-%b-%Y')
    _, sdata = mail.search(None, f'(FROM "SMGMailMgr@whysmg.com" SINCE {tfmt})')
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
        for j in range(7):
            start = find_nth(body, "%", j + 1) - 3
            end = start + 4
            score_dict[categories[j]] = body[start:end].strip()
            # catch the colon in case where response is 0% (e.g. ": 0%")
            if ":" in score_dict[categories[j]]:
                score_dict[categories[j]] = score_dict[categories[j]].replace(": ", "")
        # find number of respondents
        start = body.find("n:") + 3
        end = start + 3
        num_responses = body[start:end].strip()
        # Google Sheet work
        sh = gc.open_by_key(creds.cem_id)
        daily = sh.worksheet("Daily")
        current_month = datetime.datetime.now().month
        current_date = datetime.datetime.now().day
        current_year = datetime.datetime.now().year
        val_list = [f"{current_month}/{current_date}/{current_year}", ]
        for key, value in score_dict.items():
            val_list.append(value[:-1])
        daily.append_row(val_list, value_input_option="USER_ENTERED")
        columns = ["Date", ]
        columns.extend(categories)
        df = pd.DataFrame(daily.get_all_records(), columns=columns)
        data = df.tail(10)
        data.plot(x="Date", y=categories, title="CEM Scores (Last 10 days)", xlabel="Date")
        plt.legend(categories, loc="upper left")
        plt.savefig(fname="plot")
        ftp = ftplib.FTP(creds.ftp_host, creds.ftp_user, creds.ftp_password)
        ftp.encoding = "utf-8"
        filename = f"images/plot_{current_month}_{current_date}.png"
        with open("plot.png", "rb") as file:
            ftp.storbinary(f"STOR {filename}", file)
        # post content to Slack
        content = (f"*Month to Date CEM Scores*\n"
                   f"Out of {num_responses} responses\n```")
        for key, value in score_dict.items():
            content += f"{key}{' ' * (25 - len(key))}{' ' * (4 - len(value))}{value}\n"
        content += "```"
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": content}
                },
                {
                    "type": "image",
                    "title": {"type": "plain_text", "text": "CEM Update Chart"},
                    "image_url": f"http://www.mayodev.com/images/plot_{current_month}_{current_date}.png",
                    "alt_text": "CEM Update Chart"
                }
            ]
        }
        r = requests.post(creds.webhook_announce, json=payload)
        if r.status_code != 200:
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
                    body = part.get_payload()
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = msg.get_payload()
        # body captured, search for relevant text
        if body:
            start = body.lower().find("item #") + 1
            end = start + 14
            item_number = "I" + body[start:end].strip()
            start = end + 2
            end = body.lower().find("this item was") - 1
            item_name = body[start:end].strip()
            item = f"{item_number} - {item_name}"
            start = end
            end = body.lower().find("product")
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
                    body = part.get_payload()
                if part.get("Content-Disposition") is None:
                    pass
        else:
            body = msg.get_payload()
        # body captured, search for relevant text
        if body:
            new_line = "\n"
            start = body.find("#")
            logger.info(start)
            end = start + 10
            item_number = "Item" + body[start:end].strip()
            start = end + 1
            end = body.lower().find("this item was") - 1
            item_name = body[start:end].strip()
            item = f"{item_number} - {item_name.replace(new_line, '')}"
            start = end
            end = body.lower().find("product")
            truck_date = body[start:end].strip() + "."
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
    check_oos()
    check_allocation()
    # if datetime.date.weekday(today) != 6:
    #     time.sleep(60*60*3)  # sleep 3 hours
    #     post_symbol_goal()
