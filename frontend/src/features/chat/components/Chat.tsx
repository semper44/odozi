import { useChatSocket } from "../hooks/useChatSocket";

export const Chat = () => {
  const { sendMessage } = useChatSocket();

  return (
    <button
      onClick={() => sendMessage("Hello from React")}
    >
      Send
    </button>
  );
};