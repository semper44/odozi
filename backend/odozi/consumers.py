import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print("\n--- 🎪 CONSUMER CONNECT PHASE STARTED ---")
        self.user = self.scope.get("user")
        
        print(f"👥 [CONSUMER] Incoming scope user resolved to: {self.user} (Type: {type(self.user)})")

        # Check if the user object is anonymous or completely unassigned
        if not self.user or self.user.is_anonymous:
            print("🛑 [CONSUMER] REJECTING HANDSHAKE: User context is anonymous or None. Booting connection.")
            await self.close(code=4001)
            return

        # Authorized user - assign to their secure private room
        print(f"🟢 [CONSUMER] Access Approved for {self.user.username}. Provisioning private memory channels...")
        self.room_name = f"user_room_{self.user.id}"
        self.user_group = f"group_{self.room_name}"

        print(f"📐 [CONSUMER] Binding connection to Group Layer ID: {self.user_group}")
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        
        await self.accept()
        print("🚀 [CONSUMER] WebSocket Connection ACCEPTED cleanly by server engine.")


    async def disconnect(self, code):
        print(f"❌ WebSocket disconnected with code: {code}")
        
        # Safely discard using the exact matching group variable name
        if hasattr(self, 'user_group') and self.user_group:
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


