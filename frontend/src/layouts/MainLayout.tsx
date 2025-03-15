// src/layouts/MainLayout.tsx
import React from 'react';
import Header from '../components/Header';

const MainLayout: React.FC<{children: React.ReactNode}> = ({children}) => {
  return (
    <div className="w-full min-h-screen bg-gray-100 dark:bg-gray-900 transition-colors duration-200">
      <Header />
      <main className="w-screen">
        <div className="w-screen">
          {children}
        </div>
      </main>
    </div>
  );
};

export default MainLayout;
