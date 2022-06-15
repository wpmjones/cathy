import creds
import gspread
import requests

from datetime import datetime

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)
spreadsheet = gc.open_by_key(creds.cater_id)
sheet = spreadsheet.worksheet("Sheet1")


def main():
    """Notification of catering orders for each day"""
    webhook_url = creds.webhook_test

    now = datetime.today().strftime("%m/%d/%Y")
    list_of_cells = sheet.findall(now, in_column=1)
    list_of_rows = [x.row for x in list_of_cells]
    for row in list_of_rows:




if __name__ == "__main__":
    main()