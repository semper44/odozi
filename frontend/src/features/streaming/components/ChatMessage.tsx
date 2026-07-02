import React, { useState, useRef, useEffect } from "react";
import {SendHorizontal} from "lucide-react";
import { Typewriter } from "./Typewriter";

export interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
}

interface AIChatProps {
  messages: ChatMessage[]; // for the conversation history down
  onSendMessage: (message: string) => void;
  isAiLoading: boolean;
}

export const AIChat: React.FC<AIChatProps> = ({ messages, onSendMessage, isAiLoading }) => {
  const [inputValue, setInputValue] = useState<string>("");
  const chatBodyRef = useRef<HTMLDivElement>(null);

 const scrollToBottom = () => {
    if (chatBodyRef.current) {
      chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isAiLoading]);

  
 const handleSend = () => {
    const trimmedMessage = inputValue.trim();
    if (!trimmedMessage) return;

    // 🌟 Route ONLY the string payload up to the dashboard page
    // alert(trimmedMessage)
    onSendMessage(trimmedMessage);
    setInputValue(""); // Instantly clear the text box layout state
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSend(); // Fires your text sender logic smoothly
    }
  };


  return (
    <div id="ai-chat-body-parent" className="flex flex-col w-full" style={{ height: "100vh" }}>
      <div ref={chatBodyRef} className="h-[55%] mt-4 md:px-4 w-full flex flex-col gap-2 overflow-y-auto">
        
        {/* Render both user messages and incoming packets smoothly */}
        {messages?.map((msg) => (
          <div key={msg.id} className={`flex w-full ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
            {msg.sender === "user" ? (
              <div className="bg-gray-200 p-3 w-fit rounded-lg h-fit max-w-[75%] mt-2 text-sm text-gray-900">
                {msg.text}
              </div>
            ) : (
              <div className="flex gap-3 mt-2 items-center max-w-[75%]">
                <img src="images/gradient.jpg" alt="AI Avatar" className="rounded-full w-[35px] h-[35px] object-cover" />
                <div className="bg-blue-50 border border-blue-100 text-sm p-3 rounded-lg text-gray-800">
                  <Typewriter text={msg.text} speed={15} />
                </div>
              </div>
            )}
          </div>
        ))}

        {isAiLoading && (
          <div className="flex gap-3 mt-2 items-center justify-start">
            <img src="images/gradient.jpg" alt="AI Avatar" className="rounded-full w-[35px] h-[35px] object-cover" />
            <div className="flex items-center p-3 bg-gray-50 border rounded-lg">
              <span className="loader animate-spin border-2 border-blue-600 border-t-transparent rounded-full w-4 h-4 mr-2" />
              <p className="text-sm text-gray-500">AI processing payload...</p>
            </div>
          </div>
        )}
      </div>

      <div className="relative w-[70%] h-[10%] justify-self-center mx-auto">
        <input
          type="text"
          placeholder="Ask Odozi to compile workspaces, inject keys, or run AST rules..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          className="pl-4 pr-12 mt-4 rounded-xl border w-full h-full text-sm focus:outline-none"
          style={{ borderColor: "black" }}
        />
        <div onClick={handleSend} className="absolute top-[55%] right-[5%] cursor-pointer text-gray-600">
          <SendHorizontal />
        </div>
      </div>
    </div>
  );
};
