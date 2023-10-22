import creds
import gspread
import requests

from datetime import datetime

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)
spreadsheet = gc.open_by_key(creds.waste_id)

RED_CIRCLE = ":red_circle:"
GREEN_CIRCLE = ":large_green_circle:"


def get_emoji(weight, goal):
    if weight > goal:
        return RED_CIRCLE
    else:
        return GREEN_CIRCLE


def main():
    webhook_url = creds.webhook_test
    now_today = datetime.today().strftime("%Y-%m-%d")

    sheet = spreadsheet.worksheet("Data")
    num_rows = sheet.row_count
    values = sheet.get(f"A{num_rows - 10}:J{num_rows}")

    sheet = spreadsheet.worksheet("Goals")
    goals = sheet.get_all_values()
    goal_list = []
    for row in goals:
        if row[1] == "Pounds":
            continue
        goal_list.append(float(row[1]))

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
        emoji = get_emoji(filets, goal_list[1])
        block_text += f"\n{emoji} Filets: {filets} lbs. (Goal: {goal_list[1]} lbs.)"
    if spicy:
        emoji = get_emoji(spicy, goal_list[2])
        block_text += f"\n{emoji} Spicy: {spicy} lbs. (Goal: {goal_list[2]} lbs.)"
    if nuggets:
        emoji = get_emoji(nuggets, goal_list[3])
        block_text += f"\n{emoji} Nuggets: {nuggets} lbs. (Goal: {goal_list[3]} lbs.)"
    if strips:
        emoji = get_emoji(strips, goal_list[4])
        block_text += f"\n{emoji} Strips: {strips} lbs. (Goal: {goal_list[4]} lbs.)"
    if g_filets:
        emoji = get_emoji(g_filets, goal_list[5])
        block_text += f"\n{emoji} Grilled Filets: {g_filets} lbs. (Goal: {goal_list[5]} lbs.)"
    if g_nuggets:
        emoji = get_emoji(g_nuggets, goal_list[6])
        block_text += f"\n{emoji} Grilled Nuggets: {g_nuggets} lbs. (Goal: {goal_list[6]} lbs.)"
    if b_filets:
        emoji = get_emoji(b_filets, goal_list[7])
        block_text += f"\n{emoji} Breakfast Filets: {b_filets} lbs. (Goal: {goal_list[7]} lbs.)"
    if gb_filets:
        emoji = get_emoji(gb_filets, goal_list[8])
        block_text += f"\n{emoji} Grilled Breakfast: {gb_filets} lbs. (Goal: {goal_list[8]} lbs.)"
    if sb_filets:
        emoji = get_emoji(sb_filets, goal_list[9])
        block_text += f"\n{emoji} Spicy Breakfast: {sb_filets} lbs. (Goal: {goal_list[9]} lbs.)"

    blocks = [
        {
            "type": "section",
            "block_id": "section_header",
            "text": {
                "type": "mrkdwn",
                "text": f"*Waste Report for {now_today}*"
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
