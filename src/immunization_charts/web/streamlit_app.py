"""
Streamlit web interface for immunization charts.

This module provides a user-friendly web interface that wraps the existing
CLI functionality without modifying any core business logic.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# Add the project root to the path so we can import our modules
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root / "src"))
sys.path.append(str(project_root / "config"))

from settings import config

from immunization_charts.core.pipeline import ImmunizationPipeline
from immunization_charts.data.loader import load_and_validate_data


class WebConfig:
    """Custom configuration class for web interface that allows setting values."""

    def __init__(self, base_config, user_config):
        """Initialize with base config and user overrides."""
        self.base_config = base_config
        self.user_config = user_config

    def __getattr__(self, name):
        """Get attribute, preferring user config over base config."""
        if name in self.user_config:
            return self.user_config[name]
        return getattr(self.base_config, name)

    def __setattr__(self, name, value):
        """Set attribute in user config."""
        if name in ["base_config", "user_config"]:
            super().__setattr__(name, value)
        else:
            if not hasattr(self, "user_config"):
                super().__setattr__(name, value)
            else:
                self.user_config[name] = value


def setup_page_config():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="Immunization Charts Generator",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def display_header():
    """Display the application header."""
    st.title("🩺 Immunization Charts Generator")
    st.markdown(
        "Generate personalized immunization history charts and notice letters for children overdue for mandated vaccinations."
    )

    st.markdown("---")


def display_sidebar():
    """Display the sidebar with configuration options."""
    st.sidebar.header("⚙️ Configuration")

    # Language selection
    language = st.sidebar.selectbox(
        "Language",
        ["english", "french"],
        help="Select the language for processing and output",
    )

    # Batch size configuration
    batch_size = st.sidebar.number_input(
        "Batch Size",
        min_value=1,
        max_value=1000,
        value=config.batch_size,
        help="Number of records to process in each batch",
    )

    # Delivery date
    delivery_date = st.sidebar.date_input(
        "Delivery Date",
        value=pd.to_datetime(config.delivery_date).date(),
        help="Delivery date for the immunization notices",
    )

    # Data date
    data_date = st.sidebar.date_input(
        "Data Date",
        value=pd.to_datetime(config.data_date).date(),
        help="Date of the data being processed",
    )

    # Output directory
    output_dir = st.sidebar.text_input(
        "Output Directory",
        value="output",
        help="Directory where generated files will be saved",
    )

    return {
        "language": language,
        "batch_size": batch_size,
        "delivery_date": str(delivery_date),
        "data_date": str(data_date),
        "output_dir": output_dir,
    }


def display_branding_customization():
    """Display branding and content customization section."""
    st.header("🎨 Customize Branding & Content")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📸 Upload Assets")

        # Logo upload
        uploaded_logo = st.file_uploader(
            "Upload Logo",
            type=["png", "jpg", "jpeg", "svg"],
            help="Upload your organization's logo (PNG, JPG, or SVG format)",
        )

        # Signature upload
        uploaded_signature = st.file_uploader(
            "Upload Signature",
            type=["png", "jpg", "jpeg", "svg"],
            help="Upload signature image (PNG, JPG, or SVG format)",
        )

        # Logo size control
        logo_width = st.slider(
            "Logo Width (cm)",
            min_value=3.0,
            max_value=10.0,
            value=6.0,
            step=0.5,
            help="Adjust the width of the logo in the generated PDFs",
        )

        # Signature size control
        signature_width = st.slider(
            "Signature Width (cm)",
            min_value=2.0,
            max_value=6.0,
            value=3.0,
            step=0.5,
            help="Adjust the width of the signature in the generated PDFs",
        )

    with col2:
        st.subheader("📝 Contact Information")

        # Contact details
        contact_email = st.text_input(
            "Contact Email",
            value="records@test-immunization.ca",
            help="Email address for immunization record updates",
        )

        contact_phone = st.text_input(
            "Contact Phone",
            value="555-555-5555 ext. 1234",
            help="Phone number for immunization record updates",
        )

        contact_address = st.text_area(
            "Contact Address",
            value="Test Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
            help="Mailing address for immunization record updates",
            height=100,
        )

        st.subheader("✍️ Signature Details")

        # Signature name and title
        signature_name = st.text_input(
            "Signature Name",
            value="Dr. Jane Smith, MPH",
            help="Name to appear under the signature",
        )

        signature_title = st.text_input(
            "Signature Title",
            value=(
                "Associate Medical Officer of Health"
                if st.session_state.get("language", "english") == "english"
                else "Médecin hygiéniste adjoint"
            ),
            help="Title to appear under the signature",
        )

    # Store branding settings in session state
    st.session_state.branding = {
        "uploaded_logo": uploaded_logo,
        "uploaded_signature": uploaded_signature,
        "logo_width": logo_width,
        "signature_width": signature_width,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "contact_address": contact_address,
        "signature_name": signature_name,
        "signature_title": signature_title,
    }

    return st.session_state.branding


def handle_custom_assets(branding_options, output_dir):
    """Handle custom branding assets and create custom template parameters."""
    from pathlib import Path

    custom_assets = {
        "logo_path": None,
        "signature_path": None,
        "logo_width": branding_options["logo_width"],
        "signature_width": branding_options["signature_width"],
        "contact_email": branding_options["contact_email"],
        "contact_phone": branding_options["contact_phone"],
        "contact_address": branding_options["contact_address"],
        "signature_name": branding_options["signature_name"],
        "signature_title": branding_options["signature_title"],
    }

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Handle custom logo
    if branding_options["uploaded_logo"] is not None:
        logo_path = output_path / "custom_logo.png"
        with open(logo_path, "wb") as f:
            f.write(branding_options["uploaded_logo"].getvalue())
        custom_assets["logo_path"] = str(logo_path)
        st.success(f"✅ Custom logo uploaded: {branding_options['uploaded_logo'].name}")

    # Handle custom signature
    if branding_options["uploaded_signature"] is not None:
        signature_path = output_path / "custom_signature.png"
        with open(signature_path, "wb") as f:
            f.write(branding_options["uploaded_signature"].getvalue())
        custom_assets["signature_path"] = str(signature_path)
        st.success(
            f"✅ Custom signature uploaded: {branding_options['uploaded_signature'].name}"
        )

    return custom_assets


def generate_custom_templates(output_dir, language, custom_assets):
    """Generate custom Typst templates with user's branding and content."""
    from pathlib import Path

    # Get template directories
    project_root = Path(__file__).parent.parent.parent.parent
    templates_dir = project_root / "templates"
    assets_dir = project_root / "assets"
    config_dir = project_root / "config"

    # Create custom template generator
    template_generator = CustomTemplateGenerator(
        templates_dir, assets_dir, config_dir, custom_assets
    )

    # Generate templates
    generated_templates = template_generator.generate_templates(
        Path(output_dir), language
    )

    return generated_templates


