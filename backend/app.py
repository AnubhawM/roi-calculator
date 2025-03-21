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
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
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

# Check if Azure AI Project credentials are available
ai_project_credentials_available = bool(os.getenv("PROJECT_CONNECTION_STRING"))
if ai_project_credentials_available:
    print(f"Azure AI Project credentials available")
    print(f"  - Connection String set: {'Yes' if os.getenv('PROJECT_CONNECTION_STRING') else 'No'}")
else:
    print("Azure AI Project credentials not available - AI Agent functionality will not be available")

# Function to create a new AI Project Client for each request
def create_ai_project_client():
    """Create a new AI Project client for each request to avoid connection issues"""
    if not os.getenv("PROJECT_CONNECTION_STRING"):
        print("No PROJECT_CONNECTION_STRING environment variable found")
        return None
        
    try:
        # Create an Azure credential object - more robust to handle various authentication scenarios
        credential = None
        try:
            credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
            print("Successfully created DefaultAzureCredential")
        except Exception as auth_error:
            print(f"Warning: Could not create DefaultAzureCredential: {auth_error}")
            # We still need to proceed with connection string
        
        # Create the client with both the credential and connection string
        # Both are required according to the Azure API
        client = AIProjectClient.from_connection_string(
            credential=credential,
            conn_str=os.getenv("PROJECT_CONNECTION_STRING")
        )
        
        print("Successfully created AI Project client")
        return client
    except Exception as e:
        print(f"Error creating AI Project client: {e}")
        print(f"Error type: {type(e)}")
        return None

# Store active threads for each user session
active_threads = {}

# Store a persistent agent ID that we can reuse
PERSISTENT_AGENT_ID = None

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

Format your response using proper Markdown:
- Use ### for section headers (e.g., ### Executive Summary)
- Use ** for emphasis on important points and numbers
- Use - for bullet points
- When writing mathematical formulas or equations, ALWAYS wrap them in LaTeX dollar signs for proper rendering:
  - Inline math should use single dollar signs: $formula$
  - Display math (for more complex formulas) should use double dollar signs: $$formula$$
  - Example: $ROI = \\frac{{Total Benefits - Total Costs}}{{Total Costs}} \\times 100$
  - For the ROI formula, use: $\\text{{ROI}} = \\frac{{\\text{{Total Benefits}} - \\text{{Total Costs}}}}{{\\text{{Total Costs}}}} \\times 100$
  - For the Payback Period, use: $\\text{{Payback Period}} = \\frac{{\\text{{Total Costs}}}}{{\\text{{Annual Benefits}}}}$

Present the ROI calculation using clear formatting. For numeric values, ensure proper currency formatting with commas for thousands.

Also, don't prioritize cutting headcount to save money, even if it's mathematically the best option.
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

# New function to get or create a persistent agent
def get_or_create_persistent_agent(client):
    """Get existing agent or create a new persistent one"""
    global PERSISTENT_AGENT_ID
    
    if PERSISTENT_AGENT_ID:
        # Try to get the existing agent
        try:
            # If the ID is valid, return it to be used
            # No need to retrieve full agent, just return the ID
            return PERSISTENT_AGENT_ID
        except Exception as e:
            print(f"Error retrieving persistent agent: {e}")
            # Reset the ID and continue to create a new one
            PERSISTENT_AGENT_ID = None
    
    # Define function to create agent with retries
    def create_agent_with_retry():
        return client.agents.create_agent(
            model=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4o-mini'),
            name="roi-calculator-persistent-agent",
            instructions=(
                "You are an ROI calculation assistant that helps users understand their "
                "Return on Investment analyses. You can answer questions about the ROI "
                "calculation methodology, interpret results, explain financial concepts, "
                "and provide insights based on the calculation context. Always be precise "
                "with financial figures and calculations. When specific ROI calculation "
                "data is provided, refer to it directly in your answers. Maintain a helpful "
                "and informative tone, and reference previous parts of the conversation when relevant."
            )
        )
    
    # Create a new persistent agent with retry logic
    try:
        # Use our retry mechanism to handle potential rate limits
        agent = retry_with_backoff(
            create_agent_with_retry,
            max_retries=3,
            initial_delay=2,
            backoff_factor=2
        )
        
        # Store the agent's ID for future use
        agent_id = agent.id if hasattr(agent, 'id') else str(agent)
        PERSISTENT_AGENT_ID = agent_id
        print(f"Created new persistent agent: {PERSISTENT_AGENT_ID}")
        return PERSISTENT_AGENT_ID
    except Exception as e:
        print(f"Error creating persistent agent after retries: {e}")
        return None

