# creds.py is the file in which you store all of your personal information
# This includes usernames, passwords, keys, and tokens.
# Example:
# bot_token = "my_token"
# Once you import creds, you will access this like this:
# creds.bot_token
import creds

import asyncio
import gspread
import json
import os
import re
import requests
import string

# from slack_bolt import App
from datetime import datetime, date, timedelta
from decimal import Decimal
from fuzzywuzzy import fuzz
from loguru import logger
from slack_bolt.async_app import AsyncApp
from slack_sdk.web import WebClient
from slack_bolt.error import BoltError
from slack_sdk.errors import SlackApiError

# I'm a big fan of loguru and its simplicity. Obviously, any logging tool could be substituted here.
logger.add("app.log", rotation="1 week")

# Create Slack app
app = AsyncApp(token=creds.bot_token,
               signing_secret=creds.signing_secret)
client = WebClient(token=creds.bot_token)

# Connect to Google Sheets
gc = gspread.service_account(filename=creds.gspread)


# look for whitespace in string
# I'm not currently using this function. I honestly can't remember what I was using for, but if I
# remove it, I'll immediately remember why and need it again!
def contains_whitespace(s):
    return True in [c in s for c in string.whitespace]


# All new hires start on Monday, so I use this function to get the next Monday for a start date.
# This function is only used for adding someone to Trello since we use the start date on their cards.
def next_monday():
    now = date.today()
    days_ahead = 0 - now.weekday()
    if days_ahead <= 0:  # target already happened this week
        days_ahead += 7
    return now + timedelta(days_ahead)


# It's poor design to hard code your help command since it won't update itself when you add/change commands,
# but here it is.  I told you I wasn't a pro!  haha
@app.command("/help")
async def cathy_help(ack, say):
    """Responds with help for Cathy commands"""
    await ack()
    await say("`/symptoms` List the symptoms that require a TM to go home\n"
              "`/illness` List the illnesses that require a TM to stay home\n"
              "`/sick` Open a form to report an illness or unexcused absence\n"
              "`/find [first last]` Retrieve information on missed shifts for the specified TM\n"
              "`/tardy [first last]` Records a tardy for the specified TM\n"
              "`/goals` Responds with goals for our waste process\n"
              "`/symbol` Report on the most recent day of sales for our Symbol run\n"
              "`/add` Opens a form to add new hire to Trello"
              "`/help` List these commands")


# Remove all Slack messages from the channel you are in. I only use this in my test channel.
# This is a dangerous command and the "if body['user_id'] not in" line below limits the use of this
# command to top leadership only.
@app.command("/clear")
async def clear_messages(ack, body, say, client):
    """Clear the specified number of messages in the channel that called the command"""
    await ack()
    if body['user_id'] not in [creds.pj_user_id, creds.hc_user_id, creds.jc_user_id, creds.pr_user_id]:
        return await say("I'm sorry. Only admins can clear messages.")
    result = await client.conversations_history(channel=body['channel_id'], limit=int(body['text']))
    channel_history = result['messages']
    counter = 0
    for message in channel_history:
        # if counter % 20 == 0:
        #     await asyncio.sleep(2)
        try:
            await client.chat_delete(channel=body['channel_id'],
                                     ts=message['ts'],
                                     token=creds.user_token)
        except BoltError as e:
            print(f"Bolt error: {e}")
        except SlackApiError as e:
            print(f"Error deleting message: {e}")
            await asyncio.sleep(2)
        counter += 1