class CustomTemplateGenerator:
    """Custom template generator that uses user's branding and content."""

    def __init__(self, templates_dir, assets_dir, config_dir, custom_assets):
        self.templates_dir = templates_dir
        self.assets_dir = assets_dir
        self.config_dir = config_dir
        self.custom_assets = custom_assets

    def generate_templates(self, output_dir, language):
        """Generate custom templates for the specified language."""
        json_dir = output_dir / f"json_{language}"
        if not json_dir.exists():
            return []

        # Get template script
        template_script = self.templates_dir / f"{language}_template.sh"
        if not template_script.exists():
            st.error(f"Template script not found: {template_script}")
            return []

        # Copy custom assets to output directory
        self._copy_custom_assets(json_dir)

        # Generate custom template script
        custom_script = self._create_custom_template_script(template_script, json_dir)

        # Debug information
        st.info(f"Custom script created at: {custom_script}")
        st.info(f"Custom script exists: {custom_script.exists()}")

        # Process each JSON file
        json_files = list(json_dir.glob("*.json"))
        st.info(f"Found {len(json_files)} JSON files to process")
        generated_templates = []

        for json_file in json_files:
            filename = json_file.stem
            template_file = self._generate_single_custom_template(
                json_dir, filename, language, custom_script
            )
            if template_file:
                generated_templates.append(template_file)

        return generated_templates

    def _copy_custom_assets(self, json_dir):
        """Copy custom assets to the JSON directory."""
        # Copy custom logo if provided
        if self.custom_assets["logo_path"]:
            logo_dest = json_dir / "custom_logo.png"
            shutil.copy2(self.custom_assets["logo_path"], logo_dest)

        # Copy custom signature if provided
        if self.custom_assets["signature_path"]:
            signature_dest = json_dir / "custom_signature.png"
            shutil.copy2(self.custom_assets["signature_path"], signature_dest)

        # Copy default assets as fallback
        default_logo = self.assets_dir / "logo.png"
        default_signature = self.assets_dir / "signature.png"

        if default_logo.exists():
            shutil.copy2(default_logo, json_dir / "logo.png")
        if default_signature.exists():
            shutil.copy2(default_signature, json_dir / "signature.png")

    def _create_custom_template_script(self, original_script, json_dir):
        """Create a custom template script with user's branding."""
        # Create the custom script in the templates directory, not the json_dir
        custom_script = self.templates_dir / "custom_template.sh"

        # Read original script
        with open(original_script, "r") as f:
            content = f.read()

        # Replace template variables with custom values
        custom_content = content.replace(
            '"${LOGO}"',
            f'"custom_logo.png"' if self.custom_assets["logo_path"] else '"logo.png"',
        )
        custom_content = custom_content.replace(
            '"${SIGNATURE}"',
            (
                f'"custom_signature.png"'
                if self.custom_assets["signature_path"]
                else '"signature.png"'
            ),
        )

        # Replace contact information
        custom_content = custom_content.replace(
            "records@test-immunization.ca", self.custom_assets["contact_email"]
        )
        custom_content = custom_content.replace(
            "555-555-5555 ext. 1234", self.custom_assets["contact_phone"]
        )
        custom_content = custom_content.replace(
            "Test Health, 123 Placeholder Street, Sample City, ON A1A 1A1",
            self.custom_assets["contact_address"],
        )

        # Replace signature details
        custom_content = custom_content.replace(
            '"Dr. Jane Smith, MPH"', f'"{self.custom_assets["signature_name"]}"'
        )
        custom_content = custom_content.replace(
            '"Associate Medical Officer of Health"',
            f'"{self.custom_assets["signature_title"]}"',
        )
        custom_content = custom_content.replace(
            '"Médecin hygiéniste adjoint"', f'"{self.custom_assets["signature_title"]}"'
        )

        # Write custom script
        with open(custom_script, "w") as f:
            f.write(custom_content)

        # Make executable
        custom_script.chmod(0o755)

        return custom_script

    def _generate_single_custom_template(
        self, json_dir, filename, language, custom_script
    ):
        """Generate a single custom template."""
        try:
            # Check if custom script exists
            if not custom_script.exists():
                st.error(f"Custom template script not found: {custom_script}")
                return None

            # Run custom template generation script
            cmd = [
                str(custom_script),
                str(json_dir.absolute()),
                filename,
                "custom_logo.png" if self.custom_assets["logo_path"] else "logo.png",
                (
                    "custom_signature.png"
                    if self.custom_assets["signature_path"]
                    else "signature.png"
                ),
                "parameters.yaml",
            ]

            # Debug information
            st.info(f"Running command: {' '.join(cmd)}")
            st.info(f"Working directory: {self.templates_dir}")

            result = subprocess.run(
                cmd,
                cwd=str(self.templates_dir),
                capture_output=True,
                text=True,
                check=True,
            )

            # Check if template was generated
            template_file = json_dir / f"{filename}_immunization_notice.typ"
            if template_file.exists():
                return template_file
            else:
                st.error(f"Template file not created: {template_file}")
                return None

        except subprocess.CalledProcessError as e:
            st.error(f"Template generation failed for {filename}: {e}")
            st.error(f"STDOUT: {e.stdout}")
            st.error(f"STDERR: {e.stderr}")
            return None
        except Exception as e:
            st.error(f"Unexpected error generating template for {filename}: {e}")
            return None


