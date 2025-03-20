// src/App.tsx
import React, { useState, useRef, ChangeEvent, useEffect } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import MainLayout from './layouts/MainLayout';
import Card from './components/ui/Card';
import { GenerateResponse } from './types/api';
import UploadIcon from './components/UploadIcon';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './styles/ROIAnalysis.css';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Area, AreaChart
} from 'recharts';

// Custom field type definition
interface CustomField {
  id: string;
  title: string;
  value: string;
}

// Interface for extracted document data
interface ExtractedData {
  filename: string;
  financial_data: Record<string, string>;
  key_metrics: Record<string, string>;
  dates: Record<string, string>;
  entities: Array<{
    category: string;
    content: string;
    confidence: number | null;
  }>;
  tables?: Array<Array<Array<string>>>;
  error?: string;
  raw_text?: string;
  model_used?: string;
}

interface DocumentProcessingResult {
  results: ExtractedData[];
  message: string;
}

// Interface for chart data
interface ChartData {
  roi: number;
  costSavings: number;
  paybackPeriod: number;
  npv: number;
  totalCost: number;
  totalBenefit: number;
  annualBenefit: number;
  monthlyData?: Array<{
    month: number;
    cost: number;
    benefit: number;
    cumulativeBenefit: number;
  }>;
}

