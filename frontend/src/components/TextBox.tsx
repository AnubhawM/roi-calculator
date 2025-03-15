import React from 'react';

interface TextBoxProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  placeholder: string;
  onGenerate: () => void;
  loading: boolean;
}

const TextBox: React.FC<TextBoxProps> = ({ 
  value, 
  onChange, 
  placeholder, 
  onGenerate,
  loading 
}) => {
  return (
    <div className="w-full">
      <textarea
        className="w-full p-4 bg-gray-50 border border-gray-200 rounded-md mb-4 resize-none"
        rows={5}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
      />
      <button
        className={`w-full px-6 py-2 rounded-md text-white font-medium ${
          loading ? 'bg-gray-400' : 'bg-blue-500 hover:bg-blue-600'
        }`}
        onClick={onGenerate}
        disabled={loading}
      >
        {loading ? 'Generating...' : 'Generate'}
      </button>
    </div>
  );
};

export default TextBox;