# Also track which threads have already received context information
threads_with_context = set()

# Store thread context versions for tracking changes
thread_context_versions = {}

# New function to extract and log token usage
def log_token_usage(run_info, operation_name):
    """Extract and log token usage information from a run"""
    try:
        print(f"\n----- TOKEN USAGE FOR {operation_name} -----")
        
        # Check if run_info has usage directly
        usage = None
        if hasattr(run_info, 'usage'):
            usage = run_info.usage
        # Check if it's in _data dictionary
        elif hasattr(run_info, '_data') and isinstance(run_info._data, dict) and 'usage' in run_info._data:
            usage = run_info._data['usage']
        # Check if it's directly a dictionary with usage
        elif isinstance(run_info, dict) and 'usage' in run_info:
            usage = run_info['usage']
            
        if usage:
            prompt_tokens = usage.get('prompt_tokens', 0) if isinstance(usage, dict) else getattr(usage, 'prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0) if isinstance(usage, dict) else getattr(usage, 'completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0) if isinstance(usage, dict) else getattr(usage, 'total_tokens', 0)
            
            print(f"Prompt tokens: {prompt_tokens}")
            print(f"Completion tokens: {completion_tokens}")
            print(f"Total tokens: {total_tokens}")
            
            # Check for details on token caching if available
            if isinstance(usage, dict) and 'prompt_token_details' in usage:
                details = usage['prompt_token_details']
                print(f"Token details: {details}")
                
            return {
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens
            }
        else:
            print("No usage information available")
            return None
    except Exception as e:
        print(f"Error extracting token usage: {e}")
        return None

# Add a more sophisticated retry mechanism
def retry_with_backoff(func, *args, max_retries=3, initial_delay=2, backoff_factor=2, **kwargs):
    """Execute a function with exponential backoff retries on rate limit errors"""
    retry_count = 0
    delay = initial_delay
    
    while retry_count <= max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_message = str(e).lower()
            is_rate_limit = 'rate limit' in error_message or 'too many requests' in error_message
            
            if is_rate_limit and retry_count < max_retries:
                # Try to extract wait time from error message
                wait_time = None
                import re
                time_matches = re.findall(r'(\d+)\s*seconds', error_message)
                if time_matches:
                    wait_time = int(time_matches[0])
                
                # Use suggested wait time or calculate backoff
                if wait_time:
                    actual_delay = wait_time + 2  # Add buffer
                else:
                    actual_delay = delay
                    
                print(f"Rate limit detected. Retrying in {actual_delay} seconds (attempt {retry_count+1}/{max_retries})...")
                time.sleep(actual_delay)
                delay *= backoff_factor  # Increase delay for next retry
                retry_count += 1
            else:
                # Not a rate limit error or max retries exceeded
                raise
    
    raise Exception(f"Max retries ({max_retries}) exceeded")

# Modify the run status checking with gradual polling
def wait_for_run_completion(ai_project_client, thread_id, run_id, operation_name, max_wait_time=120):
    """Wait for a run to complete with progressive backoff to reduce API calls"""
    status = None
    start_time = time.time()
    polling_interval = 1  # Start with 1 second interval
    max_polling_interval = 10  # Maximum polling interval in seconds
    
    print(f"Waiting for {operation_name} run to complete...")
    
    while time.time() - start_time < max_wait_time:
        try:
            # Get run status with retry logic
            def get_run_status():
                run_info = ai_project_client.agents.get_run(thread_id, run_id)
                status = getattr(run_info, 'status', None)
                return run_info, status
            
            run_info, status = retry_with_backoff(get_run_status)
            
            if status in ['completed', 'failed', 'cancelled']:
                print(f"{operation_name} run completed with status: {status}")
                return run_info, status
            
            # Progressive backoff - increase polling interval
            time.sleep(polling_interval)
            polling_interval = min(polling_interval * 1.5, max_polling_interval)
            
        except Exception as e:
            print(f"Error checking {operation_name} run status: {e}")
            # Keep increasing polling interval even on errors
            time.sleep(polling_interval)
            polling_interval = min(polling_interval * 1.5, max_polling_interval)
    
    print(f"{operation_name} run did not complete within {max_wait_time} seconds")
    return None, "timeout"