const App: React.FC = () => {
  const [budget, setBudget] = useState<string>('');
  const [employees, setEmployees] = useState<string>('');
  const [duration, setDuration] = useState<string>('');
  const [files, setFiles] = useState<File[]>([]);
  const [response, setResponse] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [documentLoading, setDocumentLoading] = useState<boolean>(false);
  const [extractedData, setExtractedData] = useState<ExtractedData[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // State for custom fields
  const [customFields, setCustomFields] = useState<CustomField[]>([]);
  const [showAddField, setShowAddField] = useState<boolean>(false);
  const [newFieldTitle, setNewFieldTitle] = useState<string>('');

  // Add a state to track the newly added field
  const [newFieldId, setNewFieldId] = useState<string | null>(null);

  // ROI context for the chat interface
  const roiContext = {
    budget,
    employees,
    duration,
    customFields,
    roiResults: response
  };

  // Generate a version hash for ROI context
  const calculateContextVersion = (): string => {
    // Create a string representation of the context data
    const contextString = `${budget}|${employees}|${duration}|${customFields.map(field => 
      `${field.title}:${field.value}`).join('|')}|${response ? response.substring(0, 100) : ''}`;
    
    // Generate a simple hash
    let hash = 0;
    for (let i = 0; i < contextString.length; i++) {
      const char = contextString.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    
    // Return as a string
    return hash.toString();
  };

  const contextVersion = calculateContextVersion();

  const [chartData, setChartData] = useState<ChartData>({
    roi: 0,
    costSavings: 0,
    paybackPeriod: 0,
    npv: 0,
    totalCost: 0,
    totalBenefit: 0,
    annualBenefit: 0
  });

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const fileArray = Array.from(e.target.files);
      setFiles(fileArray);
      
      // If files are selected, process them with Document Intelligence
      if (fileArray.length > 0) {
        processDocuments(fileArray);
      }
    }
  };

  // Process documents with Azure Document Intelligence
  const processDocuments = async (files: File[]) => {
    try {
      setDocumentLoading(true);
      
      // Create a FormData object to send files
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });
      
      // Send request to the document intelligence endpoint
      const response = await axios.post<DocumentProcessingResult>(
        `${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/document_intelligence`,
        formData,
        {
          headers: { 
            'Content-Type': 'multipart/form-data'
          }
        }
      );
      
      // Set the extracted data
      setExtractedData(response.data.results);
      
      // Check for any errors in the results
      const hasErrors = response.data.results.some(doc => doc.error);
      
      if (hasErrors) {
        const errorCount = response.data.results.filter(doc => doc.error).length;
        toast.warning(`Processed ${files.length} document(s), but ${errorCount} had errors. See details below.`);
      } else {
        toast.success(`Successfully processed ${files.length} document(s)`);
      }
      
      // Automatically populate form fields if data is available
      const validResults = response.data.results.filter(doc => !doc.error);
      if (validResults.length > 0) {
        populateFormFieldsFromDocuments(validResults);
      }
    } catch (error) {
      console.error('Error processing documents:', error);
      toast.error('Failed to process documents. Please try again.');
      // Create a placeholder result with the error
      const errorResults = files.map(file => ({
        filename: file.name,
        error: error instanceof Error ? error.message : 'Unknown error processing document',
        financial_data: {},
        key_metrics: {},
        dates: {},
        entities: []
      }));
      setExtractedData(errorResults);
    } finally {
      setDocumentLoading(false);
    }
  };
  
  // Populate form fields based on extracted document data
  const populateFormFieldsFromDocuments = (results: ExtractedData[]) => {
    if (!results || results.length === 0) return;
    
    // Try to extract budget from financial data
    for (const result of results) {
      const financialData = result.financial_data;
      // Look for budget-related keys
      for (const [key, value] of Object.entries(financialData)) {
        if (key.includes('budget') && !budget) {
          // Extract numeric value from the string
          const numericValue = value.replace(/[^0-9.]/g, '');
          if (numericValue) {
            setBudget(numericValue);
            break;
          }
        }
      }
      
      // Look for employee-related keys in key metrics
      const metrics = result.key_metrics;
      for (const [key, value] of Object.entries(metrics)) {
        if ((key.includes('employee') || key.includes('headcount')) && !employees) {
          // Extract numeric value from the string
          const numericValue = value.replace(/[^0-9.]/g, '');
          if (numericValue) {
            setEmployees(numericValue);
            break;
          }
        }
      }
      
      // Look for duration-related keys in dates
      const dates = result.dates;
      for (const [key, value] of Object.entries(dates)) {
        if (key.includes('duration') && !duration) {
          // Extract numeric value from the string
          const numericValue = value.replace(/[^0-9.]/g, '');
          if (numericValue) {
            setDuration(numericValue);
            break;
          }
        }
      }
      
      // Look for other relevant custom fields
      let newCustomFields: CustomField[] = [...customFields];
      for (const [key, value] of Object.entries(financialData)) {
        // Skip budget as it's already a standard field
        if (key.includes('budget')) continue;
        
        // Add as custom field if it's a relevant financial metric
        if (
          key.includes('cost') || key.includes('rate') || 
          key.includes('price') || key.includes('saving') ||
          key.includes('revenue') || key.includes('benefit')
        ) {
          const numericValue = value.replace(/[^0-9.]/g, '');
          if (numericValue) {
            const newField: CustomField = {
              id: `custom-${Date.now()}-${key}`,
              title: key.charAt(0).toUpperCase() + key.slice(1), // Capitalize first letter
              value: numericValue
            };
            newCustomFields.push(newField);
          }
        }
      }
      
      if (newCustomFields.length > customFields.length) {
        setCustomFields(newCustomFields);
      }
    }
  };

  // Function to prepare content for LaTeX rendering
  const prepareContent = (text: string): string => {
    if (!text) return '';
    
    // Ensure proper bullet point formatting with a space after dash
    let processedText = text.replace(/^-([^\s])/gm, '- $1');
    
    // Handle currency notation to prevent it from being interpreted as LaTeX
    // We need a different approach that won't show the backslashes
    processedText = processedText.replace(/\$(\d[\d,]*(?:\.\d+)?)/g, (match) => {
      // Use a temporary placeholder that KaTeX won't interpret as math
      return '\\$' + match.substring(1);
    });
    
    // Ensure proper line breaks in markdown
    processedText = processedText.replace(/([^\n])\n([^\n])/g, '$1\n\n$2');
    
    return processedText;
  };

  // Format currency values with commas
  const formatCurrency = (text: string): string => {
    return text.replace(/\$(\d+)(?=\D)/g, (match, number) => {
      return '$' + Number(number).toLocaleString();
    });
  };

  // Handle adding a new custom field
  const handleAddField = () => {
    const newField: CustomField = {
      id: `custom-${Date.now()}`,
      title: '',
      value: ''
    };

    setCustomFields([...customFields, newField]);
  };

  // Handle removing a custom field
  const handleRemoveField = (id: string) => {
    setCustomFields(customFields.filter(field => field.id !== id));
  };

  // Handle updating a custom field title
  const handleCustomFieldTitleChange = (id: string, title: string) => {
    setCustomFields(customFields.map(field => 
      field.id === id ? { ...field, title } : field
    ));
  };

  // Handle updating a custom field value
  const handleCustomFieldValueChange = (id: string, value: string) => {
    setCustomFields(customFields.map(field => 
      field.id === id ? { ...field, value } : field
    ));
  };

  // Handle adding an extracted data point as a custom field
  const addExtractedDataAsCustomField = (key: string, value: string) => {
    // Format the value to extract just the numeric part if it has $ or %
    let formattedValue = value;
    
    // Remove $ or % and commas from the value to get just the number
    if (value.includes('$') || value.includes('%') || value.includes(',')) {
      formattedValue = value
        .replace(/[$,]/g, '') // Remove $ and commas
        .replace(/%$/, '');   // Remove trailing % if present
    }
    
    // Create a new unique ID for this field
    const newId = `custom-${Date.now()}-${key}`;
    
    // Create a new custom field
    const newField: CustomField = {
      id: newId,
      title: key.charAt(0).toUpperCase() + key.slice(1), // Capitalize first letter
      value: formattedValue
    };
    
    // Add to custom fields
    setCustomFields([...customFields, newField]);
    
    // Track this field as newly added (for animation)
    setNewFieldId(newId);
    
    // Clear the "new" status after animation completes
    setTimeout(() => {
      setNewFieldId(null);
    }, 2000);
    
    // Show success message
    toast.success(`Added "${key}" to custom fields`);
    
    // Scroll to custom fields section
    const customFieldsSection = document.getElementById('custom-fields-section');
    if (customFieldsSection) {
      customFieldsSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Add a new function to handle adding table cell data as custom field
  const addTableCellAsCustomField = (rowIndex: number, colIndex: number, table: string[][], tableIdx: number) => {
    // Get the cell value
    const value = table[rowIndex][colIndex];
    
    // Skip if the cell is empty or doesn't look like a number/metric
    if (!value || value.trim() === '') return;
    
    // Try to identify row and column headers to create a meaningful field name
    let fieldName = '';
    
    // First row usually contains column headers
    const columnHeader = table[0][colIndex];
    
    // First column usually contains row headers
    const rowHeader = table[rowIndex][0];
    
    // Only use header info if it's not empty
    if (columnHeader && rowHeader && columnHeader !== rowHeader) {
      // Combine row and column headers for a descriptive name
      fieldName = `${rowHeader} ${columnHeader.toLowerCase()}`;
    } else if (columnHeader) {
      fieldName = columnHeader;
    } else if (rowHeader) {
      fieldName = rowHeader;
    } else {
      // Fallback - use table index and cell coordinates
      fieldName = `Table ${tableIdx + 1} data (${rowIndex},${colIndex})`;
    }
    
    // Format the value to extract just the numeric part
    let formattedValue = value;
    
    // Remove $ or % and commas from the value to get just the number
    if (value.includes('$') || value.includes('%') || value.includes(',')) {
      formattedValue = value
        .replace(/[$,]/g, '') // Remove $ and commas
        .replace(/%$/, '');   // Remove trailing % if present
    }
    
    // Create a new unique ID for this field
    const newId = `custom-${Date.now()}-table-${tableIdx}-${rowIndex}-${colIndex}`;
    
    // Create a new custom field
    const newField: CustomField = {
      id: newId,
      title: fieldName.charAt(0).toUpperCase() + fieldName.slice(1), // Capitalize first letter
      value: formattedValue
    };
    
    // Add to custom fields
    setCustomFields([...customFields, newField]);
    
    // Track this field as newly added (for animation)
    setNewFieldId(newId);
    
    // Clear the "new" status after animation completes
    setTimeout(() => {
      setNewFieldId(null);
    }, 2000);
    
    // Show success message
    toast.success(`Added "${fieldName}" to custom fields`);
    
    // Scroll to custom fields section
    const customFieldsSection = document.getElementById('custom-fields-section');
    if (customFieldsSection) {
      customFieldsSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Function to extract numeric data from response text for charts
  const extractChartDataFromResponse = (text: string): ChartData => {
    const data: ChartData = {
      roi: 0,
      costSavings: 0,
      paybackPeriod: 0,
      npv: 0,
      totalCost: 0,
      totalBenefit: 0,
      annualBenefit: 0
    };
    
    try {
      // Extract ROI percentage
      const roiMatch = text.match(/ROI.*?(\d+(?:\.\d+)?)%/i);
      if (roiMatch && roiMatch[1]) {
        data.roi = parseFloat(roiMatch[1]);
      }
      
      // Extract cost savings
      const savingsMatch = text.match(/savings.*?\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)/i);
      if (savingsMatch && savingsMatch[1]) {
        data.costSavings = parseFloat(savingsMatch[1].replace(/,/g, ''));
      }
      
      // Extract payback period
      const paybackMatch = text.match(/payback period.*?(\d+(?:\.\d+)?)\s*(?:months|years)/i);
      if (paybackMatch && paybackMatch[1]) {
        data.paybackPeriod = parseFloat(paybackMatch[1]);
      }
      
      // Extract NPV if present
      const npvMatch = text.match(/NPV.*?\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)/i);
      if (npvMatch && npvMatch[1]) {
        data.npv = parseFloat(npvMatch[1].replace(/,/g, ''));
      }
      
      // Extract total cost
      const totalCostMatch = text.match(/total cost.*?\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)/i);
      if (totalCostMatch && totalCostMatch[1]) {
        data.totalCost = parseFloat(totalCostMatch[1].replace(/,/g, ''));
      } else {
        // Fallback - try to extract from budget
        data.totalCost = parseFloat(budget.replace(/,/g, '')) || 0;
      }
      
      // Extract total benefit
      const totalBenefitMatch = text.match(/total benefit.*?\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)/i);
      if (totalBenefitMatch && totalBenefitMatch[1]) {
        data.totalBenefit = parseFloat(totalBenefitMatch[1].replace(/,/g, ''));
      } else if (data.roi > 0 && data.totalCost > 0) {
        // Calculate total benefit from ROI and total cost
        data.totalBenefit = data.totalCost * (1 + data.roi / 100);
      }
      
      // Extract annual benefit or calculate it
      const annualBenefitMatch = text.match(/annual benefit.*?\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)/i);
      if (annualBenefitMatch && annualBenefitMatch[1]) {
        data.annualBenefit = parseFloat(annualBenefitMatch[1].replace(/,/g, ''));
      } else if (data.totalBenefit > 0 && duration) {
        // Calculate annual benefit based on total benefit and project duration
        const durationInYears = parseFloat(duration) / 12;
        data.annualBenefit = data.totalBenefit / durationInYears;
      }
      
      // Generate monthly data for a timeline chart if we have enough information
      if (data.totalCost > 0 && data.annualBenefit > 0 && duration) {
        const durationMonths = parseInt(duration);
        const monthlyData = [];
        const monthlyCost = data.totalCost / durationMonths;
        const monthlyBenefit = data.annualBenefit / 12;
        
        let cumulativeBenefit = 0;
        for (let i = 1; i <= durationMonths; i++) {
          cumulativeBenefit += monthlyBenefit;
          monthlyData.push({
            month: i,
            cost: i === 1 ? data.totalCost : 0, // Assume all costs incurred in month 1
            benefit: monthlyBenefit,
            cumulativeBenefit: cumulativeBenefit
          });
        }
        
        data.monthlyData = monthlyData;
      }
    } catch (e) {
      console.error("Error extracting chart data:", e);
    }
    
    return data;
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

      // Include custom fields in the request - only include fields with both title and value
      let validCustomFieldCount = 0;
      const customFieldsData = customFields.reduce((acc, field) => {
        if (field.title.trim() && field.value.trim()) {
          acc[field.title] = field.value;
          validCustomFieldCount++;
        }
        return acc;
      }, {} as Record<string, string>);

      // Notify if some custom fields were ignored
      const invalidCustomFieldCount = customFields.length - validCustomFieldCount;
      if (invalidCustomFieldCount > 0 && customFields.length > 0) {
        toast.info(`${invalidCustomFieldCount} incomplete custom field(s) will be ignored.`);
      }

      // Send the request to the API
      const response = await axios.post<GenerateResponse>(
        `${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/calculate_roi`,
        { 
          budget: budget,
          employees: employees,
          duration: duration,
          files: fileNames,
          customFields: customFieldsData,
          documentData: extractedData.length > 0 ? extractedData : undefined
        },
        {
          headers: { 
            'Content-Type': 'application/json'
          }
        }
      );
      
      setResponse(response.data.response);
      
      // Extract chart data from the response
      const extractedChartData = extractChartDataFromResponse(response.data.response);
      setChartData(extractedChartData);
    } catch (error) {
      console.error(error);
      toast.error('Failed to calculate ROI. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout roiContext={{...roiContext, contextVersion}}>
      <div>
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

              {/* Custom Fields Section */}
              <div id="custom-fields-section" className="mt-4 space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100">Custom Fields</h3>
                  <button
                    type="button"
                    onClick={handleAddField}
                    className="flex items-center text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
                    </svg>
                    Add Field
                  </button>
                </div>
                
                <p className="text-sm text-gray-600 dark:text-gray-400 italic">
                  Add custom fields to include additional factors in your ROI calculation. 
                  Examples: Hourly Rate, Training Costs, Expected Efficiency Gain (%).
                </p>
                
                {customFields.map((field) => (
                  <div 
                    key={field.id} 
                    className={`relative flex space-x-2 ${newFieldId === field.id ? 'custom-field-new rounded-lg' : ''}`}
                  >
                    <div className="flex-1">
                      <input
                        type="text"
                        placeholder="Field Name"
                        value={field.title}
                        onChange={(e) => handleCustomFieldTitleChange(field.id, e.target.value)}
                        className="w-full p-2.5 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg
                                  focus:ring-blue-500 focus:border-blue-500
                                  dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white"
                      />
                    </div>
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Value"
                        value={field.value}
                        onChange={(e) => handleCustomFieldValueChange(field.id, e.target.value)}
                        className="w-full p-2.5 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg
                                  focus:ring-blue-500 focus:border-blue-500
                                  dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveField(field.id)}
                      className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 000 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>
                ))}
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
                      <UploadIcon className="w-8 h-8 mb-4 text-gray-500 dark:text-gray-400" />
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
                {documentLoading && (
                  <div className="mt-2 flex items-center justify-center">
                    <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-500"></div>
                    <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">Processing documents...</span>
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
              <div className="text-gray-800 dark:text-gray-200 text-base leading-relaxed font-light roi-analysis">
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    // Customize heading styles
                    h3: ({node, ...props}) => <h3 className="text-lg font-bold mt-4 mb-2 text-blue-600 dark:text-blue-400" {...props} />,
                    // Customize paragraph styles
                    p: ({node, ...props}) => <p className="mb-3" {...props} />,
                    // Customize list styles
                    li: ({node, ...props}) => <li className="ml-4" {...props} />
                  }}
                >
                  {formatCurrency(prepareContent(response))}
                </ReactMarkdown>
              </div>
              
              {/* ROI Visualization Section - Using Recharts */}
              {chartData && (chartData.roi > 0 || chartData.totalCost > 0) && (
                <div className="mt-8 mb-2">
                  <h3 className="text-lg font-bold mb-4 text-blue-600 dark:text-blue-400">ROI Visualization</h3>
                  
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Cost-Benefit Comparison Chart */}
                    {chartData.totalCost > 0 && chartData.totalBenefit > 0 && (
                      <div className="bg-white dark:bg-gray-700 p-4 rounded-lg shadow">
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Cost-Benefit Analysis</h4>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                              data={[
                                { name: 'Cost', value: chartData.totalCost },
                                { name: 'Benefit', value: chartData.totalBenefit }
                              ]}
                              margin={{ top: 10, right: 10, left: 50, bottom: 20 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="name" />
                              <YAxis 
                                tickFormatter={(value) => `$${value.toLocaleString()}`} 
                                width={80}
                              />
                              <Tooltip formatter={(value) => [`$${Number(value).toLocaleString()}`, '']} />
                              <Legend wrapperStyle={{ paddingTop: '10px' }} />
                              <Bar dataKey="value" name="Amount" radius={[4, 4, 0, 0]}>
                                <Cell fill="#ef4444" />
                                <Cell fill="#22c55e" />
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
                          Net Benefit: ${(chartData.totalBenefit - chartData.totalCost).toLocaleString()}
                        </div>
                      </div>
                    )}
                    
                    {/* ROI and Payback Period Chart */}
                    {chartData.roi > 0 && (
                      <div className="bg-white dark:bg-gray-700 p-4 rounded-lg shadow">
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">ROI and Payback Period</h4>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={[
                                  { name: 'ROI', value: chartData.roi },
                                  { name: 'Baseline', value: 100 - chartData.roi > 0 ? 100 - chartData.roi : 0 }
                                ]}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                                label={({ name, percent }) => name === 'ROI' ? `${(percent * 100).toFixed(0)}%` : ''}
                              >
                                <Cell fill="#3b82f6" />
                                <Cell fill="#e5e7eb" />
                              </Pie>
                              <Tooltip formatter={(value, name) => [name === 'ROI' ? `${value}%` : '', name]} />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          <div className="text-center">
                            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">{chartData.roi.toFixed(1)}%</div>
                            <div className="text-sm text-gray-600 dark:text-gray-400">Return on Investment</div>
                          </div>
                          {chartData.paybackPeriod > 0 && (
                            <div className="text-center">
                              <div className="text-3xl font-bold text-orange-500 dark:text-orange-400">{chartData.paybackPeriod.toFixed(1)}</div>
                              <div className="text-sm text-gray-600 dark:text-gray-400">{chartData.paybackPeriod === 1 ? 'Month' : 'Months'} Payback</div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {/* Investment Timeline Chart */}
                    {chartData.monthlyData && chartData.monthlyData.length > 0 && (
                      <div className="bg-white dark:bg-gray-700 p-4 rounded-lg shadow lg:col-span-2">
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Investment Timeline</h4>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart
                              data={chartData.monthlyData}
                              margin={{ top: 20, right: 20, left: 50, bottom: 30 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis 
                                dataKey="month" 
                                label={{ 
                                  value: 'Month', 
                                  position: 'insideBottom', 
                                  offset: -15,
                                  style: { textAnchor: 'middle' }
                                }} 
                              />
                              <YAxis 
                                tickFormatter={(value) => `$${value.toLocaleString()}`} 
                                width={80}
                              />
                              <Tooltip formatter={(value) => [`$${Number(value).toLocaleString()}`, '']} />
                              <Legend 
                                verticalAlign="top" 
                                height={36}
                                wrapperStyle={{ paddingTop: '5px' }}
                              />
                              <Area type="monotone" dataKey="cumulativeBenefit" name="Cumulative Benefit" fill="#22c55e" stroke="#16a34a" fillOpacity={0.3} />
                              <Area type="monotone" dataKey="cost" name="Cost" fill="#ef4444" stroke="#dc2626" fillOpacity={0.3} />
                              <Line type="monotone" dataKey="benefit" name="Monthly Benefit" stroke="#3b82f6" strokeWidth={2} dot={false} />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
                          Break-even point occurs when cumulative benefits exceed initial costs
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Extracted Document Data Section */}
          {extractedData.length > 0 && (
            <div className="mt-6 p-6 bg-gray-50 dark:bg-gray-800 rounded-lg shadow-sm">
              <h2 className="text-xl font-bold mb-4 text-blue-700 dark:text-blue-400 border-b border-gray-200 dark:border-gray-700 pb-2">
                Extracted Document Data <span className="text-sm font-normal text-gray-600 dark:text-gray-400">(Click the green + button next to any data point to add it as a custom field)</span>
              </h2>
              <div className="space-y-4">
                {extractedData.map((docData, index) => (
                  <details key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4" open>
                    <summary className="text-lg font-semibold text-gray-800 dark:text-gray-200 cursor-pointer">
                      {docData.filename}
                    </summary>
                    
                    <div className="mt-4 pl-1">
                      {/* Show error if there was one */}
                      {docData.error && (
                        <div className="mb-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-red-600 dark:text-red-400">
                          <p className="font-medium">Error processing document:</p>
                          <p className="text-sm">{docData.error}</p>
                        </div>
                      )}
                      
                      {/* Show message if no data was extracted */}
                      {!docData.error && 
                        Object.keys(docData.financial_data).length === 0 && 
                        Object.keys(docData.key_metrics).length === 0 && 
                        Object.keys(docData.dates).length === 0 && 
                        (!docData.tables || docData.tables.length === 0) && 
                        !docData.raw_text && (
                          <div className="mb-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md text-yellow-700 dark:text-yellow-400">
                            <p>No structured data could be extracted from this document.</p>
                            <p className="text-sm mt-1">Try uploading a different format or a document with more clearly defined information.</p>
                          </div>
                      )}
                      
                      {/* Financial Data - make collapsible */}
                      {Object.keys(docData.financial_data).length > 0 && (
                        <div className="mb-3">
                          <details className="w-full" open>
                            <summary className="text-md font-medium mb-1 text-blue-600 dark:text-blue-400 cursor-pointer">
                              Financial Data
                            </summary>
                            <div className="bg-white dark:bg-gray-700 p-3 rounded-md mt-2">
                              <table className="w-full text-sm">
                                <tbody>
                                  {Object.entries(docData.financial_data).map(([key, value], idx) => (
                                    <tr key={idx} className="border-b border-gray-100 dark:border-gray-600">
                                      <td className="py-2 font-medium text-gray-600 dark:text-gray-300 capitalize">{key}</td>
                                      <td className="py-2 text-gray-800 dark:text-gray-100">{value}</td>
                                      <td className="py-2 w-10 text-right">
                                        <button 
                                          onClick={() => addExtractedDataAsCustomField(key, value)}
                                          className="text-green-500 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300"
                                          title={`Add "${key}" to custom fields`}
                                        >
                                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                            <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
                                          </svg>
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </details>
                        </div>
                      )}
                      
                      {/* Key Metrics - make collapsible */}
                      {Object.keys(docData.key_metrics).length > 0 && (
                        <div className="mb-3">
                          <details className="w-full" open>
                            <summary className="text-md font-medium mb-1 text-blue-600 dark:text-blue-400 cursor-pointer">
                              Key Metrics
                            </summary>
                            <div className="bg-white dark:bg-gray-700 p-3 rounded-md mt-2">
                              <table className="w-full text-sm">
                                <tbody>
                                  {Object.entries(docData.key_metrics).map(([key, value], idx) => (
                                    <tr key={idx} className="border-b border-gray-100 dark:border-gray-600">
                                      <td className="py-2 font-medium text-gray-600 dark:text-gray-300 capitalize">{key}</td>
                                      <td className="py-2 text-gray-800 dark:text-gray-100">{value}</td>
                                      <td className="py-2 w-10 text-right">
                                        <button 
                                          onClick={() => addExtractedDataAsCustomField(key, value)}
                                          className="text-green-500 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300"
                                          title={`Add "${key}" to custom fields`}
                                        >
                                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                            <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
                                          </svg>
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </details>
                        </div>
                      )}
                      
                      {/* Dates - make collapsible */}
                      {Object.keys(docData.dates).length > 0 && (
                        <div className="mb-3">
                          <details className="w-full" open>
                            <summary className="text-md font-medium mb-1 text-blue-600 dark:text-blue-400 cursor-pointer">
                              Timeline Information
                            </summary>
                            <div className="bg-white dark:bg-gray-700 p-3 rounded-md mt-2">
                              <table className="w-full text-sm">
                                <tbody>
                                  {Object.entries(docData.dates).map(([key, value], idx) => (
                                    <tr key={idx} className="border-b border-gray-100 dark:border-gray-600">
                                      <td className="py-2 font-medium text-gray-600 dark:text-gray-300 capitalize">{key}</td>
                                      <td className="py-2 text-gray-800 dark:text-gray-100">{value}</td>
                                      <td className="py-2 w-10 text-right">
                                        <button 
                                          onClick={() => addExtractedDataAsCustomField(key, value)}
                                          className="text-green-500 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300"
                                          title={`Add "${key}" to custom fields`}
                                        >
                                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                            <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
                                          </svg>
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </details>
                        </div>
                      )}
                      
                      {/* Tables - make collapsible */}
                      {docData.tables && docData.tables.length > 0 && (
                        <div className="mb-3">
                          <details className="w-full" open>
                            <summary className="text-md font-medium mb-1 text-blue-600 dark:text-blue-400 cursor-pointer">
                              Tables
                            </summary>
                            <div className="space-y-4 mt-2">
                              {docData.tables.map((table, tableIdx) => (
                                <div key={tableIdx} className="bg-white dark:bg-gray-700 p-3 rounded-md overflow-x-auto">
                                  <table className="w-full text-sm border-collapse">
                                    <tbody>
                                      {table.map((row, rowIdx) => (
                                        <tr key={rowIdx} className="border-b border-gray-100 dark:border-gray-600">
                                          {row.map((cell, cellIdx) => {
                                            // Check if the cell likely contains a numeric value
                                            const hasNumericValue = /\d/.test(cell) && 
                                                                   !cell.includes("No.") && 
                                                                   (rowIdx > 0 || cellIdx > 0); // Skip headers in first row/column
                                            
                                            return (
                                              <td key={cellIdx} className="py-2 px-2 border border-gray-200 dark:border-gray-600 relative">
                                                {cell}
                                                {hasNumericValue && (
                                                  <button 
                                                    onClick={() => addTableCellAsCustomField(rowIdx, cellIdx, table, tableIdx)}
                                                    className="absolute right-1 top-1 text-green-500 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300"
                                                    title="Add to custom fields"
                                                  >
                                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                                      <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
                                                    </svg>
                                                  </button>
                                                )}
                                              </td>
                                            );
                                          })}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              ))}
                            </div>
                          </details>
                        </div>
                      )}
                      
                      {/* Raw Text Content - already has a details tag */}
                      {docData.raw_text && (
                        <div className="mb-3">
                          <details>
                            <summary className="text-md font-medium mb-1 text-blue-600 dark:text-blue-400 cursor-pointer">
                              Document Content (Raw Text)
                            </summary>
                            <div className="bg-white dark:bg-gray-700 p-3 rounded-md mt-2">
                              <div className="max-h-60 overflow-y-auto text-sm text-gray-800 dark:text-gray-100 whitespace-pre-wrap">
                                {docData.raw_text}
                              </div>
                            </div>
                          </details>
                        </div>
                      )}
                      
                      {/* Document Model Used */}
                      {docData.model_used && (
                        <div className="mt-4 text-xs text-gray-500 dark:text-gray-400">
                          Processed with model: {docData.model_used}
                        </div>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
      <ToastContainer theme="colored" />
    </MainLayout>
  );
};

export default App;
