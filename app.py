import creds
import os

from slack_bolt.async_app import AsyncApp

app = AsyncApp(token=creds.bot_token,
               signing_secret=creds.signing_secret)


# Listens to incoming messages that contain "hello"
@app.message("hello")
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    say(
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Hey there <@{message['user']}>!"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Click Me"},
                    "action_id": "button_click",
                },
            }
        ],
        text=f"Hey there <@{message['user']}>!",
    )


@app.command("/hello-bolt-python")
async def hello(body, ack):
    user_id = body["user_id"]
    await ack(f"Hi <@{user_id}>!")


@app.action("button_click")
def action_button_click(body, ack, say):
    # Acknowledge the action
    ack()
    say(f"<@{body['user']['id']}> clicked the button")


# Start your app
if __name__ == "__main__":
    app.start(port=3000)  # int(os.environ.get("PORT", 3000)))