# New endpoint for AI Agent Q&A
@app.route('/ask', methods=['POST', 'OPTIONS'])
def ask_question():
    """Process user questions using Azure AI Agent service"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response
    
    # Create a new AI Project client for this request
    ai_project_client = create_ai_project_client()
    if not ai_project_client:
        return jsonify({"error": "AI Agent service is not available"}), 503
    
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Request data is required"}), 400
        
        # Extract question and context
        question = data.get('question')
        roi_context = data.get('context', {})
        session_id = data.get('sessionId', str(uuid.uuid4()))
        context_version = data.get('contextVersion', '')
        is_new_session = data.get('isNewSession', False)
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        print(f"Processing question for session {session_id}: {question}")
        
        # Format ROI context
        context_text = ""
        if roi_context:
            context_text = "Current ROI Calculation Context:\n"
            if roi_context.get('budget'):
                context_text += f"- Budget: ${roi_context.get('budget')}\n"
            if roi_context.get('employees'):
                context_text += f"- Impacted Employees: {roi_context.get('employees')}\n"
            if roi_context.get('duration'):
                context_text += f"- Project Duration: {roi_context.get('duration')} months\n"
            
            # Add custom fields if available
            custom_fields = roi_context.get('customFields', [])
            if custom_fields and len(custom_fields) > 0:
                context_text += "- Custom Fields:\n"
                for field in custom_fields:
                    if isinstance(field, dict) and 'title' in field and 'value' in field:
                        context_text += f"  - {field.get('title')}: {field.get('value')}\n"
                    elif isinstance(field, dict) and 'name' in field and 'value' in field:
                        context_text += f"  - {field.get('name')}: {field.get('value')}\n"
            
            # Add ROI results if available
            if roi_context.get('roiResults'):
                context_text += "\nROI Calculation Results:\n"
                context_text += roi_context.get('roiResults')
        
        # Get or create thread for this session
        thread_id = active_threads.get(session_id)
        
        with ai_project_client:
            # Get or create the persistent agent
            agent_id = get_or_create_persistent_agent(ai_project_client)
            if not agent_id:
                return jsonify({"error": "Failed to initialize agent"}), 500
            
            # Create thread if needed
            if not thread_id:
                try:
                    thread = ai_project_client.agents.create_thread()
                    # Handle if create_thread returns a string ID instead of a thread object
                    if isinstance(thread, str):
                        thread_id = thread
                    else:
                        thread_id = thread.id
                    active_threads[session_id] = thread_id
                    print(f"Created new thread {thread_id} for session {session_id}")
                except Exception as e:
                    print(f"Error creating thread: {e}")
                    return jsonify({"error": f"Failed to create conversation thread: {str(e)}"}), 500
            
            # Check if context version has changed
            current_thread_version = thread_context_versions.get(thread_id)
            context_changed = context_version and current_thread_version != context_version
            
            # Define context key for tracking
            context_key = f"{thread_id}_context"
            
            # If this is a new session, clear previous context tracking
            if is_new_session:
                if context_key in threads_with_context:
                    threads_with_context.remove(context_key)
                if thread_id in thread_context_versions:
                    del thread_context_versions[thread_id]
                context_changed = True
                print(f"New session detected, clearing context tracking for thread {thread_id}")
            
            # Add or update ROI context as a message
            if context_text and (context_key not in threads_with_context or context_changed):
                try:
                    # Prepare context update message
                    context_message = f"Here is my current ROI calculation context that you should reference when answering my questions:\n\n{context_text}\n\n"
                    
                    # Add additional note if context was updated
                    if context_changed:
                        if is_new_session:
                            context_message += "Note: This is a completely new ROI calculation. Disregard all previous context and conversations.\n\n"
                        else:
                            context_message += "Note: The ROI calculation data has been updated. Please use this new information for your answers and ignore previous context.\n\n"
                    
                    context_message += "Please acknowledge receipt of this context."
                    
                    # Add context as user message
                    ai_project_client.agents.create_message(
                        thread_id=thread_id,
                        role="user",
                        content=context_message
                    )
                    
                    # Process the context message
                    run = ai_project_client.agents.create_and_process_run(
                        thread_id=thread_id, 
                        agent_id=agent_id
                    )
                    
                    # Use improved waiting function
                    run_info, context_run_status = wait_for_run_completion(
                        ai_project_client, thread_id, run.id, "Context", max_wait_time=60
                    )
                    
                    if run_info:
                        # Extract and log token usage for context message
                        log_token_usage(run_info, "CONTEXT MESSAGE")
                    
                    # Add a small delay to ensure any pending operations are complete
                    time.sleep(2)
                    
                    # Update tracking
                    if context_changed:
                        print(f"Updated context for thread {thread_id} (version change: {current_thread_version} -> {context_version})")
                    else:
                        print(f"Added initial context to thread {thread_id}")
                    
                    # Mark this thread as having received context and update version
                    threads_with_context.add(context_key)
                    thread_context_versions[thread_id] = context_version
                except Exception as e:
                    print(f"Error adding/updating context to thread: {e}")
                    # Continue even if context addition fails
            
            # Add user question
            try:
                ai_project_client.agents.create_message(
                    thread_id=thread_id,
                    role="user",
                    content=question
                )
                
                # Create system message with formatting instructions
                system_instructions = """You are a change management specialist, assisting leaders with providing analysis and insights.

