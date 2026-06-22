import json
from celery import current_app
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")
        print("consumer_user", self.user)

        # Check if the user object is anonymous or completely unassigned
        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return

        # Authorized user - assign to their secure private room
        self.room_name = f"user_room_{self.user.id}"
        self.user_group = f"group_{self.room_name}"

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        # Safely discard using the exact matching group variable name
        if hasattr(self, 'user_group') and self.user_group:
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        print("")
        print("-------------")
        print(text_data)
        print("-------------")
        print("")
        try:
            data = json.loads(text_data)
            print(data)
            msg_type = data.get('type')

            if msg_type == "start_processing":
                # 🚀 INSTANTLY OFFLOAD EVERYTHING TO CELERY
                # Your web processes remain 100% responsive while handling traffic peaks
                current_app.send_task(  # type: ignore
                    "agents.tasks.process_agentic_chat_turn_task", # Ensure this matches your celery task path string exactly!
                    kwargs={
                        "channel_name": self.channel_name,
                        "session_id": data.get('session_id', 1),
                        "prompt_text": data.get('prompt', ''),
                        "repos": data.get('repos', []),
                        "provider": data.get('provider', 'google'),
                        "model_name": data.get('model_name', 'gemini-2.5-flash'),
                        "api_key": data.get('user_api_key', '')
                    }
                )

                print("goal post")
            print("sexy")

        except json.JSONDecodeError:
            print("🚨 Malformed socket frame payload dropped.")

    async def chat_message(self, event):
        """
        Pushes broadcast packets sent from your isolated Celery workers 
        directly down the raw socket pipe straight back to the browser.
        """
        # Ensure we serialize the dictionary correctly to avoid downstream parsing crashes
        await self.send(text_data=json.dumps(event['payload']))
