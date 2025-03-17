from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
import tempfile
import uuid
import mimetypes
import json
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
import base64
import io
import sys
import time
import openai

# Load environment variables from .env file
load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
)
deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')

# Initialize Azure Document Intelligence client
document_analysis_client = None
try:
    document_analysis_client = DocumentAnalysisClient(
        endpoint=os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'),
        credential=AzureKeyCredential(os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY'))
    )
    
    # Print diagnostics about the client
    print(f"Azure Document Analysis client initialized successfully")
    print(f"  - Endpoint: {os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')}")
    print(f"  - API Key set: {'Yes' if os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY') else 'No'}")
    print(f"  - SDK Methods: {', '.join([m for m in dir(document_analysis_client) if not m.startswith('_')])[:200]+'...'}")
except Exception as e:
    print(f"Error initializing Azure Document Analysis client: {e}")
    print("Document processing functionality will not be available")

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

# Document Intelligence endpoint for processing documents
@app.route('/document_intelligence', methods=['POST', 'OPTIONS'])
def document_intelligence():
    """Process documents using Azure Document Analysis"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response

    try:
        if 'files' not in request.files:
            return jsonify({"error": "No files provided"}), 400
        
        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            return jsonify({"error": "No files selected"}), 400
        
        results = []
        
        for file in files:
            try:
                # Create a temporary file to hold the uploaded content
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp:
                    file.save(temp.name)
                    temp_path = temp.name
                
                print(f"Processing file: {file.filename}, temp path: {temp_path}")
                
                # Try to analyze the document with different models
                document_result = None
                error = None
                
                # List of models to try in order of preference
                models_to_try = ["prebuilt-document", "prebuilt-layout", "prebuilt-read"]
                
                for model in models_to_try:
                    try:
                        print(f"Attempting to process {file.filename} with {model} model")
                        
                        # Read the file content for analysis
                        with open(temp_path, "rb") as f:
                            document_content = f.read()
                        
                        # Begin document analysis with the current model
                        poller = document_analysis_client.begin_analyze_document(
                            model,
                            document_content
                        )
                        document_result = poller.result()
                        
                        print(f"Successfully processed {file.filename} with {model} model")
                        break  # Exit loop if successful
                        
                    except Exception as e:
                        error = str(e)
                        print(f"Failed to process {file.filename} with {model} model: {error}")
                        continue  # Try next model
                
                if document_result:
                    # Extract relevant data for ROI calculation
                    extracted_data = extract_roi_relevant_data(document_result, file.filename)
                    results.append(extracted_data)
                else:
                    # If all models failed, add an error result
                    results.append({
                        "filename": file.filename,
                        "error": f"Failed to process document with any available model: {error}"
                    })
                
                # Clean up the temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    print(f"Warning: Could not delete temporary file {temp_path}: {e}")
                    
            except Exception as e:
                print(f"Error processing file {file.filename}: {str(e)}")
                results.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        return jsonify({"results": results})
    
    except Exception as e:
        print(f"Error in document_intelligence: {str(e)}")
        return jsonify({"error": str(e)}), 500

def extract_roi_relevant_data(document_result, filename):
    """
    Extract data relevant to ROI calculations from document analysis results
    """
    # Print diagnostic info about the document_result
    print(f"Document result type: {type(document_result)}")
    print(f"Document result attributes: {', '.join([a for a in dir(document_result) if not a.startswith('_')])[:200]+'...'}")
    
    # Initialize data structure for holding extracted information
    extracted_data = {
        'filename': filename,
        'financial_data': {},
        'key_metrics': {},
        'dates': {},
        'entities': [],
        'debug_info': {
            'result_type': str(type(document_result)),
            'has_key_value_pairs': hasattr(document_result, 'key_value_pairs'),
            'has_pages': hasattr(document_result, 'pages'),
            'has_tables': hasattr(document_result, 'tables'),
            'has_entities': hasattr(document_result, 'entities'),
            'document_type': getattr(document_result, 'document_type', 'unknown')
        }
    }
    
    # Extract key-value pairs from the document (form fields)
    if hasattr(document_result, 'key_value_pairs') and document_result.key_value_pairs is not None:
        print(f"Found {len(document_result.key_value_pairs)} key-value pairs")
        for kv_pair in document_result.key_value_pairs:
            if kv_pair.key and kv_pair.value:
                key_text = kv_pair.key.content.lower() if kv_pair.key.content else ""
                value_text = kv_pair.value.content if kv_pair.value.content else ""
                
                print(f"Found key-value pair: '{key_text}': '{value_text}'")
                
                # Categorize financial data
                if any(term in key_text for term in ['cost', 'budget', 'expense', 'price', 'investment', 'roi', 'return']):
                    extracted_data['financial_data'][key_text] = value_text
                # Categorize timeline data
                elif any(term in key_text for term in ['date', 'deadline', 'timeline', 'duration', 'period', 'start', 'end']):
                    extracted_data['dates'][key_text] = value_text
                # Categorize metrics
                elif any(term in key_text for term in ['rate', 'percentage', 'efficiency', 'productivity', 'employees', 'headcount']):
                    extracted_data['key_metrics'][key_text] = value_text
                else:
                    # If we can't categorize it, put it in the most appropriate category based on value
                    if '$' in value_text or any(c in value_text for c in '0123456789'):
                        if '%' in value_text:
                            extracted_data['key_metrics'][key_text] = value_text
                        else:
                            extracted_data['financial_data'][key_text] = value_text
    
    # Extract tables which may contain financial data
    tables_data = []
    if hasattr(document_result, 'tables') and document_result.tables is not None:
        print(f"Found {len(document_result.tables)} tables")
        for table in document_result.tables:
            print(f"Processing table: {table.row_count} rows, {table.column_count} columns")
            table_data = []
            for row in range(table.row_count):
                row_data = []
                for col in range(table.column_count):
                    # Find cells for this row and column
                    cell_content = ""
                    for cell in table.cells:
                        if cell.row_index == row and cell.column_index == col:
                            cell_content = cell.content
                            break
                    row_data.append(cell_content)
                table_data.append(row_data)
            tables_data.append(table_data)
    
    if tables_data:
        extracted_data['tables'] = tables_data
    
    # Extract named entities (people, organizations, locations)
    if hasattr(document_result, 'entities') and document_result.entities is not None:
        print(f"Found {len(document_result.entities)} entities")
        for entity in document_result.entities:
            if entity.category and entity.content:
                extracted_data['entities'].append({
                    'category': entity.category,
                    'content': entity.content,
                    'confidence': entity.confidence if hasattr(entity, 'confidence') else None
                })
    
    # Add text content as fallback when the model doesn't provide structured data
    raw_text = ""
    if hasattr(document_result, 'pages') and document_result.pages is not None:
        print(f"Found {len(document_result.pages)} pages")
        page_contents = []
        for page in document_result.pages:
            # Different models have different page content structures
            if hasattr(page, 'content') and page.content is not None:
                page_contents.append(page.content)
            # Try alternative content access patterns based on model type
            elif hasattr(page, 'lines') and page.lines is not None:
                lines_content = []
                for line in page.lines:
                    if hasattr(line, 'content') and line.content is not None:
                        lines_content.append(line.content)
                if lines_content:
                    page_contents.append(' '.join(lines_content))
        
        if page_contents:
            raw_text = '\n'.join(page_contents)
            extracted_data['raw_text'] = raw_text
            print(f"Extracted {len(raw_text)} characters of raw text")
            
            # If no structured data was extracted, try to find patterns in raw text
            if (not extracted_data['financial_data'] and 
                not extracted_data['key_metrics'] and 
                not extracted_data['dates']):
                
                import re
                print("No structured data found, using pattern recognition on raw text")
                
                # Find financial data using regex patterns
                # Look for budget patterns ($X, X dollars, etc.)
                budget_patterns = [
                    r'budget\s*(?:is|:)?\s*\$?([0-9,.]+)(?:k|K|thousand|m|M|million)?',
                    r'cost\s*(?:is|:)?\s*\$?([0-9,.]+)(?:k|K|thousand|m|M|million)?',
                    r'investment\s*(?:is|:)?\s*\$?([0-9,.]+)(?:k|K|thousand|m|M|million)?',
                    r'total\s*(?:budget|cost|investment)\s*(?:is|:)?\s*\$?([0-9,.]+)(?:k|K|thousand|m|M|million)?',
                    r'\$([0-9,.]+)(?:k|K|thousand|m|M|million)?\s*(?:budget|cost|investment)'
                ]
                
                for pattern in budget_patterns:
                    matches = re.findall(pattern, raw_text, re.IGNORECASE)
                    if matches:
                        extracted_data['financial_data']['budget'] = f"${matches[0]}"
                        print(f"Found budget via pattern matching: ${matches[0]}")
                        break
                
                # Look for ROI/return patterns
                roi_patterns = [
                    r'roi\s*(?:is|:)?\s*([0-9,.]+)%',
                    r'return\s*(?:on|of)\s*investment\s*(?:is|:)?\s*([0-9,.]+)%',
                    r'([0-9,.]+)%\s*roi',
                    r'([0-9,.]+)%\s*return'
                ]
                
                for pattern in roi_patterns:
                    matches = re.findall(pattern, raw_text, re.IGNORECASE)
                    if matches:
                        extracted_data['financial_data']['estimated roi'] = f"{matches[0]}%"
                        break
                
                # Look for employee/headcount patterns
                employee_patterns = [
                    r'employees?\s*(?:affected|impacted|involved)?\s*(?:is|:)?\s*([0-9,.]+)',
                    r'(?:total|number\s*of)\s*employees?\s*(?:is|:)?\s*([0-9,.]+)',
                    r'headcount\s*(?:is|:)?\s*([0-9,.]+)',
                    r'(?:affects|impacts)\s*([0-9,.]+)\s*employees?'
                ]
                
                for pattern in employee_patterns:
                    matches = re.findall(pattern, raw_text, re.IGNORECASE)
                    if matches:
                        extracted_data['key_metrics']['impacted employees'] = matches[0]
                        break
                
                # Look for duration/timeline patterns
                duration_patterns = [
                    r'duration\s*(?:is|:)?\s*([0-9,.]+)\s*(?:months?|years?)',
                    r'(?:project|timeline)\s*(?:duration|length)\s*(?:is|:)?\s*([0-9,.]+)\s*(?:months?|years?)',
                    r'(?:lasts?|runs?|continues?)\s*for\s*([0-9,.]+)\s*(?:months?|years?)',
                    r'([0-9,.]+)\s*(?:month|year)s?\s*(?:duration|timeline|project)'
                ]
                
                for pattern in duration_patterns:
                    matches = re.findall(pattern, raw_text, re.IGNORECASE)
                    if matches:
                        if 'year' in pattern:
                            # Convert years to months
                            months = float(matches[0].replace(',', '')) * 12
                            extracted_data['dates']['project duration'] = f"{int(months)} months"
                        else:
                            extracted_data['dates']['project duration'] = f"{matches[0]} months"
                        break
                
                # Look for rate patterns (hourly rate, etc.)
                rate_patterns = [
                    r'hourly\s*rate\s*(?:is|:)?\s*\$?([0-9,.]+)',
                    r'rate\s*(?:is|:)?\s*\$?([0-9,.]+)\s*(?:per|\/)\s*hour',
                    r'\$?([0-9,.]+)\s*(?:per|\/)\s*hour'
                ]
                
                for pattern in rate_patterns:
                    matches = re.findall(pattern, raw_text, re.IGNORECASE)
                    if matches:
                        extracted_data['key_metrics']['hourly rate'] = f"${matches[0]}"
                        break
                
                # Look for savings or benefits patterns
                savings_patterns = [
                    r'savings\s*(?:is|are|:)?\s*\$?([0-9,.]+)(?:k|K|thousand|m|M|million)?',
                    r'benefits?\s*(?:is|are|:)?\s*\$?([0-9,.]+)(?:k|K|thousand|m|M|million)?',
                    r'(?:annual|yearly|monthly)\s*savings\s*(?:is|are|:)?\s*\$?([0-9,.]+)(?:k|K|thousand|m|M|million)?'
                ]
                
                for pattern in savings_patterns:
                    matches = re.findall(pattern, raw_text, re.IGNORECASE)
                    if matches:
                        extracted_data['financial_data']['expected savings'] = f"${matches[0]}"
                        break
                        
                # Look for efficiency gain patterns
                efficiency_patterns = [
                    r'efficiency\s*(?:gain|improvement)\s*(?:is|:)?\s*([0-9,.]+)%',
                    r'productivity\s*(?:gain|improvement)\s*(?:is|:)?\s*([0-9,.]+)%',
                    r'([0-9,.]+)%\s*(?:efficiency|productivity)\s*(?:gain|improvement)'
                ]
                
                for pattern in efficiency_patterns:
                    matches = re.findall(pattern, raw_text, re.IGNORECASE)
                    if matches:
                        extracted_data['key_metrics']['efficiency gain'] = f"{matches[0]}%"
                        break
    
    # Add model used to process this document
    model_id = None
    if hasattr(document_result, 'model_id'):
        model_id = document_result.model_id
    else:
        # Try to determine model from document_type
        document_type = getattr(document_result, 'document_type', '')
        if document_type:
            model_id = f"prebuilt-{document_type.lower()}"
        
    extracted_data['model_used'] = model_id or "unknown"
    print(f"Document processed with model: {extracted_data['model_used']}")
    
    return extracted_data

# ROI calculations endpoint using Azure OpenAI
@app.route('/calculate_roi', methods=['POST'])
def calculate_roi():
    try:
        # Check if this is a form data request or JSON request
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Extract form data
            budget = request.form.get('budget')
            employees = request.form.get('employees')
            duration = request.form.get('duration')
            files_json = request.form.get('file_names', '[]')
            custom_fields_json = request.form.get('custom_fields', '{}')
            document_data_json = request.form.get('document_data', '[]')
            
            try:
                files = json.loads(files_json)
                custom_fields = json.loads(custom_fields_json)
                document_data = json.loads(document_data_json)
            except json.JSONDecodeError:
                files = []
                custom_fields = {}
                document_data = []
                
            # Process any attached files
            uploaded_files = request.files.getlist('files')
            if uploaded_files and len(uploaded_files) > 0:
                files = [f.filename for f in uploaded_files]
        else:
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
            document_data = data.get('documentData', [])
            
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
        
        # Prepare document data section if any documents were processed
        document_data_text = ""
        if document_data and len(document_data) > 0:
            document_data_text = "\n- Extracted Document Data:\n"
            
            for doc in document_data:
                filename = doc.get('filename', 'Unknown document')
                document_data_text += f"  - From {filename}:\n"
                
                # Add financial data
                financial_data = doc.get('financial_data', {})
                if financial_data:
                    document_data_text += f"    - Financial data:\n"
                    for key, value in financial_data.items():
                        document_data_text += f"      - {key}: {value}\n"
                
                # Add key metrics
                key_metrics = doc.get('key_metrics', {})
                if key_metrics:
                    document_data_text += f"    - Key metrics:\n"
                    for key, value in key_metrics.items():
                        document_data_text += f"      - {key}: {value}\n"
                
                # Add dates
                dates = doc.get('dates', {})
                if dates:
                    document_data_text += f"    - Timeline information:\n"
                    for key, value in dates.items():
                        document_data_text += f"      - {key}: {value}\n"
                
                # Add raw text if available
                raw_text = doc.get('raw_text', '')
                if raw_text:
                    document_data_text += f"    - Raw document text excerpt (first 300 chars):\n"
                    # Include just enough text to be useful without overwhelming the prompt
                    document_data_text += f"      {raw_text[:300]}...\n" if len(raw_text) > 300 else f"      {raw_text}\n"
        
        user_message = f"""
Project ROI Analysis Request:
- Budget: ${budget}
- Number of Impacted Employees: {employees}
- Project Duration: {duration} months
{f"- Supporting Documents: {', '.join(files)}" if files else "- No supporting documents provided"}
{custom_fields_text}
{document_data_text}

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

If extracted document data is provided, use this information to:
1. Validate and support your calculations
2. Reference specific data points from the documents to add credibility to your analysis
3. Identify any discrepancies between the document data and the input parameters

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

@app.route('/available_models', methods=['GET'])
def available_models():
    """Test which document analysis models are available"""
    if not document_analysis_client:
        return jsonify({"error": "Document Analysis client not initialized"}), 500
        
    try:
        # Create a test document to analyze
        test_content = "Test document for model testing."
        test_bytes = test_content.encode('utf-8')
        
        # Models to test
        models_to_test = {
            "prebuilt-document": {"available": False, "error": None},
            "prebuilt-layout": {"available": False, "error": None},
            "prebuilt-read": {"available": False, "error": None}
        }
        
        # Test each model
        for model_id in models_to_test:
            try:
                print(f"Testing model: {model_id}")
                # Create a temporary file with test content
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp:
                    temp.write(test_bytes)
                    temp_path = temp.name
                
                try:
                    # Try to analyze with this model
                    with open(temp_path, "rb") as f:
                        document_content = f.read()
                    
                    poller = document_analysis_client.begin_analyze_document(
                        model_id,
                        document_content
                    )
                    result = poller.result()
                    
                    # If we got here, the model is available
                    models_to_test[model_id]["available"] = True
                    print(f"Model {model_id} is available")
                    
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                        
            except Exception as e:
                # This model is not available
                models_to_test[model_id]["error"] = str(e)
                print(f"Model {model_id} is not available: {e}")
        
        return jsonify({
            "available_models": models_to_test,
            "subscription_info": {
                "endpoint": os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'),
                "api_key_provided": bool(os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY'))
            }
        })
        
    except Exception as e:
        print(f"Error testing available models: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
