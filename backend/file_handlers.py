import os
import tempfile
import uuid
import mimetypes
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'csv': 'text/csv'
}

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(original_filename):
    """Generate a unique filename while preserving the original extension."""
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    unique_id = str(uuid.uuid4())
    if ext:
        return f"{unique_id}.{ext}"
    return unique_id

def save_uploaded_file(file, upload_folder=None):
    """Save an uploaded file to a temporary location or specified folder."""
    if upload_folder is None:
        # Use system temp directory if no folder specified
        upload_folder = tempfile.gettempdir()
    
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        return None, "File type not allowed"
    
    unique_filename = generate_unique_filename(filename)
    file_path = os.path.join(upload_folder, unique_filename)
    
    try:
        file.save(file_path)
        return file_path, None
    except Exception as e:
        return None, str(e)

def extract_text_from_file(file_path):
    """
    Extract text from various file types.
    This is a placeholder. In a real implementation, you would use libraries like:
    - PyPDF2 or pdfminer for PDFs
    - python-docx for Word documents
    - pandas or openpyxl for Excel files
    """
    # This is just a placeholder implementation
    file_ext = file_path.rsplit('.', 1)[1].lower() if '.' in file_path else ''
    
    if file_ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv']:
        return f"Content extracted from {file_path} (simulated for now)"
    
    return "Unsupported file format" 