@app.command("/tardy")
async def tardy(ack, body, say, client):
    """Record when someone shows up late for their shift. We take away their meal credit when this happens
    which is why the response message is worded as such.  This updates our pay scale Google Sheet since
    tardiness also affects one's ability to get a pay raise.

    Example usage:
    /tardy First Last
    """
    await ack()
    try:
        sh = gc.open_by_key(creds.pay_scale_id)
        sheet = sh.worksheet("Tardy")
        now = date.strftime(date.today(), "%m/%d/%Y")
        logger.info(f"{now} - {body['text']} was tardy")
        to_post = [body['text'], now]
        sheet.append_row(to_post, value_input_option='USER_ENTERED')
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Tardy record added for {body['text']}. No meal credit today ({now})."
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"Submitted by: {body['user_name']}"
                    }
                ]
            }
        ]
        await client.chat_postMessage(channel=creds.sick_channel,
                                      blocks=blocks,
                                      text=f"{body['text']} was tardy on {now}.")
    except gspread.exceptions.GSpreadException as e:
        await client.chat_postMessage(channel=body['user']['id'], text=e)
    except Exception as e:
        await client.chat_postMessage(channel=body['user']['id'],
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        await client.chat_postMessage(channel=creds.pj_user_id,
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")


@app.command("/add")
async def add_trello(ack, body, client):
    """This command adds a card to our Trello board (front or back) for a new hire.  We have a template card
    in the board that is used as a source. Using this command will open a form to select FOH/BOH, employee name,
    and start date.

    Slack forms (referred to as modals or views) require to functions. The command that initiates the form (this
    function) and a view handler (the next function).

    Example usage:
    /add
    """
    await ack()
    await client.views_open(
        trigger_id=body['trigger_id'],
        view={
            "type": "modal",
            "callback_id": "add_view",
            "title": {"type": "plain_text", "text": "Add New Hire"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "input_a",
                    "label": {"type": "plain_text", "text": "Location:"},
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select FOH or BOH"
                        },
                        "action_id": "select_1",
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Front of House"
                                },
                                "value": "FOH"
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Back of House"
                                },
                                "value": "BOH"
                            }
                        ]
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_b",
                    "label": {"type": "plain_text", "text": "Full Name:"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "full_name",
                        "multiline": False
                    },
                    "optional": False
                },
                {
                    "type": "input",
                    "block_id": "input_c",
                    "label": {"type": "plain_text", "text": "Select start date:"},
                    "element": {
                        "type": "datepicker",
                        "action_id": "start_date",
                        "initial_date": str(next_monday()),
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Start date"
                        }
                    }
                },
                {
                    "type": "context",
                    "block_id": "context_a",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": body['channel_id']
                        }
                    ]
                }
            ]
        }
    )


