import creds
import gspread
import requests

from datetime import datetime

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)
spreadsheet = gc.open_by_key(creds.waste_id)


def main():
    webhook_url = creds.webhook_test
    now_today = datetime.today().strftime("%Y-%m-%d")

    sheet = spreadsheet.worksheet("Data")
    num_rows = sheet.row_count
    values = sheet.get(f"A{num_rows - 10}:J{num_rows}")

    filets = spicy = nuggets = strips = g_filets = g_nuggets = b_filets = gb_filets = sb_filets = 0
    for row in values:
        if row[0][:10] == now_today:
            # If there is an index error, it's only because there is no value in that cell toward
            # the end of that row. It will probably never trigger before strips, but lets be safe and
            # catch them all.  Hmm.  Sounds like Pokemon.
            try:
                filets += float(row[1])
            except (ValueError, IndexError):
                pass
            try:
                spicy += float(row[2])
            except (ValueError, IndexError):
                pass
            try:
                nuggets += float(row[3])
            except (ValueError, IndexError):
                pass
            try:
                strips += float(row[4])
            except (ValueError, IndexError):
                pass
            try:
                g_filets += float(row[5])
            except (ValueError, IndexError):
                pass
            try:
                g_nuggets += float(row[6])
            except (ValueError, IndexError):
                pass
            try:
                b_filets += float(row[7])
            except (ValueError, IndexError):
                pass
            try:
                gb_filets += float(row[8])
            except (ValueError, IndexError):
                pass
            try:
                sb_filets += float(row[9])
            except (ValueError, IndexError):
                pass

    block_text = ""
    if filets:
        block_text += f"\nFilets: {filets}"
    if spicy:
        block_text += f"\nSpicy: {spicy}"
    if nuggets:
        block_text += f"\nNuggets: {nuggets}"
    if strips:
        block_text += f"\nStrips: {strips}"
    if g_filets:
        block_text += f"\nGrilled Filets: {g_filets}"
    if g_nuggets:
        block_text += f"\nGrilled Nuggets: {g_nuggets}"
    if b_filets:
        block_text += f"\nBreakfast Filets: {b_filets}"
    if gb_filets:
        block_text += f"\nGrilled Breakfast: {gb_filets}"
    if sb_filets:
        block_text += f"\nSpicy Breakfast: {sb_filets}"

    blocks = [
        {
            "type": "section",
            "block_id": "section_header",
            "text": {
                "type": "mrkdwn",
                "text": f"*Waste Report for {now_today}"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "block_id": "waste_report",
            "text": {
                "type": "mrkdwn",
                "text": block_text
            }
        }
    ]

    payload = {
        "text": "Daily Waste Report",
        "blocks": blocks
    }

    r = requests.post(webhook_url, json=payload)
    if r.status_code != 200:
        raise ValueError(f"Request to Slack returned an error {r.status_code}\n"
                         f"The response is: {r.text}")


if __name__ == "__main__":
    main()
