import json
from celery import current_app
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")
        username = getattr(self.user, "username", "Anonymous")
        print(f"📡 [WS-CONNECT] User attempting connection: {username}")

        # Reject unauthenticated or anonymous sessions cleanly with my standard close code
        if not self.user or self.user.is_anonymous:
            print("rejected")
            await self.close(code=4001)
            return

        # Authorized user - assign to their secure private room
        self.room_name = f"user_room_{self.user.id}"
        self.user_group = f"group_{self.room_name}"
        print("self.room_name", self.room_name)
        print("self.user_group", self.user_group)

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        print("accepted")

    async def disconnect(self, code):
        # Safely discard using the exact matching group variable name
        if hasattr(self, 'user_group') and self.user_group:
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
        print("disconnect")


    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        print("")
        print("-------------")
        print("dermatologist")
        print(self.user)
        print(self.scope.get("user"))
        print(text_data)
        print("-------------")
        print("")
        try:
            data = json.loads(text_data)
            print(data)
            msg_type = data.get('type')
            self.token  = self.scope.get("github_token")
            print("")
            print("WWWWWWWWWWWWWWWWWWWWW", msg_type)

            #  INSTANTLY OFFLOAD EVERYTHING TO CELERY
            current_app.send_task(  # type: ignore
                "agents.tasks.process_agentic_chat_turn_task", # Ensure this matches my celery task path string exactly!
                kwargs={
                    "channel_name": self.user_group,
                    "user_id": self.user.pk,
                    "username": self.user.username,
                    "token": self.token,
                    # I pass None for a fresh chat so the Celery task can create
                    # a session and let Django assign its primary key.
                    "session_id": data.get('session_id'),
                    # I echo this token so the browser can ignore stale session acknowledgements.
                    "session_request_id": data.get('session_request_id'),
                    "prompt_text": data.get('prompt', ''),
                    "repos": data.get('repos', []),
                    "provider": data.get('provider', 'google'),
                    "model_name": data.get('model_name', 'gemini-2.5-flash'),
                    "api_key": data.get('user_api_key', '')
                }
            )

            print("sexy")

        except json.JSONDecodeError:
            print("🚨 Malformed socket frame payload dropped.")


    async def chat_message(self, event):
        """
        Pushes broadcast packets sent from your isolated Celery workers 
        directly down the raw socket pipe straight back to the browser.
        """
        # Ensure we serialize the dictionary correctly to avoid downstream parsing crashes
        text_data=json.dumps(event['payload'])
        print("heyy", text_data)
        await self.send(text_data)
