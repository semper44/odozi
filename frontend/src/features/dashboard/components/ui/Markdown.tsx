import ReactMarkdown from "react-markdown";

interface ResponseProps{
  response: string;
}

export default function ChatResponse({ response }: ResponseProps) {
  return (
    <div className="space-y-4 text-sm leading-6 text-gray-800">
      <ReactMarkdown
        components={{
          // Paragraphs
          p: ({ children }) => (
            <p className="text-gray-700">
              {children}
            </p>
          ),

          // Section headings
          h3: ({ children }) => (
            <h3 className="mt-6 mb-3 text-base font-semibold text-gray-900">
              {children}
            </h3>
          ),

          // Lists
          ul: ({ children }) => (
            <ul className="space-y-2 ml-1">
              {children}
            </ul>
          ),

          // List item
          li: ({ children }) => (
            <li className="flex gap-2">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gray-400" />

              <span className="min-w-0">
                {children}
              </span>
            </li>
          ),

          // Bold text
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">
              {children}
            </strong>
          ),

          // Inline code
          code: ({ children }) => (
            <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[13px] text-gray-800">
              {children}
            </code>
          ),
        }}
      >
        {response}
      </ReactMarkdown>
    </div>
  );
}