@app.view("add_view")
async def handle_add_view(ack, body, client, view):
    """Process info from add form.  This is the view handler for the previous function.  It takes the information
    you provide in the form and processes it."""
    logger.info("Processing add input...")
    location = view['state']['values']['input_a']['select_1']['selected_option']['value']
    name = view['state']['values']['input_b']['full_name']['value']
    start_date = view['state']['values']['input_c']['start_date']['selected_date']
    channel_id = view['blocks'][3]['elements'][0]['text']
    # Get user name from body
    user = await client.users_info(user=body['user']['id'])
    user_name = user['user']['real_name']
    # Add card to Trello
    if location == "FOH":
        list_id = creds.trello_foh_list
        card_id = creds.trello_foh_card
    else:
        list_id = creds.trello_boh_list
        card_id = creds.trello_boh_card
    card_name = name + " (" + start_date[5:7] + "/" + start_date[8:10] + "/" + start_date[:4] + ")"
    await ack()
    headers = {
        "Accept": "application/json"
    }
    query = {
        "name": card_name,
        "pos": "bottom",
        "idList": list_id,
        "idCardSource": card_id,
        "key": creds.trello_key,
        "token": creds.trello_token
    }
    r = requests.post("https://api.trello.com/1/cards", headers=headers, params=query)
    if r.status_code == 200:
        data = json.loads(r.content)
        trello_url = data['shortUrl']
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{name} successfully added to the Trello {location} board.\n"
                                                   f"<{trello_url}|Click here to access card>"}
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"Submitted by: {user_name}"
                    }
                ]
            }
        ]
        await client.chat_postMessage(channel=channel_id,
                                      blocks=blocks,
                                      text=f"{name} added to {location} Trello board.")
    else:
        failure_text = f"Failed to add {name} to {location} Trello board. Error code: {r.status_code}"
        blocks = [
            {
                "type": "section",
                "text": {"type": "plain_text", "text": failure_text}
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"Submitted by: {user_name}"
                    }
                ]
            }
        ]
        await client.chat_postMessage(channel=channel_id,
                                      blocks=blocks,
                                      text=f"{name} failed to add to {location} Trello board.")
        await client.chat_postMessage(channel=creds.pj_user_id,
                                      text=f"There was an error while adding {name} to {location} Trello board.")
    # add user to CFA Staff spreadsheet (for use in /sick dropdown list)
    sh = gc.open_by_key(creds.staff_id)
    staff_sheet = sh.worksheet("Sheet1")
    staff_sheet.append_row([name], value_input_option="USER_ENTERED")
    staff_sheet.sort([1, "asc"])
    # if staff_sheet.row_count > 100:
    #     await client.chat_postMessage(channel=channel_id,
    #                                   text="The number of rows in CFA Staff has exceeded 100. This will cause the "
    #                                        "/sick command to stop working. Please notify Patrick as soon as "
    #                                        "possible so old names can be removed.")
    # add user to Pay Scale Tracking
    sh = gc.open_by_key(creds.pay_scale_id)
    pay_sheet = sh.worksheet("Champs Info")
    to_post = [name, "Team Member", "", start_date]
    pay_sheet.append_row(to_post, value_input_option="USER_ENTERED")
    pay_sheet.sort([1, "asc"])
    r = await client.conversations_open(users=creds.jj_user_id)
    dm_id = r['channel']['id']
    await client.chat_postMessage(channel=dm_id,
                                  text=f"{name} was added to Pay Scale Tracking as a Team Member. If they are "
                                       f"anything other than a Team Member, please manually update their title.")


@app.command("/sick")
async def sick(ack, body, client):
    """This command opens the form for tracking missed shifts.  I called it 'sick' but it's for any time someone
    misses a shift, including No Call, No Shows.  It pulls the list of Team Members from a Google Sheet that is
    literally just a list of TM names (first last).  Slack limits its dropdown (select) lists to 100 items, so I
    chose to limit my list of names to Team Members and Team Leads only.

    I used a dropdown because I don't trust anyone to spell names properly. :)

    Example usage:
    /sick
    """
    await ack()
    # Create options for select menu
    sheet = gc.open_by_key(creds.staff_id)
    worksheet = sheet.get_worksheet(0)
    values = worksheet.col_values(1)
    options = []
    for name in values:
        options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": name
                },
                "value": name
            }
        )
    # open the view
    await client.views_open(
        trigger_id=body['trigger_id'],
        view={
            "type": "modal",
            "callback_id": "sick_view",
            "title": {"type": "plain_text", "text": "Missed Shift"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "input_a",
                    "label": {"type": "plain_text", "text": "Name"},
                    "element": {
                        "type": "static_select",
                        "action_id": "tm_name",
                        "placeholder": {"type": "plain_text", "text": "Select a name"},
                        "options": options
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_b",
                    "label": {"type": "plain_text", "text": "Callout Reason"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reason",
                        "multiline": False
                    },
                    "optional": False,
                    "hint": {"type": "plain_text", "text": "Use NCNS for No Call/No Show"}
                },
                {
                    "type": "input",
                    "block_id": "input_c",
                    "label": {"type": "plain_text", "text": "Missed Shift"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "shift",
                        "multiline": False
                    },
                    "optional": False,
                    "hint": {"type": "plain_text", "text": "Position and Time"}
                },
                {
                    "type": "input",
                    "block_id": "input_d",
                    "label": {"type": "plain_text", "text": "Contact Person/Method"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "contact",
                        "multiline": False
                    },
                    "optional": False,
                    "hint": {
                        "type": "plain_text",
                        "text": "Hot Schedules or the name of the leader that spoke to the TM"
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_e",
                    "label": {"type": "plain_text", "text": "Other notes"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "other",
                        "multiline": False
                    },
                    "optional": True
                }
            ]
        }
    )


@app.view("sick_view")
async def handle_sick_input(ack, body, client, view):
    """Process input from sick form. This is the view handler for the previous function.  It takes the information
    you provide in the form and processes it."""
    logger.info("Processing sick input...")
    name = view['state']['values']['input_a']['tm_name']['selected_option']['value']
    reason = view['state']['values']['input_b']['reason']['value']
    shift = view['state']['values']['input_c']['shift']['value']
    contact = view['state']['values']['input_d']['contact']['value']
    other = view['state']['values']['input_e']['other']['value']
    block_text = (f"*Name*: {name}\n"
                  f"*Callout reason:* {reason}\n"
                  f"*Shift:* {shift}\n"
                  f"*Contact:* {contact}")
    if other:
        block_text += f"\n*Other notes:* {other}"
    await ack()
    # Send data to Google Sheet
    try:
        sh = gc.open_by_key(creds.sick_log_id)
        sheet = sh.get_worksheet(0)
        now = str(datetime.date(datetime.today()))
        to_post = [now, name, reason, shift, contact, other]
        sheet.append_row(to_post)
    except gspread.exceptions.GSpreadException as e:
        return await client.chat_postMessage(channel=body['user']['id'],
                                             text=e)
    except Exception as e:
        await client.chat_postMessage(channel=body['user']['id'],
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        await client.chat_postMessage(channel=creds.pj_user_id,
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        return
    user = await client.users_info(user=body['user']['id'])
    user_name = user['user']['real_name']
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": block_text}
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "text": f"Submitted by: {user_name}"
                }
            ]
        }
    ]
    await client.chat_postMessage(channel=creds.sick_channel,
                                  blocks=blocks,
                                  text=f"New callout for {name}.  Review the sheet <{creds.sick_log_link}|here>.")