When writing your responses, you MUST format ALL mathematical formulas and equations using the EXACT LaTeX syntax shown below:

For ANY formula containing \text commands or fractions:
1. ALWAYS wrap the ENTIRE formula with double dollar signs ($$...$$)
2. NEVER use single dollar signs for complex formulas
3. Example: $$\\text{ROI} = \\frac{\\text{Total Benefits} - \\text{Total Costs}}{\\text{Total Costs}} \\times 100$$

For simple inline math (variables or simple expressions):
1. Use single dollar signs ($...$)
2. Example: The value of $x$ is 5.

For ROI and Payback formulas specifically:
- ALWAYS format ROI as: $$\\text{ROI} = \\frac{\\text{Total Benefits} - \\text{Total Costs}}{\\text{Total Costs}} \\times 100$$
- ALWAYS format Payback Period as: $$\\text{Payback Period} = \\frac{\\text{Total Costs}}{\\text{Annual Benefits}}$$
- When substituting values, keep the same double dollar sign format: $$\\text{ROI} = \\frac{205,480 - 23,434}{23,434} \\times 100 \\approx 776.27\\%$$

Format your responses using proper Markdown:
- Use ### for section headers
- Use ** for emphasis on important points and numbers
- Use - for bullet points
"""
                
                # Process the user's question
                run = ai_project_client.agents.create_and_process_run(
                    thread_id=thread_id, 
                    agent_id=agent_id,
                    additional_instructions=system_instructions
                )
                
                # Use improved waiting function
                run_info, run_status = wait_for_run_completion(
                    ai_project_client, thread_id, run.id, "Question", max_wait_time=120
                )
                
                if run_info:
                    # Extract and log token usage for question message
                    token_usage = log_token_usage(run_info, "QUESTION MESSAGE")

                    if run_status != 'completed':
                        print(f"Run did not complete successfully. Status: {run_status}")
                        
                        if run_status == 'timeout':
                            return jsonify({
                                "answer": "I'm sorry, but your request is taking longer than expected to process. Please try again later.",
                                "sessionId": session_id,
                                "error": "Request timed out"
                            })
                        
                        # Check if we should return an error based on run status
                        if run_status == 'failed':
                            error_message = "The AI agent was unable to process your question."
                            try:
                                # Get error details
                                if run_info:
                                    error_details = getattr(run_info, 'last_error', {})
                                    rate_limit_info = check_for_rate_limit(error_details)
                                    
                                    if rate_limit_info.get('is_rate_limit'):
                                        wait_time = rate_limit_info.get('wait_time', 60)
                                        
                                        # Wait for the suggested time plus a buffer
                                        print(f"Rate limit encountered. Waiting {wait_time + 5} seconds before retrying...")
                                        time.sleep(wait_time + 5)
                                        
                                        # Create a new message and try again
                                        print(f"Retrying question after waiting for rate limit...")
                                        
                                        # Create a new message - avoid recreating the run immediately to prevent rate limit
                                        ai_project_client.agents.create_message(
                                            thread_id=thread_id,
                                            role="user",
                                            content=f"Retrying my previous question: {question}"
                                        )
                                        
                                        # Return a message to the user that their request is being processed
                                        return jsonify({
                                            "answer": "I'm processing your request. Please wait a moment and then ask me again. Our service is experiencing high demand right now.",
                                            "sessionId": session_id
                                        })
                                    
                                    # If it's another type of error, extract details
                                    if error_details and hasattr(error_details, 'message'):
                                        error_message = f"Processing failed: {error_details.message}"
                            
                            except Exception as e:
                                print(f"Error handling run failure: {e}")
                            
                            # Return a friendly error to the user
                            return jsonify({
                                "answer": f"I'm sorry, but I encountered an issue while processing your question. Please try asking in a different way or try again in a few minutes.",
                                "sessionId": session_id,
                                "error": error_message
                            })
                
                # Add a small delay to ensure message is available
                time.sleep(1)
                
                # Get messages after processing, SORTED BY CREATED TIME
                messages = ai_project_client.agents.list_messages(thread_id=thread_id)
                
                # Try to get the last assistant message by specifically looking for the most recent one
                last_msg = None
                try:
                    # Get all assistant messages
                    assistant_messages = []
                    
                    if hasattr(messages, 'data') and isinstance(messages.data, list):
                        # If messages has a data property that's a list, use that
                        assistant_messages = [msg for msg in messages.data 
                                             if getattr(msg, 'role', None) == "assistant"]
                    else:
                        # Otherwise try to iterate messages directly
                        assistant_messages = [msg for msg in messages 
                                             if getattr(msg, 'role', None) == "assistant"]
                    
                    if assistant_messages:
                        # Sort assistant messages by creation time if possible
                        if all(hasattr(msg, 'created_at') for msg in assistant_messages):
                            assistant_messages.sort(key=lambda x: x.created_at, reverse=True)
                        
                        # Get the most recent assistant message
                        last_msg = assistant_messages[0]
                        print(f"Found latest assistant message: {last_msg.id if hasattr(last_msg, 'id') else 'unknown id'}")
                except Exception as e:
                    print(f"Error getting assistant messages: {e}")
                
                # Extract answer from the message based on its structure
                answer = None
                if last_msg:
                    try:
                        print(f"Message structure type: {type(last_msg)}")
                        print(f"Message attributes: {dir(last_msg)}")
                        
                        # Try to print the full message content for debugging
                        try:
                            print(f"Full message content: {last_msg}")
                            if hasattr(last_msg, 'model_dump'):
                                print(f"Model dump: {last_msg.model_dump()}")
                            elif hasattr(last_msg, 'to_dict'):
                                print(f"To dict: {last_msg.to_dict()}")
                        except Exception as e:
                            print(f"Error dumping message: {e}")
                        
                        # Handle the new format where content might be an array of content blocks
                        if hasattr(last_msg, 'content') and isinstance(last_msg.content, list):
                            # Content is a list of content blocks
                            content_blocks = last_msg.content
                            combined_text = []
                            
                            print(f"Content is a list with {len(content_blocks)} blocks")
                            for i, block in enumerate(content_blocks):
                                print(f"Block {i} type: {type(block)}")
                                print(f"Block {i} content: {block}")
                                
                                if isinstance(block, dict):
                                    if 'text' in block and isinstance(block['text'], dict) and 'value' in block['text']:
                                        combined_text.append(block['text']['value'])
                                        print(f"Added text from block {i}: {block['text']['value'][:50]}...")
                                    elif 'type' in block and block['type'] == 'text':
                                        if 'text' in block and isinstance(block['text'], dict) and 'value' in block['text']:
                                            combined_text.append(block['text']['value'])
                                            print(f"Added text from typed block {i}: {block['text']['value'][:50]}...")
                                        
                                # Try to handle custom object types
                                elif hasattr(block, 'type') and getattr(block, 'type') == 'text':
                                    if hasattr(block, 'text') and hasattr(block.text, 'value'):
                                        combined_text.append(block.text.value)
                                        print(f"Added text from object block {i}: {block.text.value[:50]}...")
                            
                            if combined_text:
                                answer = ' '.join(combined_text)
                                print(f"Combined text answer: {answer[:100]}...")
                            else:
                                print("No text could be extracted from content blocks")
                                # Try a fallback approach - convert the whole thing to string
                                try:
                                    answer = f"Content available but format not recognized. Raw: {str(content_blocks)}"
                                except:
                                    answer = "Content available but format could not be interpreted."
                        # Original structure with text.value
                        elif hasattr(last_msg, 'text') and hasattr(last_msg.text, 'value'):
                            answer = last_msg.text.value
                            print(f"Text.value format: {answer[:100]}...")
                        # Alternative structure with direct content
                        elif hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
                            answer = last_msg.content
                            print(f"Direct content string: {answer[:100]}...")
                        # Dictionary structure
                        elif isinstance(last_msg, dict):
                            if 'content' in last_msg and isinstance(last_msg['content'], str):
                                answer = last_msg['content']
                                print(f"Dict content string: {answer[:100]}...")
                            elif 'text' in last_msg and 'value' in last_msg['text']:
                                answer = last_msg['text']['value']
                                print(f"Dict text.value: {answer[:100]}...")
                        # String content directly
                        elif isinstance(last_msg, str):
                            answer = last_msg
                            print(f"Direct string: {answer[:100]}...")
                    except Exception as e:
                        print(f"Error extracting message content: {e}")
                        print(f"Exception type: {type(e)}")
                        print(f"Traceback: {sys.exc_info()}")
                        # Try to convert the message to string as a fallback
                        try:
                            answer = f"Message received but could not be properly formatted. Raw content: {str(last_msg)}"
                        except Exception as inner_e:
                            print(f"Even fallback formatting failed: {inner_e}")
                            answer = "Message received but could not be displayed."
                
                if answer:
                    print(f"Got answer from agent: {answer[:100]}...")
                    return jsonify({
                        "answer": answer,
                        "sessionId": session_id
                    })
                else:
                    return jsonify({"error": "No response from agent"}), 500
                    
            except Exception as e:
                print(f"Error processing question: {e}")
                return jsonify({"error": f"Failed to process question: {str(e)}"}), 500
    
    except Exception as e:
        print(f"Error in ask_question: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # Ensure client is properly closed
        if ai_project_client:
            try:
                ai_project_client.close()
            except:
                pass

# Health check for AI agent service
@app.route('/agent_health', methods=['GET'])
def agent_health():
    """Check if the AI agent service is available and working"""
    # Create a new AI Project client for this request
    ai_project_client = create_ai_project_client()
    if not ai_project_client:
        return jsonify({
            "status": "unavailable", 
            "error": "AI Agent client not initialized",
            "connection_info": {
                "connection_string_provided": bool(os.getenv('PROJECT_CONNECTION_STRING'))
            }
        }), 503
    
    try:
        with ai_project_client:
            # Check if we can get or create the persistent agent
            agent_id = get_or_create_persistent_agent(ai_project_client)
            
            if agent_id:
                return jsonify({
                    "status": "available",
                    "agent_id": agent_id,
                    "connection_info": {
                        "connection_string_provided": bool(os.getenv('PROJECT_CONNECTION_STRING'))
                    }
                })
            else:
                return jsonify({
                    "status": "error",
                    "error": "Failed to get or create persistent agent",
                    "connection_info": {
                        "connection_string_provided": bool(os.getenv('PROJECT_CONNECTION_STRING'))
                    }
                }), 500
    
    except Exception as e:
        print(f"Error checking AI agent health: {e}")
        return jsonify({
            "status": "error", 
            "error": str(e),
            "connection_info": {
                "connection_string_provided": bool(os.getenv('PROJECT_CONNECTION_STRING'))
            }
        }), 500
    finally:
        # Ensure client is properly closed
        if ai_project_client:
            try:
                ai_project_client.close()
            except:
                pass

# New function to check for and log rate limit errors
def check_for_rate_limit(error_details):
    """Check if error is related to rate limits and log relevant information"""
    try:
        # Check if this is a rate limit error
        is_rate_limit = False
        wait_time = None
        
        # Extract error code and message
        error_code = None
        error_message = None
        
        if isinstance(error_details, dict):
            error_code = error_details.get('code')
            error_message = error_details.get('message')
        else:
            error_code = getattr(error_details, 'code', None)
            error_message = getattr(error_details, 'message', None)
        
        # Check for rate limit indicators
        if error_code == 'rate_limit_exceeded' or (error_message and 'rate limit' in error_message.lower()):
            is_rate_limit = True
            print("\n----- RATE LIMIT DETECTED -----")
            print(f"Error code: {error_code}")
            print(f"Error message: {error_message}")
            
            # Try to extract wait time from message if present
            if error_message:
                import re
                time_matches = re.findall(r'(\d+)\s*seconds', error_message)
                if time_matches:
                    wait_time = int(time_matches[0])
                    print(f"Suggested wait time: {wait_time} seconds")
            
            return {
                'is_rate_limit': True,
                'error_code': error_code,
                'error_message': error_message,
                'wait_time': wait_time
            }
        
        return {'is_rate_limit': False}
    
    except Exception as e:
        print(f"Error checking for rate limit: {e}")
        return {'is_rate_limit': False}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
