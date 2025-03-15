from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
import tempfile
import uuid
import mimetypes

# Load environment variables from .env file
load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
)
deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')

# Initialize Flask app
app = Flask(__name__)

# Configure CORS for specific frontend URL
CORS(app, 
    origins="http://localhost:5173",
    allow_headers=["Content-Type"],
    methods=["GET", "POST", "OPTIONS"])

# Add CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = "http://localhost:5173"
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.route('/')
def health_check():
    return "OK", 200

# Handle preflight OPTIONS requests explicitly
@app.route('/calculate_roi', methods=['OPTIONS'])
def handle_roi_options():
    response = make_response()
    response.headers['Access-Control-Allow-Origin'] = "http://localhost:5173"
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ROI calculations endpoint using Azure OpenAI
@app.route('/calculate_roi', methods=['POST'])
def calculate_roi():
    try:
        # Parse incoming JSON data
        data = request.json

        if not data:
            return jsonify({'error': 'Request data is required'}), 400
            
        # Extract ROI parameters
        budget = data.get('budget')
        employees = data.get('employees')
        duration = data.get('duration')
        files = data.get('files', [])
        
        if not budget or not employees or not duration:
            return jsonify({'error': 'Budget, employees, and duration are required'}), 400
            
        # Format the input for the AI model
        user_message = f"""
Project ROI Analysis Request:
- Budget: ${budget}
- Number of Impacted Employees: {employees}
- Project Duration: {duration} months
{f"- Supporting Documents: {', '.join(files)}" if files else "- No supporting documents provided"}

Please provide a detailed ROI analysis for this change management project. Include:
1. Executive summary
2. Cost-benefit analysis
3. Estimated ROI percentage
4. Payback period
5. Key risks and assumptions
6. Recommendations
        """
        
        try:
            # Call Azure OpenAI API
            response = client.chat.completions.create(
                model=deployment_name,  # Use deployment name for Azure
                messages=[
                    {"role": "system", "content": "You are a change management specialist, assisting leaders with providing analysis and insights."},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1000,
                temperature=0.7,
            )

            # Extract and return the generated response
            response_text = response.choices[0].message.content.strip()
            return jsonify({'response': response_text}), 200
                
        except Exception as e:
            print(f"Error calling Azure AI service: {e}")
            return jsonify({'error': f'Failed to generate ROI analysis: {str(e)}'}), 500

    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({'error': f'Failed to process request: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
