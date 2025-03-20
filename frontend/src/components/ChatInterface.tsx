import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import '../styles/ROIAnalysis.css';

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
    contextVersion?: string;
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
  const [sessionId, setSessionId] = useState<string>('');
  const [serviceStatus, setServiceStatus] = useState<'available' | 'unavailable' | 'checking'>('checking');
  const [error, setError] = useState<string | null>(null);
  const [chatHeight, setChatHeight] = useState<number>(400);
  const [currentContextVersion, setCurrentContextVersion] = useState<string>('');
  const [isNewSession, setIsNewSession] = useState<boolean>(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Track context version changes
  useEffect(() => {
    if (roiContext?.contextVersion && roiContext.contextVersion !== currentContextVersion) {
      // If this is the first context version, just set it
      if (!currentContextVersion) {
        setCurrentContextVersion(roiContext.contextVersion);
        return;
      }
      
      // Check if this is a drastic change (e.g., completely new ROI calculation)
      // This could be a simple heuristic based on results existence
      const isDrasticChange = 
        // If we had results before but now they're gone (new calculation)
        (roiContext.roiResults === "" && messages.length > 2) ||
        // Or if the session has been going for a while (10+ messages)
        (messages.length > 10);
      
      // For drastic changes, start a new session to avoid confusion
      if (isDrasticChange) {
        const newSessionId = `session_${Math.random().toString(36).substring(2, 15)}`;
        setSessionId(newSessionId);
        setIsNewSession(true);
        setMessages([{
          id: Date.now().toString(),
          content: 'I notice you\'ve started a new ROI calculation. How can I help you with this new analysis?',
          sender: 'assistant',
          timestamp: new Date(),
        }]);
      }
      
      // Update the current context version
      setCurrentContextVersion(roiContext.contextVersion);
    }
  }, [roiContext?.contextVersion, messages.length]);

  // Load saved height from localStorage on mount
  useEffect(() => {
    const savedHeight = localStorage.getItem('roiAssistantHeight');
    if (savedHeight) {
      setChatHeight(parseInt(savedHeight));
    }
  }, []);

  // Save height to localStorage when it changes
  const handleResize = () => {
    if (chatContainerRef.current) {
      const newHeight = chatContainerRef.current.clientHeight;
      // Only update if height is at least 250px (reasonable minimum)
      if (newHeight >= 250) {
        setChatHeight(newHeight);
        localStorage.setItem('roiAssistantHeight', newHeight.toString());
      }
    }
  };

  // Generate a session ID on first load
  useEffect(() => {
    // Generate a unique session ID if not already set
    if (!sessionId) {
      setSessionId(`session_${Math.random().toString(36).substring(2, 15)}`);
    }

    // Check if agent service is available
    const checkAgentHealth = async () => {
      try {
        const response = await axios.get(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/agent_health`);
        if (response.data.status === 'available') {
          setServiceStatus('available');
          setError(null);
        } else {
          setServiceStatus('unavailable');
          setError('ROI Assistant service is currently unavailable. Some features may be limited.');
        }
      } catch (error) {
        console.error('Error checking agent service:', error);
        setServiceStatus('unavailable');
        setError('ROI Assistant service is currently unavailable. Some features may be limited.');
      }
    };

    checkAgentHealth();
  }, [sessionId]);

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

  // Function to prepare content for markdown rendering - similar to App.tsx
  const prepareContent = (text: string): string => {
    if (!text) return '';

    // Fix any common issues with formatting
    let processedText = text
      // Clean up any LaTeX-style formatting that might have been used
      .replace(/\\{/g, '{')
      .replace(/\\}/g, '}')
      .replace(/\\\[/g, '')
      .replace(/\\\]/g, '')
      
      // Remove any CSS class strings that might have been included
      .replace(/text-[a-z-0-9]+ /g, '')
      .replace(/m[tblr]-[0-9]+ /g, '')
      .replace(/dark:[a-z-0-9]+ /g, '')
      
      // Ensure proper bullet point formatting with a space after dash
      .replace(/^-([^\s])/gm, '- $1');

    // Special handling for LaTeX formulas containing \text{...}
    // This ensures \text commands are properly wrapped in LaTeX delimiters
    processedText = processedText.replace(/\$?\\text\{([^}]+)\}(.*?)(?:\$|$)/g, (match, textContent, remainder) => {
      // If it's already properly wrapped in delimiters, leave it alone
      if (match.startsWith('$') && match.endsWith('$')) {
        return match;
      }
      
      // If this is part of a larger expression or formula
      if (remainder && (remainder.includes('\\frac') || remainder.includes('=') || remainder.includes('\\times'))) {
        return `$\\text{${textContent}}${remainder}$`;
      }
      
      // Just wrap the \text command itself if it's standalone
      return `$\\text{${textContent}}${remainder}$`;
    });

    // Properly handle common ROI and Payback Period formulas
    // This ensures the complete formulas are properly delimited
    processedText = processedText
      .replace(/(\$?\\text\{ROI\}\s*=\s*\\frac\{[^}]+\}\{[^}]+\}\s*\\times\s*100\$?)/g, (match) => {
        if (match.startsWith('$') && match.endsWith('$')) return match;
        return `$$${match.replace(/^\$|\$$/, '')}$$`;
      })
      .replace(/(\$?\\text\{Payback Period\}\s*=\s*\\frac\{[^}]+\}\{[^}]+\}\$?)/g, (match) => {
        if (match.startsWith('$') && match.endsWith('$')) return match;
        return `$$${match.replace(/^\$|\$$/, '')}$$`;
      });

    // Handle complete formulas that might not be properly delimited
    processedText = processedText.replace(/([^$])(\\frac\{[^}]+\}\{[^}]+\})([^$]|$)/g, '$1$$$$2$$$$3');

    // *** STEP 1: PRE-PROCESS EXISTING LATEX DELIMITERS ***
    // First, normalize all LaTeX delimiters to a single $ for easier processing
    processedText = processedText
      .replace(/\$\$/g, '$') // Convert double $$ to single $
      .replace(/\$\$\$/g, '$'); // Convert triple $$$ to single $
    
    // *** STEP 2: IDENTIFY AND MARK LATEX EXPRESSIONS ***
    // Common LaTeX commands to identify mathematical expressions
    const latexCommands = [
      '\\text', '\\frac', '\\times', '\\cdot', '\\div', '\\approx', 
      '\\sqrt', '\\sum', '\\prod', '\\int', '\\lim', '\\log', 
      '\\sin', '\\cos', '\\tan', '\\alpha', '\\beta', '\\gamma',
      '\\delta', '\\theta', '\\sigma', '\\omega', '\\pi'
    ];
    
    // Start with existing dollar-delimited expressions
    const existingLatexBlocks: string[] = [];
    processedText = processedText.replace(/\$(.*?)\$/g, (match, content) => {
      // Only capture if it's not empty
      if (content && content.trim()) {
        existingLatexBlocks.push(content);
        return `__LATEX_BLOCK_${existingLatexBlocks.length - 1}__`;
      }
      return match;
    });
    
    // Handle free-standing LaTeX expressions (not already in delimiters)
    // We'll process line by line to better manage context
    processedText = processedText.split('\n').map(line => {
      // Skip lines already marked
      if (line.includes('__LATEX_BLOCK_')) {
        return line;
      }

      // Check if the line has any LaTeX commands
      const hasLatexCommand = latexCommands.some(cmd => line.includes(cmd));
      
      if (hasLatexCommand) {
        // For lines with equations like "ROI = ..."
        if (line.match(/(?:ROI|Payback Period)\s*=\s*\\/) || 
            line.match(/\\text\{(?:ROI|Payback Period)\}\s*=\s*/)) {
          existingLatexBlocks.push(line);
          return `__LATEX_BLOCK_${existingLatexBlocks.length - 1}__`;
        }
        
        // For lines with other LaTeX expressions
        latexCommands.forEach(cmd => {
          // Match expressions containing the command
          if (line.includes(cmd)) {
            const regex = new RegExp(`([^$])(${cmd}[^$]+)([^$]|$)`, 'g');
            line = line.replace(regex, (match, prefix, expr, suffix) => {
              existingLatexBlocks.push(expr);
              return `${prefix}__LATEX_BLOCK_${existingLatexBlocks.length - 1}__${suffix}`;
            });
          }
        });
      }
      
      // Handle equation lines with multiplication and equals
      if ((line.includes('×') || line.includes('=')) && /\d+\s*(?:×|\*)\s*\d+/.test(line)) {
        // Extract complete equations containing × or multiplication
        const equationRegex = /([\w\s]+)\s*=\s*([^=]+)/g;
        line = line.replace(equationRegex, (match, leftSide, rightSide) => {
          existingLatexBlocks.push(`${leftSide} = ${rightSide}`);
          return `__LATEX_BLOCK_${existingLatexBlocks.length - 1}__`;
        });
      }
      
      return line;
    }).join('\n');
    
    // *** STEP 3: FORMAT EQUATION BLOCKS WITH PROPER DELIMITERS ***
    // Now format each captured LaTeX expression appropriately
    existingLatexBlocks.forEach((block, index) => {
      const placeholder = `__LATEX_BLOCK_${index}__`;
      
      // Check if this is an equation block (simple test: contains = sign)
      const isEquation = block.includes('=');
      
      // Check if it's a more complex formula with LaTeX commands
      const hasLatexCommand = latexCommands.some(cmd => block.includes(cmd));
      
      // Special handling for \text expressions - ensure they're always formatted correctly
      const containsText = block.includes('\\text');
      
      if (isEquation || (hasLatexCommand && !containsText)) {
        // For display math (centered equations), use double dollar signs
        processedText = processedText.replace(placeholder, `$$${block}$$`);
      } else if (containsText && block.includes('\\frac')) {
        // For \text expressions containing fractions (likely ROI formulas)
        processedText = processedText.replace(placeholder, `$$${block}$$`);
      } else {
        // For inline math, use single dollar signs
        processedText = processedText.replace(placeholder, `$${block}$`);
      }
    });

    // *** STEP 4: HANDLE SPECIAL CASES FOR COMMON ROI PATTERNS ***
    // These patterns are common in ROI calculations but more generalized now
    processedText = processedText
      // Handle substitution lines
      .replace(/(Substituting(?:\s+in(?:\s+our)?\s+values)?:?)\s*([^$]*)(\$\$[^$]+\$\$)/gi, 
        (match, prefix, middle, formula) => `${prefix}\n\n${formula}`)
      
      // Handle calculation results
      .replace(/(Calculating this gives:?)\s*([^$]*)(\$\$[^$]+\$\$)/gi, 
        (match, prefix, middle, formula) => `${prefix}\n\n${formula}`)
      
      // Fix basic formula introductions
      .replace(/(To calculate the ROI,[^:]*:?)\s*([^$]*)(\$\$[^$]+\$\$)/gi, 
        (match, prefix, middle, formula) => `${prefix}\n\n${formula}`)
      
      // Fix ROI percentage headers followed immediately by formulas
      .replace(/(Estimated ROI Percentage)\s*\n+-+\s*\n+\s*(\$\$[^$]+\$\$)/gi, 
        (match, header, formula) => `${header}\n\n---\n\n${formula}`);
    
    // *** STEP 5: FINAL CLEANUP ***
    // Ensure all \text{ROI} expressions are properly formatted
    processedText = processedText
      // Convert inline \text{ROI} to double dollar if part of an equation
      .replace(/\$\\text\{(ROI|Payback Period)\}([^$]*=[\s\S]*?)\$/g, '$$\\text{$1}$2$$')
      
      // Properly format colored text in LaTeX
      .replace(/\\color\{([^}]+)\}\{([^}]+)\}/g, '\\color{$1}{$2}')
      
      // Ensure proper spacing around display math
      .replace(/(\$\$[^$]+\$\$)([^\s\n])/g, '$1\n\n$2')
      .replace(/([^\s\n])(\$\$[^$]+\$\$)/g, '$1\n\n$2')
      
      // Fix any lines starting with formulas by ensuring space
      .replace(/^(\$\$)/gm, '\n$1')
      .replace(/(\$\$)$/gm, '$1\n')
      
      // Remove any backslash-escaped dollar signs in equations
      .replace(/\\\$/g, '$')
      
      // Fix any double spaces
      .replace(/\s{2,}/g, ' ');
    
    return processedText;
  };

  // Format currency values with commas
  const formatCurrency = (text: string): string => {
    return text.replace(/\$(\d+)(?=\D)/g, (match, number) => {
      return '$' + Number(number).toLocaleString();
    });
  };

  const sendMessage = async () => {
    if (inputValue.trim() === '' || isLoading) return;
    
    // Clear any transient errors
    setError(null);
    
    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue.trim(),
      sender: 'user',
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    
    // If service is unavailable, provide a fallback message
    if (serviceStatus === 'unavailable') {
      setTimeout(() => {
        const fallbackMessage: Message = {
          id: (Date.now() + 1).toString(),
          content: 'I apologize, but the ROI Assistant service is currently unavailable. Please try again later or contact support if the issue persists.',
          sender: 'assistant',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, fallbackMessage]);
        setIsLoading(false);
      }, 1000);
      return;
    }
    
    try {
      // Call backend API with Azure AI Agent Service
      const response = await axios.post(
        `${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/ask`, 
        {
          question: userMessage.content,
          context: roiContext,
          sessionId: sessionId,
          contextVersion: roiContext?.contextVersion || '',
          isNewSession: isNewSession
        }
      );
      
      // Reset the new session flag after the first message
      if (isNewSession) {
        setIsNewSession(false);
      }
      
      // Handle successful response
      if (response.data && response.data.answer) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          content: response.data.answer,
          sender: 'assistant',
          timestamp: new Date(),
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        
        // Store session ID if returned from backend
        if (response.data.sessionId) {
          setSessionId(response.data.sessionId);
        }
      } else {
        throw new Error('Received invalid response from assistant');
      }
    } catch (error) {
      console.error('Error sending message:', error);
      
      // Get the error message
      let errorMessage = 'Sorry, I encountered an error processing your question. Please try again.';
      if (axios.isAxiosError(error) && error.response?.data?.error) {
        errorMessage = `Error: ${error.response.data.error}`;
      } else if (error instanceof Error) {
        errorMessage = `Error: ${error.message}`;
      }
      
      const errorResponseMessage: Message = {
        id: (Date.now() + 2).toString(),
        content: errorMessage,
        sender: 'assistant',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorResponseMessage]);
      setError('An error occurred. Service might be unavailable.');
      setServiceStatus('unavailable');
    } finally {
      setIsLoading(false);
    }
  };

  const retryConnection = async () => {
    setError('Checking service status...');
    setServiceStatus('checking');
    
    try {
      const response = await axios.get(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/agent_health`);
      if (response.data.status === 'available') {
        setServiceStatus('available');
        setError(null);
        
        // Add a system message
        const systemMessage: Message = {
          id: Date.now().toString(),
          content: 'Connection restored! You can now ask questions about your ROI calculations.',
          sender: 'assistant',
          timestamp: new Date(),
        };
        
        setMessages(prev => [...prev, systemMessage]);
      } else {
        setServiceStatus('unavailable');
        setError('ROI Assistant service is still unavailable. Please try again later.');
      }
    } catch (error) {
      console.error('Error rechecking service:', error);
      setServiceStatus('unavailable');
      setError('ROI Assistant service is currently unavailable. Please try again later.');
    }
  };

  return (
    <div 
      ref={chatContainerRef}
      className="flex flex-col h-full bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-hidden" 
      style={{ 
        maxHeight: 'calc(100vh - 80px)', 
        height: `${chatHeight}px`,
        resize: 'vertical',
      }}
      onMouseUp={handleResize}
    >
      {/* Chat header */}
      <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 text-gray-800 dark:text-white flex-shrink-0 rounded-t-lg">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">ROI Assistant</h2>
          {serviceStatus === 'unavailable' && (
            <button 
              onClick={retryConnection}
              className="text-xs bg-blue-500 hover:bg-blue-600 text-white py-1 px-2 rounded"
            >
              Retry Connection
            </button>
          )}
        </div>
        <div className="flex justify-between items-center">
          <p className="text-xs text-gray-600 dark:text-gray-300">Ask questions about your ROI calculations</p>
        </div>
        {error && (
          <p className="text-xs text-red-500 mt-1">{error}</p>
        )}
      </div>
      
      {/* Messages container with flex height */}
      <div
        ref={messagesContainerRef}
        className="flex-1 p-4 overflow-y-auto" 
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
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-none roi-analysis'
              }`}
            >
              {message.sender === 'assistant' ? (
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    // Customize heading styles for chat
                    h3: ({node, ...props}) => <h3 className="text-base font-bold mt-2 mb-1 text-blue-600 dark:text-blue-400" {...props} />,
                    // Customize paragraph styles
                    p: ({node, ...props}) => <p className="mb-2" {...props} />,
                    // Customize list styles
                    li: ({node, ...props}) => <li className="ml-4" {...props} />
                  }}
                >
                  {formatCurrency(prepareContent(message.content))}
                </ReactMarkdown>
              ) : (
                message.content
              )}
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
            placeholder={serviceStatus === 'unavailable' 
              ? "Service unavailable. You can still type a message..." 
              : "Ask a question about your ROI..."}
            className="flex-1 resize-none overflow-hidden rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 p-2 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[40px] max-h-[120px]"
            rows={1}
            disabled={isLoading}
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