@app.block_action("waste_sheet")
async def waste_sheet(ack):
    """This function is necessary for the Waste Sheet button to work. The url is actually in the button from
    waste_remind.py.  That's where there isn't anything here.  It just opens that url."""
    await ack()


@app.block_action("waste_tracking_form")
async def waste(ack, body, client):
    """This is not a command!  waste_remind.py is the script that posts a reminder in Slack at determined
    times. That reminder has a button to Record Waste.  That button initiates this modal."""
    await ack()
    # I store my BOH leaders in creds.py.  I probably ought to keep them in the same Google Sheet as my Team
    # Members, but again, I'm not a pro and I don't always do things the best way!  Having leaders names in a
    # Google Sheet would allow others to update the list, but it changes infrequently enough that I don't mind
    # being the only that can update it.
    leader_options = []
    time_options = []
    for leader in creds.leaders:
        leader_options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": leader
                },
                "value": leader
            }
        )
    for _time in creds.times:
        time_options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": _time
                },
                "value": _time
            }
        )
    blocks = [
        {
            "type": "input",
            "block_id": "input_a",
            "label": {"type": "plain_text", "text": "Leaders on"},
            "element": {
                "type": "multi_static_select",
                "action_id": "leader_names",
                "placeholder": {"type": "plain_text", "text": "Select leaders"},
                "options": leader_options
            }
        },
        {
            "type": "input",
            "block_id": "input_a2",
            "label": {"type": "plain_text", "text": "Report Time(s) Covered"},
            "element": {
                "type": "multi_static_select",
                "action_id": "times",
                "placeholder": {"type": "plain_text", "text": "Times covered"},
                "options": time_options
            }
        },
        {
            "type": "section",
            "block_id": "section_info",
            "text": {
                "type": "plain_text",
                "text": "Please enter weight as a decimal. For example, 1.25 instead of 1lb 4oz."
            }
        },
        {
            "type": "input",
            "block_id": "input_b",
            "label": {"type": "plain_text", "text": "Regular Filets"},
            "element": {
                "type": "plain_text_input",
                "action_id": "regulars",
                "initial_value": "0"
            },
            "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
        },
        {
            "type": "input",
            "block_id": "input_c",
            "label": {"type": "plain_text", "text": "Spicy Filets"},
            "element": {
                "type": "plain_text_input",
                "action_id": "spicy",
                "initial_value": "0"
            },
            "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
        },
        {
            "type": "input",
            "block_id": "input_d",
            "label": {"type": "plain_text", "text": "Nuggets"},
            "element": {
                "type": "plain_text_input",
                "action_id": "nuggets",
                "initial_value": "0"
            },
            "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
        },
        {
            "type": "input",
            "block_id": "input_e",
            "label": {"type": "plain_text", "text": "Strips"},
            "element": {
                "type": "plain_text_input",
                "action_id": "strips",
                "initial_value": "0"
            },
            "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
        },
        {
            "type": "input",
            "block_id": "input_f",
            "label": {"type": "plain_text", "text": "Grilled Filets"},
            "element": {
                "type": "plain_text_input",
                "action_id": "grilled1",
                "initial_value": "0"
            },
            "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
        },
        {
            "type": "input",
            "block_id": "input_g",
            "label": {"type": "plain_text", "text": "Grilled Nuggets"},
            "element": {
                "type": "plain_text_input",
                "action_id": "grilled2",
                "initial_value": "0"
            },
            "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
        }
    ]
    # If it's before 1pm, include the breakfast meats as well.
    if datetime.now().hour < 13:
        blocks.append(
            {
                "type": "input",
                "block_id": "input_h",
                "label": {"type": "plain_text", "text": "Breakfast Filets"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "breakfast",
                    "initial_value": "0"
                },
                "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
            }
        )
        blocks.append(
            {
                "type": "input",
                "block_id": "input_i",
                "label": {"type": "plain_text", "text": "Grilled Breakfast"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "grilled3",
                    "initial_value": "0"
                },
                "hint": {"type": "plain_text", "text": "Weight in decimal pounds"}
            }
        )
    blocks.append(
        {
            "type": "input",
            "block_id": "input_j",
            "label": {"type": "plain_text", "text": "Additional Info"},
            "element": {
                "type": "plain_text_input",
                "action_id": "other",
                "multiline": True
            },
            "optional": True
        }
    )
    blocks.append(
        {
            "type": "context",
            "block_id": "context_a",
            "elements": [
                {
                    "type": "plain_text",
                    "text": body['container']['message_ts']
                }
            ]
        }
    )
    await client.views_open(
        trigger_id=body['trigger_id'],
        view={
            "type": "modal",
            "callback_id": "waste_view",
            "title": {"type": "plain_text", "text": "Waste Form"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": blocks
        }
    )


@app.view("waste_view")
async def handle_waste_view(ack, body, client, view):
    """Process input from waste form. This is the view handler for the previous function.  It takes the information
    you provide in the form and processes it."""
    logger.info("Processing waste input...")
    raw_leaders = view['state']['values']['input_a']['leader_names']['selected_options']
    leader_list = [" - " + n['value'] for n in raw_leaders]
    raw_times = view['state']['values']['input_a2']['times']['selected_options']
    time_list = [" - " + n['value'] for n in raw_times]
    message_ts = view['blocks'][-1]['elements'][0]['text']
    errors = {}
    text_error = "Must be a decimal number with no text"
    try:
        regulars = float(view['state']['values']['input_b']['regulars']['value'])
    except ValueError:
        errors['input_b'] = text_error
    try:
        spicy = float(view['state']['values']['input_c']['spicy']['value'])
    except ValueError:
        errors['input_c'] = text_error
    try:
        nuggets = float(view['state']['values']['input_d']['nuggets']['value'])
    except ValueError:
        errors['input_d'] = text_error
    try:
        strips = float(view['state']['values']['input_e']['strips']['value'])
    except ValueError:
        errors['input_e'] = text_error
    try:
        g_filets = float(view['state']['values']['input_f']['grilled1']['value'])
    except ValueError:
        errors['input_f'] = text_error
    try:
        g_nuggets = float(view['state']['values']['input_g']['grilled2']['value'])
    except ValueError:
        errors['input_g'] = text_error
    # Handle breakfast items
    if datetime.now().hour < 13:
        try:
            breakfast = float(view['state']['values']['input_h']['breakfast']['value'])
        except ValueError:
            errors['input_h'] = text_error
        try:
            g_breakfast = float(view['state']['values']['input_i']['grilled3']['value'])
        except ValueError:
            errors['input_i'] = text_error
    if len(errors) > 0:
        return await ack(response_action="errors", errors=errors)
    await ack()
    chicken_list = [regulars, spicy, nuggets, strips, g_filets, g_nuggets]
    # Store data
    total_weight = sum(chicken_list)
    sh = gc.open_by_key(creds.waste_id)
    goal_sheet = sh.worksheet("Goals")
    goal_values = goal_sheet.get_all_values()
    goals = {}
    for row in goal_values:
        if row[0] == "Type":
            continue
        goals[row[0]] = float(row[1])
    user = await client.users_info(user=body['user']['id'])
    user_name = user['user']['real_name']
    new_line = "\n"
    block1 = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Submitted by:* {user_name}"}
    }
    block2 = {
        "type": "section",
        "text": {"type": "mrkdwn",
                 "text": (f"*Leaders on:*\n"
                          f"{new_line.join(leader_list)}\n")
                 }
    }
    block3 = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (f"*Times covered:*\n"
                     f"{new_line.join(time_list)}\n")
        }
    }
    block4_text = "*Weights:*\n"
    if total_weight > 0:
        if regulars:
            if regulars >= goals['Filets']:
                block4_text += f"_Regulars: {regulars} lbs._\n"
            else:
                block4_text += f"Regulars: {regulars} lbs.\n"
        if spicy:
            if spicy >= goals['Spicy']:
                block4_text += f"_Spicy: {spicy} lbs._\n"
            else:
                block4_text += f"Spicy: {spicy} lbs.\n"
        if nuggets:
            if nuggets >= goals['Nuggets']:
                block4_text += f"_Nuggets: {nuggets} lbs._\n"
            else:
                block4_text += f"Nuggets: {nuggets} lbs.\n"
        if strips:
            if strips >= goals['Strips']:
                block4_text += f"_Strips: {strips} lbs._\n"
            else:
                block4_text += f"Strips: {strips} lbs.\n"
        if g_filets:
            if g_filets >= goals['Grilled Filets']:
                block4_text += f"_Grilled Filets: {g_filets} lbs._\n"
            else:
                block4_text += f"Grilled Filets: {g_filets} lbs.\n"
        if g_nuggets:
            if g_nuggets >= goals['Grilled Nuggets']:
                block4_text += f"_Grilled Nuggets: {g_nuggets} lbs._\n"
            else:
                block4_text += f"Grilled Nuggets: {g_nuggets} lbs.\n"
    to_post = [str(datetime.now()), regulars, spicy, nuggets, strips, g_filets, g_nuggets]
    # Handle breakfast items
    if datetime.now().hour < 13:
        to_post.append(breakfast)
        to_post.append(g_breakfast)
        if sum([breakfast, g_breakfast]) > 0:
            total_weight += sum([breakfast, g_breakfast])
            if breakfast:
                if breakfast >= goals['Breakfast Filets']:
                    block4_text += f"_Breakfast Filets: {breakfast} lbs._\n"
                else:
                    block4_text += f"Breakfast Filets: {breakfast} lbs.\n"
            if g_breakfast:
                if g_breakfast >= goals['Grilled Breakfast']:
                    block4_text += f"_Grilled Breakfast: {g_breakfast} lbs._\n"
                else:
                    block4_text += f"Grilled Breakfast: {g_breakfast} lbs.\n"
    block4 = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": block4_text}
    }
    blocks = [block1, block2, block3, block4]
    other = view['state']['values']['input_j']['other']['value']
    if other:
        block4 = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Notes:*\n{other}"}
        }
        blocks.append(block4)
    block5 = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Please remember to replace stickers on all waste containers."}
    }
    blocks.append(block5)
    # Send data to Google Sheet
    try:
        sheet = sh.worksheet("Data")
        sheet.append_row(to_post, value_input_option='USER_ENTERED')
    except gspread.exceptions.GSpreadException as e:
        return await client.chat_postMessage(channel=body['user']['id'],
                                             text=e)
    except Exception as e:
        await client.chat_postMessage(channel=body['user']['id'],
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        await client.chat_postMessage(channel=creds.pj_user_id,
                                      text=f"There was an error while storing the message to the Google Sheet.\n{e}")
        return
    await client.chat_postMessage(channel=creds.boh_channel,
                                  blocks=blocks,
                                  text="New waste report posted.")
    logger.info("Attempting to delete waste_remind message.")
    try:
        await client.chat_delete(channel=creds.boh_channel,
                                 ts=message_ts,
                                 token=creds.user_token)
    except:
        logger.exception("Message deletion failed:\n")
    if datetime.now().hour < 12:
        await asyncio.sleep(300)
        safe_url = "https://www.cfahome.com/go/appurl.go?app=ERQA"
        content = f"Have we completed our first SAFE Daily Critical yet today?\nIf not, <{safe_url}|click here.>"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": content}
            }
        ]
        await client.chat_postMessage(channel=creds.boh_channel,
                                      blocks=blocks,
                                      text=f"SAFE yet?")


