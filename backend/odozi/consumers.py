import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("🔥 WebSocket connection attempt...")
        
        # 1. DEFENSIVE PROGRAMMING: Safely handle signed-in vs anonymous user sessions
        user = self.scope.get('user')
        
        # Deny connection if the user isn't authenticated via GitHub
        if not user.is_authenticated:
            await self.close(code=4001)  # Custom close code for unauthorized
            return
            
        await self.accept()

        # Lock down your single group name cleanly across the whole class instance
        self.user_group = f"user_{user.pk}"

        print(f"🔐 Assigning WebSocket to group: {self.user_group}")

        # 2. Add connection channel to the Redis group pipeline
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )

        await self.accept()
        print(f"✅ WebSocket connected successfully to group: {self.user_group}")

    async def disconnect(self, code):
        print(f"❌ WebSocket disconnected with code: {code}")
        
        # Safely discard using the exact matching group variable name
        await self.channel_layer.group_discard(
            self.user_group,
            self.channel_name
        )

    async def receive(self, text_data):
        print("📥 INCOMING WEB FRAME RECEIVED")
        print("RAW STRING PACKET:", text_data)
        
        try:
            data = json.loads(text_data)
            message = data.get('message', '')
            print("PARSED MESSAGE TEXT:", message)
            
            # (Optional) Echo back to the sender's user group to verify the loopback works
            await self.channel_layer.group_send(
                self.user_group,
                {
                    "type": "chat_message",
                    "message": f"Echo loopback: {message}"
                }
            )
        except json.JSONDecodeError:
            print("🚨 Failed to parse raw string data frame into JSON structures.")

    async def chat_message(self, event):
        """
        This system handler picks up messages sent to self.user_group 
        (from either this consumer or your Celery background tasks) 
        and pushes them down the raw pipe directly to the browser.
        """

        print(
            f"📥 WS RECEIVED "
            f"channel={self.channel_name}"
        )
        message = event['message']
        # print(f"🚀 Outbound routing data to browser pipe layout: {message}")

        # Push to browser
        await self.send(text_data=json.dumps({
            'message': message
        }))
