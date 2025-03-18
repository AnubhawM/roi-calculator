// src/layouts/MainLayout.tsx
import React, { useState, useEffect } from 'react';
import Header from '../components/Header';
import ChatInterface from '../components/ChatInterface';
import ChatToggleButton from '../components/ChatToggleButton';

interface MainLayoutProps {
  children: React.ReactNode;
  roiContext?: {
    budget: string;
    employees: string;
    duration: string;
    customFields: any[];
    roiResults?: string;
  };
}

const MainLayout: React.FC<MainLayoutProps> = ({ children, roiContext }) => {
  const [isChatOpen, setIsChatOpen] = useState<boolean>(false);
  const [isDesktop, setIsDesktop] = useState<boolean>(false);

  // Handle resize events to toggle chat visibility based on screen size
  useEffect(() => {
    const handleResize = () => {
      const desktop = window.innerWidth >= 1200;
      setIsDesktop(desktop);
      
      // On desktop, the chat should be visible by default
      if (desktop) {
        setIsChatOpen(true);
      } else {
        setIsChatOpen(false);
      }
    };

    // Initial check
    handleResize();

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleChat = () => {
    setIsChatOpen(!isChatOpen);
  };

  return (
    <div className="w-full min-h-screen bg-gray-100 dark:bg-gray-900 transition-colors duration-200">
      <Header />
      
      {/* Two-column layout with auto margins */}
      <div className="max-w-[1400px] mx-auto px-4 mt-4 flex flex-wrap">
        {/* Main content - first column */}
        <div className="flex-1 min-w-0 lg:pr-4">
          {children}
        </div>
        
        {/* Chat interface - second column */}
        <div className={`
          w-[300px] lg:ml-4 flex-shrink-0
          ${isDesktop ? 'lg:block' : isChatOpen ? 'block fixed right-0 top-[60px] h-[calc(100vh-60px)] z-10 bg-gray-100 dark:bg-gray-900' : 'hidden'}
        `}>
          <div className="sticky top-[60px] pt-2 h-[600px]">
            <ChatInterface roiContext={roiContext} />
          </div>
        </div>
      </div>
      
      {/* Only show toggle button on smaller screens */}
      {!isDesktop && (
        <ChatToggleButton isOpen={isChatOpen} onClick={toggleChat} />
      )}
    </div>
  );
};

export default MainLayout;