@app.command("/goals")
async def waste_goals(ack, say):
    """Responds with the current daily waste goals from the Waste Tracking Google Sheet. These goals are calculated
    from averages in the Food Cost Report."""
    await ack()
    sh = gc.open_by_key(creds.waste_id)
    sheet = sh.worksheet("Goals")
    values = sheet.get_all_values()
    content = "*Daily Waste Goals:*\n"
    for row in values:
        if row[0] == "Type":
            continue
        content += f"{row[0]}: {row[1]} lbs\n"
    await say(content)


@app.command("/sales")
async def sales(ack, body, say):
    """Record sales numbers for forecasting/revenue.  A modal will pop up asking for information.

    Example usage:
    /sales
    """
    await ack()
    current_date = date.today()
    yesterday = current_date - timedelta(days=1)
    regex = r'[^\d.]'
    await client.views_open(
        trigger_id=body['trigger_id'],
        view={
            "type": "modal",
            "callback_id": "sales_view",
            "title": {"type": "plain_text", "text": "Sales Input"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "input_a",
                    "label": {"type": "plain_text", "text": "Sales Date:"},
                    "element": {
                        "type": "datepicker",
                        "action_id": "sales_date",
                        "initial_date": str(yesterday),
                        "placeholder": {"type": "plain_text", "text": "Sales date"}
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_b",
                    "label": {"type": "plain_text", "text": "Sales"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "sales_amount",
                        "multiline": False
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_c",
                    "label": {"type": "plain_text", "text": "Catering"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "cater_amount",
                        "multiline": False
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_d",
                    "label": {"type": "plain_text", "text": "Transactions"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "transaction_count",
                        "multiline": False
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_e",
                    "label": {"type": "plain_text", "text": "Labor %"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "labor_percent",
                        "multiline": False
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_f",
                    "label": {"type": "plain_text", "text": "Labor Hours"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "labor_hours",
                        "multiline": False
                    }
                }
            ]
        }
    )


@app.view("sales_view")
async def handle_sales_input(ack, body, client, view):
    """Process input from sales form. This is the view handler for the previous function."""
    logger.info("Processing sales input...")
    sales_date = view['state']['values']['input_a']['sales_date']['selected_date']
    sales_amount = view['state']['values']['input_b']['sales_amount']['value']
    cater_amount = view['state']['values']['input_c']['cater_amount']['value']
    transactions = view['state']['values']['input_d']['transaction_count']['value']
    labor_percent = view['state']['values']['input_e']['labor_percent']['value']
    labor_hours = view['state']['values']['input_f']['labor_hours']['value']
    sh = gc.open_by_key(creds.sales_id)
    sheet = sh.worksheet("Sales")
    cell_list = sheet.findall(sales_date)
    for cell in cell_list:
        if cell.col == 1:
            sheet.update_cell(cell.row, 4, transactions)
            sheet.update_cell(cell.row, 5, sales_amount)
            sheet.update_cell(cell.row, 6, cater_amount)
            sheet.update_cell(cell.row, 9, labor_percent)
            sheet.update_cell(cell.row, 10, labor_hours)
            copy_from_list = [7, 8, 11, 12]
            for col in copy_from_list:
                formula = sheet.cell(cell.row - 1, col, value_render_option="FORMULA").value
                sheet.update_cell(cell.row, col, formula)
    await client.chat_postMessage(channel=creds.test_channel,
                                  text=f"Sales date: {sales_date}\nSales amount: {sales_amount}")


@app.command("/find")
async def find_names(ack, body, client):
    """Find matching names from Sick & Discipline Logs. This reports on both absences and tardies for the name
    provided. Fuzzy is a great tool that allows for misspellings and such as long as it's 'close'.

    Example usage:
    /find first last
    """
    await ack()
    fuzzy_number = 78
    # Collect sick records
    sh = gc.open_by_key(creds.sick_log_id)
    sheet = sh.worksheet("Form Responses 1")
    data = sheet.get_all_values()
    count = 0
    input_name = body['text']
    sick_text = f"*Sick records for {input_name}:*"
    for row in data:
        ratio = fuzz.token_sort_ratio(input_name.lower(), row[1].lower())
        if ratio > fuzzy_number:
            count += 1
            sick_text += f"\n{row[0]} - {row[2]}"
            if row[3]:
                sick_text += f" ({row[3]})"

            logger.info(f"Sick - {row[1]} matches {input_name}")
    if count == 0:
        sick_text = f"No absences found for {input_name}."
    # Collect tardies
    sheet = sh.worksheet("Tardy Import")
    data = sheet.get_all_values()
    count = 0
    tardy_text = f"*Tardy records for {input_name}:*"
    for row in data:
        ratio = fuzz.token_sort_ratio(input_name.lower(), row[0].lower())
        if ratio > fuzzy_number:
            count += 1
            tardy_text += f"\nTardy on {row[1]}"
            logger.info(f"Tardy - {row[0]} matches {input_name}")
    if count == 0:
        tardy_text = f"No tardies found for {input_name}"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": sick_text}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": tardy_text}
        }
    ]
    await client.chat_postEphemeral(channel=body['channel_id'],
                                    user=body['user_id'],
                                    blocks=blocks,
                                    text=f"Sick & tardy records for {body['text']}.")


@app.command("/symptoms")
async def symptoms(ack, say):
    """Respond with the symptoms that require a Team Member to go home"""
    await ack()
    await say("*Team Members must be sent home if displaying the following symptoms:*\n"
              "Vomiting\n"
              "Diarrhea\n"
              "Jaundice (yellowing of the skin)\n"
              "Fever\n"
              "Sore throat with fever or lesions containing pus\n"
              "Infected wound or burn that is opening or draining")


@app.command("/illness")
async def illness(ack, say):
    """Respond with the illnesses that require a Team Member to stay home"""
    await ack()
    await say("*Team Members must stay home if they have the following illnesses:*\n"
              "Salmonella Typhi\n"
              "Non-typhoidal Salmonella\n"
              "Shigella spp.\n"
              "Shiga toxin-producing Escherichia coli (E coli)\n"
              "Hepatitis A virus\n"
              "Norovirus (a type of stomach flu)")


@app.command("/test")
async def bot_test(ack, body, say):
    """Testing various features"""
    await ack()
    user = client.users_info(user=body['user_id'])
    logger.info(user['user'])
    await say(user['user']['real_name'])


# Start your app
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
    # while True:
    #     asyncio.run(cem_poster())
