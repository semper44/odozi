import ReactMarkdown from "react-markdown";

function ChatResponse({ response }) {
  return (
    <div className="chat-response">
      <ReactMarkdown>
        {response}
      </ReactMarkdown>
    </div>
  );
}

export default ChatResponse;