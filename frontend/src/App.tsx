// src/App.tsx
import React, { useState, useRef, ChangeEvent } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import MainLayout from './layouts/MainLayout';
import Card from './components/ui/Card';
import { GenerateResponse } from './types/api';

const App: React.FC = () => {
  const [budget, setBudget] = useState<string>('');
  const [employees, setEmployees] = useState<string>('');
  const [duration, setDuration] = useState<string>('');
  const [files, setFiles] = useState<File[]>([]);
  const [response, setResponse] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const fileArray = Array.from(e.target.files);
      setFiles(fileArray);
    }
  };

  const calculateROI = async () => {
    // Validate inputs
    if (!budget.trim() || !employees.trim() || !duration.trim()) {
      toast.error('Please fill in all required fields!');
      return;
    }

    try {
      setLoading(true);
      
      // Prepare data for the direct ROI calculation endpoint
      const fileNames = files.length > 0 
        ? files.map(f => f.name) 
        : [];

      // Send the request to the API
      const response = await axios.post<GenerateResponse>(
        `${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/calculate_roi`,
        { 
          budget: budget,
          employees: employees,
          duration: duration,
          files: fileNames
        },
        {
          headers: { 
            'Content-Type': 'application/json'
          }
        }
      );
      
      setResponse(response.data.response);
    } catch (error) {
      console.error(error);
      toast.error('Failed to calculate ROI. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-800 dark:text-gray-100">ROI Calculator Dashboard</h1>
        <Card>
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-6">
              <div>
                <label htmlFor="budget" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Project Budget ($)
                </label>
                <input
                  type="number"
                  id="budget"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md 
                            focus:outline-none focus:ring-2 focus:ring-blue-500
                            bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100"
                  placeholder="Enter project budget"
                />
              </div>
              
              <div>
                <label htmlFor="employees" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Number of Impacted Employees
                </label>
                <input
                  type="number"
                  id="employees"
                  value={employees}
                  onChange={(e) => setEmployees(e.target.value)}
                  className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md 
                            focus:outline-none focus:ring-2 focus:ring-blue-500
                            bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100"
                  placeholder="Enter number of employees"
                />
              </div>
              
              <div>
                <label htmlFor="duration" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Project Duration (months)
                </label>
                <input
                  type="number"
                  id="duration"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md 
                            focus:outline-none focus:ring-2 focus:ring-blue-500
                            bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100"
                  placeholder="Enter project duration"
                />
              </div>
            </div>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Upload Supporting Documents
                </label>
                <div className="flex items-center justify-center w-full">
                  <label
                    htmlFor="fileUpload"
                    className="flex flex-col items-center justify-center w-full h-32 
                               border-2 border-gray-300 dark:border-gray-600 border-dashed rounded-lg 
                               cursor-pointer bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                      <svg
                        className="w-8 h-8 mb-4 text-gray-500 dark:text-gray-400"
                        aria-hidden="true"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 20 16"
                      >
                        <path
                          stroke="currentColor"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M10 13.333 4.667 8 10 2.667M4.667 8h10.666"
                        />
                      </svg>
                      <p className="mb-2 text-sm text-gray-500 dark:text-gray-400">
                        <span className="font-semibold">Click to upload</span> or drag and drop
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Word, PDF, Excel (MAX. 10MB)</p>
                    </div>
                    <input
                      id="fileUpload"
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      multiple
                      onChange={handleFileChange}
                      accept=".doc,.docx,.pdf,.xls,.xlsx,.csv"
                    />
                  </label>
                </div>
                {files.length > 0 && (
                  <div className="mt-2">
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {files.length} file(s) selected: {files.map(f => f.name).join(', ')}
                    </p>
                  </div>
                )}
              </div>
              
              <button
                className={`w-full px-6 py-2 rounded-md text-white font-medium mt-6 ${
                  loading ? 'bg-gray-400 dark:bg-gray-600' : 'bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700'
                }`}
                onClick={calculateROI}
                disabled={loading}
              >
                {loading ? 'Calculating...' : 'Calculate ROI'}
              </button>
            </div>
          </div>

          {response && (
            <div className="mt-6 p-6 bg-gray-50 dark:bg-gray-800 rounded-lg shadow-sm">
              <h2 className="text-xl font-bold mb-4 text-blue-700 dark:text-blue-400 border-b border-gray-200 dark:border-gray-700 pb-2">ROI Analysis</h2>
              <div className="text-gray-800 dark:text-gray-200 text-base leading-relaxed whitespace-pre-wrap font-light">{response}</div>
            </div>
          )}
        </Card>
      </div>
      <ToastContainer theme="colored" />
    </MainLayout>
  );
};

export default App;
