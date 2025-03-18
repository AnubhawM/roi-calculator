import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

// Define message interface
interface Message {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
}

// Props interface
interface ChatInterfaceProps {
  roiContext?: {
    budget: string;
    employees: string;
    duration: string;
    customFields: any[];
    roiResults?: string;
  };
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ roiContext }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Hello! I can answer questions about your ROI calculations. How can I help you today?',
      sender: 'assistant',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  // Auto-resize textarea as content grows
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [inputValue]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const sendMessage = async () => {
    if (inputValue.trim() === '' || isLoading) return;
    
    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue.trim(),
      sender: 'user',
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    
    try {
      // Here you would connect to your Azure AI Agent or Search service
      // For now, we'll simulate a response
      setTimeout(() => {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          content: `I'm analyzing your question about ROI calculations. This would connect to Azure AI services in a real implementation.`,
          sender: 'assistant',
          timestamp: new Date(),
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        setIsLoading(false);
      }, 1000);
      
      // Uncomment and adapt when backend is ready
      /*
      const response = await axios.post(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/ask`, {
        question: userMessage.content,
        context: roiContext
      });
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response.data.answer,
        sender: 'assistant',
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      */
    } catch (error) {
      console.error('Error sending message:', error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: 'Sorry, I encountered an error processing your question. Please try again.',
        sender: 'assistant',
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-hidden" style={{ maxHeight: 'calc(100vh - 80px)' }}>
      {/* Chat header */}
      <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 text-gray-800 dark:text-white flex-shrink-0 rounded-t-lg">
        <h2 className="text-lg font-semibold">ROI Assistant</h2>
        <p className="text-xs text-gray-600 dark:text-gray-300">Ask questions about your ROI calculations</p>
      </div>
      
      {/* Messages container with fixed height */}
      <div 
        ref={messagesContainerRef}
        className="flex-1 p-4 overflow-y-auto" 
        style={{ height: '400px' }}
      >
        {messages.map((message) => (
          <div
            key={message.id}
            className={`mb-4 ${
              message.sender === 'user' ? 'ml-auto max-w-[80%]' : 'mr-auto max-w-[80%]'
            }`}
          >
            <div
              className={`p-3 rounded-lg ${
                message.sender === 'user'
                  ? 'bg-blue-500 text-white rounded-br-none'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-none'
              }`}
            >
              {message.content}
            </div>
            <div
              className={`text-xs mt-1 text-gray-500 ${
                message.sender === 'user' ? 'text-right' : ''
              }`}
            >
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex items-center mr-auto max-w-[80%] p-3 bg-gray-100 dark:bg-gray-700 rounded-lg rounded-bl-none">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input area */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-3 bg-white dark:bg-gray-800 flex-shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your ROI..."
            className="flex-1 resize-none overflow-hidden rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 p-2 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[40px] max-h-[120px]"
            rows={1}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || inputValue.trim() === ''}
            className={`p-2 rounded-full flex-shrink-0 ${
              isLoading || inputValue.trim() === ''
                ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                : 'bg-blue-500 hover:bg-blue-600 text-white'
            }`}
            aria-label="Send message"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface; 