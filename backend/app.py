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
        custom_fields = data.get('customFields', {})
        
        if not budget or not employees or not duration:
            return jsonify({'error': 'Budget, employees, and duration are required'}), 400
            
        # Format the input for the AI model
        # Prepare custom fields section if any custom fields were provided
        custom_fields_text = ""
        if custom_fields:
            custom_fields_text = "- Custom Inputs:\n"
            for field_name, field_value in custom_fields.items():
                # Try to determine if this is a numeric field (possibly with % or $ symbols)
                clean_value = field_value.strip().replace('$', '').replace('%', '').replace(',', '')
                value_display = field_value
                
                try:
                    # If it can be converted to float, it's numeric
                    float(clean_value)
                    # Add back any special symbols for display
                    if field_value.strip().startswith('$'):
                        value_display = f"${clean_value}"
                    elif field_value.strip().endswith('%'):
                        value_display = f"{clean_value}%"
                except ValueError:
                    # Not a numeric value, leave as is
                    pass
                
                custom_fields_text += f"  - {field_name}: {value_display}\n"
        
        user_message = f"""
Project ROI Analysis Request:
- Budget: ${budget}
- Number of Impacted Employees: {employees}
- Project Duration: {duration} months
{f"- Supporting Documents: {', '.join(files)}" if files else "- No supporting documents provided"}
{custom_fields_text}

Please provide a detailed ROI analysis for this change management project. Include:
1. Executive summary
2. Cost-benefit analysis with detailed calculations
3. Estimated ROI percentage
4. Payback period
5. Key risks and assumptions
6. Recommendations

IMPORTANT: You MUST incorporate ALL the custom fields provided above into your ROI calculations. 
For each custom field, explain how it impacts the ROI calculation and show the math clearly.
The custom field values should be used as direct inputs to your calculations and be explicitly
referenced in your formulas. For example, if "Hourly Rate" is provided, use this exact value
in your calculations rather than making assumptions.

Present the ROI calculation using clear formatting. For numeric values, ensure proper currency formatting with commas for thousands. Format the ROI calculation formula clearly showing how the ROI percentage is derived.
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
