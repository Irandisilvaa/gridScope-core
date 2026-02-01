from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
import os
import io

def generate_pdf(data_dict: dict) -> bytes:
    """
    Generates a PDF report from the provided data using WeasyPrint and Jinja2.
    
    Args:
        data_dict: Dictionary containing all data needed for the report.
        
    Returns:
        bytes: The binary content of the generated PDF.
    """
    
    # 1. Setup Jinja2 Environment
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(current_dir, 'templates')
    logo_path = os.path.join(current_dir, 'logo.png')
    
    # Load Logo as Base64
    import base64
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_b64 = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Add logo to data
    if isinstance(data_dict, dict):
        data_dict['logo_b64'] = logo_b64

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('report.html')
    
    # 2. Render HTML with Data
    html_string = template.render(pdf_data=data_dict)
    
    # 3. Generate PDF
    # We write to BytesIO to keep it in memory (no disk IO as requested)
    pdf_file = io.BytesIO()
    
    # Optional: Presenter might want specific CSS adjustments passed here, 
    # but most styling is already in the HTML <style> block.
    HTML(string=html_string).write_pdf(target=pdf_file)
    
    # Reset pointer to beginning of stream
    pdf_file.seek(0)
    
    return pdf_file.getvalue()
