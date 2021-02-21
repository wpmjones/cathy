import creds
import logging

logging.basicConfig(level=logging.DEBUG)

from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

app = App(token=creds.bot_token,
          signing_secret=creds.signing_secret)


@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@app.event("app_mention")
def event_test(body, say, logger):
    logger.info(body)
    say("What's up?")


@app.event("message")
def handle_message():
    pass


from flask import Flask, request

flask_app = Flask(__name__)
handler = SlackRequestHandler(app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

# import creds
# import os
#
# # from loguru import logger
# from slack_bolt.async_app import AsyncApp
#
# app = AsyncApp(token=creds.bot_token,
#                signing_secret=creds.signing_secret)
#
#
# # Listens to incoming messages that contain "hello"
# @app.message("hello")
# async def message_hello(message, say):
#     # say() sends a message to the channel where the event was triggered
#     say(
#         blocks=[
#             {
#                 "type": "section",
#                 "text": {"type": "mrkdwn", "text": f"Hey there <@{message['user']}>!"},
#                 "accessory": {
#                     "type": "button",
#                     "text": {"type": "plain_text", "text": "Click Me"},
#                     "action_id": "button_click",
#                 },
#             }
#         ],
#         text=f"Hey there <@{message['user']}>!",
#     )
#
#
# @app.event("app_mention")
# async def event_test(body, say, logger):
#     logger.info(body)
#     say("What's up?")
#
#
# @app.command("/hello-bolt-python")
# async def hello(body, ack):
#     user_id = body["user_id"]
#     await ack(f"Hi <@{user_id}>!")
#
#
# @app.action("button_click")
# async def action_button_click(body, ack, say):
#     # Acknowledge the action
#     ack()
#     say(f"<@{body['user']['id']}> clicked the button")
#
#
# # Start your app
# if __name__ == "__main__":
#     app.start(port=3000)  # int(os.environ.get("PORT", 3000)))
