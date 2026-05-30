import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("🔥 WebSocket connection attempt")
        # self.room_name = self.scope['url_route']['kwargs'].get('room_name', 'lobby')
        # self.room_group_name = f'chat_{self.room_name}'

        # await self.channel_layer.group_add(
        #     self.room_group_name,
        #     self.channel_name
        # )

        self.user_group = f"user_{self.scope['user'].id}"

        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )

        await self.accept()
        print("✅ WebSocket connected")

    async def disconnect(self, code):
        print("❌ WebSocket disconnected")
        # await self.channel_layer.group_discard(
        #     self.room_group_name,
        #     self.channel_name
        # )

    async def receive(self, text_data):
        print("RECEIVE CALLED")
        print("RAW:", text_data)
        data = json.loads(text_data)
        message = data.get('message', '')
        print("message", message)

        # await self.channel_layer.group_send(
        #     self.room_group_name,
        #     {
        #         'type': 'chat_message',
        #         'message': message
        #     }
        # )

    async def chat_message(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({
            'message': message
        }))

        await self.channel_layer.group_send(
            "user_123",
            {
                "type": "chat_message",
                "message": "Hello from Celery"
            }
        )

    