def display_file_upload():
    """Display file upload section."""
    st.header("📁 Upload Data File")

    uploaded_file = st.file_uploader(
        "Choose an Excel or CSV file",
        type=["xlsx", "csv"],
        help="Upload your immunization data file. Supported formats: Excel (.xlsx) and CSV (.csv)",
    )

    if uploaded_file is not None:
        # Display file info
        st.success(f"✅ File uploaded: {uploaded_file.name}")
        st.info(f"📊 File size: {uploaded_file.size:,} bytes")

        # Preview data
        try:
            if uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)

            st.subheader("📋 Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            st.info(f"📈 Total records: {len(df):,}")
            st.info(f"📋 Columns: {', '.join(df.columns.tolist())}")

        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")
            return None

    return uploaded_file


def display_processing_options():
    """Display processing options."""
    st.header("⚡ Processing Options")

    col1, col2 = st.columns(2)

    with col1:
        preprocess_only = st.checkbox(
            "Preprocess Only",
            value=False,
            help="Only run data preprocessing without generating PDFs",
        )

    with col2:
        cleanup_temp = st.checkbox(
            "Cleanup Temporary Files",
            value=True,
            help="Remove temporary files after processing",
        )

    return {"preprocess_only": preprocess_only, "cleanup_temp": cleanup_temp}


def run_processing(uploaded_file, config_options, processing_options, branding_options):
    """Run the immunization charts processing pipeline."""
    if uploaded_file is None:
        st.error("❌ Please upload a file first")
        return None

    # Create temporary file
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}"
    ) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name

    try:
        # Create custom config with user settings
        user_config = {
            "batch_size": config_options["batch_size"],
            "delivery_date": config_options["delivery_date"],
            "data_date": config_options["data_date"],
        }

        # Create pipeline instance with custom config
        web_config = WebConfig(config, user_config)
        pipeline = ImmunizationPipeline(web_config)

        # Handle custom branding assets
        custom_assets = handle_custom_assets(
            branding_options, config_options["output_dir"]
        )

        # Create progress container
        progress_container = st.container()
        status_container = st.container()

        with progress_container:
            st.subheader("🔄 Processing Status")
            progress_bar = st.progress(0)
            status_text = st.empty()

        # Run processing
        start_time = time.time()

        if processing_options["preprocess_only"]:
            status_text.text("🔄 Running preprocessing...")
            progress_bar.progress(25)

            pipeline.run_preprocessing(
                tmp_file_path, config_options["output_dir"], config_options["language"]
            )

            progress_bar.progress(100)
            status_text.text("✅ Preprocessing completed!")

            result = {
                "success": True,
                "message": "Preprocessing completed successfully",
                "output_dir": config_options["output_dir"],
            }
        else:
            status_text.text("🔄 Running full pipeline with custom branding...")
            progress_bar.progress(10)

            # Run preprocessing
            pipeline.run_preprocessing(
                tmp_file_path, config_options["output_dir"], config_options["language"]
            )
            progress_bar.progress(40)

            # Generate custom templates
            status_text.text("🔄 Generating custom templates...")
            templates = generate_custom_templates(
                config_options["output_dir"], config_options["language"], custom_assets
            )
            progress_bar.progress(70)

            # Compile templates to PDF
            status_text.text("🔄 Compiling PDFs...")
            from immunization_charts.templates.compiler import compile_templates_to_pdf

            pdfs = compile_templates_to_pdf(
                Path(config_options["output_dir"]), config_options["language"]
            )
            progress_bar.progress(90)

            # Quality checks
            status_text.text("🔄 Running quality checks...")
            pipeline._run_quality_checks(
                Path(config_options["output_dir"]), config_options["language"]
            )
            progress_bar.progress(100)

            result = {
                "success": True,
                "timing": pipeline.step_times,
                "output_dir": config_options["output_dir"],
                "language": config_options["language"],
                "templates_generated": len(templates),
                "pdfs_generated": len(pdfs),
            }

            status_text.text("✅ Pipeline completed successfully!")

        # Display results
        with status_container:
            if result["success"]:
                st.success("🎉 Processing completed successfully!")

                # Display timing information
                if "timing" in result:
                    st.subheader("⏱️ Performance Summary")
                    timing_df = pd.DataFrame(
                        [
                            {
                                "Step": step.replace("_", " ").title(),
                                "Duration (s)": f"{duration:.2f}",
                            }
                            for step, duration in result["timing"].items()
                            if step != "total"
                        ]
                    )
                    st.dataframe(timing_df, use_container_width=True)

                    if "total" in result["timing"]:
                        st.info(
                            f"⏱️ Total processing time: {result['timing']['total']:.2f} seconds"
                        )

                # Display output information
                if "pdfs_generated" in result:
                    st.info(f"📄 Generated {result['pdfs_generated']} PDF files")
                if "templates_generated" in result:
                    st.info(
                        f"📝 Generated {result['templates_generated']} template files"
                    )

                # Display output directory contents
                output_path = Path(config_options["output_dir"])
                if output_path.exists():
                    st.subheader("📁 Generated Files")

                    # List files by type
                    json_files = list(output_path.glob("json_*/**/*.json"))
                    pdf_files = list(output_path.glob("json_*/**/*.pdf"))
                    csv_files = list(output_path.glob("**/*.csv"))

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("JSON Files", len(json_files))
                    with col2:
                        st.metric("PDF Files", len(pdf_files))
                    with col3:
                        st.metric("CSV Files", len(csv_files))

                    # Create download links
                    if pdf_files:
                        st.subheader("📥 Download Generated Files")

                        # Create zip file
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(
                            zip_buffer, "w", zipfile.ZIP_DEFLATED
                        ) as zip_file:
                            for file_path in pdf_files:
                                zip_file.write(file_path, file_path.name)

                        zip_buffer.seek(0)

                        st.download_button(
                            label="📦 Download All PDFs (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name=f"immunization_charts_{config_options['language']}_{int(time.time())}.zip",
                            mime="application/zip",
                        )

                        # Individual PDF downloads
                        for pdf_file in pdf_files[:5]:  # Show first 5 PDFs
                            with open(pdf_file, "rb") as f:
                                st.download_button(
                                    label=f"📄 Download {pdf_file.name}",
                                    data=f.read(),
                                    file_name=pdf_file.name,
                                    mime="application/pdf",
                                )

                        if len(pdf_files) > 5:
                            st.info(f"... and {len(pdf_files) - 5} more PDF files")
            else:
                st.error(
                    f"❌ Processing failed: {result.get('error', 'Unknown error')}"
                )

        return result

    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

    finally:
        # Cleanup temporary file
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


def display_help_section():
    """Display help and documentation section."""
    with st.expander("📚 Help & Documentation"):
        st.markdown(
            """
        ### How to Use
        
        1. **Upload Data**: Upload an Excel (.xlsx) or CSV (.csv) file with immunization data
        2. **Customize Branding**: Upload your logo and signature, customize contact information
        3. **Configure Settings**: Adjust language, batch size, and dates in the sidebar
        4. **Choose Processing**: Select whether to run full pipeline or preprocessing only
        5. **Generate Charts**: Click the process button to generate immunization charts
        6. **Download Results**: Download the generated PDF files with your custom branding
        
        ### Required Data Columns
        
        Your input file should contain these columns:
        - **School Name**: Name of the school/daycare
        - **Client ID**: Unique identifier for each client
        - **First Name**: Client's first name
        - **Last Name**: Client's last name
        - **Date of Birth**: Birth date (YYYY-MM-DD format)
        - **Street Address**: Street address
        - **City**: City name
        - **Province/Territory**: Province or territory
        - **Postal Code**: Postal code
        - **Overdue Disease**: Comma-separated list of overdue diseases
        - **Imms Given**: Vaccination history
        
        ### Branding Customization
        
        You can customize the generated PDFs with:
        - **Custom Logo**: Upload your organization's logo (PNG, JPG, SVG)
        - **Custom Signature**: Upload signature image with name and title
        - **Contact Information**: Customize email, phone, and address
        - **Size Controls**: Adjust logo and signature sizes
        - **Multi-language Support**: Different content for English and French
        
        ### Output Files
        
        The system generates:
        - **PDF Reports**: Professional immunization notice letters with your branding
        - **JSON Data**: Structured data for each client
        - **CSV Files**: Client ID lists for tracking
        - **Quality Reports**: Processing statistics and validation
        
        ### Support
        
        For technical support or questions, please refer to the project documentation or create an issue in the repository.
        """
        )


def main():
    """Main Streamlit application."""
    setup_page_config()
    display_header()

    # Display sidebar configuration
    config_options = display_sidebar()

    # Store language in session state for dynamic content
    st.session_state.language = config_options["language"]

    # Display branding customization
    branding_options = display_branding_customization()

    # Display file upload
    uploaded_file = display_file_upload()

    # Display processing options
    processing_options = display_processing_options()

    # Process button
    if st.button(
        "🚀 Generate Immunization Charts", type="primary", use_container_width=True
    ):
        if uploaded_file is not None:
            run_processing(
                uploaded_file, config_options, processing_options, branding_options
            )
        else:
            st.warning("⚠️ Please upload a file first")

    # Display help section
    display_help_section()

    # Display footer
    st.markdown("---")
    st.markdown(
        "🩺 **Immunization Charts Generator** - Professional PDF report generation for healthcare providers"
    )


if __name__ == "__main__":
    main()
