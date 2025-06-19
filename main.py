from google import genai
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Tuple
import pickle
from dotenv import load_dotenv
import os
from pathlib import Path
import uuid

from fasthtml.common import *
from monsterui.all import *
import pyperclip
import pandas as pd

# Load environment variables
load_dotenv()

# Create a client
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

# Define the model you are going to use
model_id = "gemini-2.5-pro-exp-03-25" # Alternatives: "gemini-2.0-flash", "gemini-2.0-flash-lite-preview-02-05"  , "gemini-2.0-pro-exp-02-05", "gemini-2.5-pro-exp-03-25"

# ------------------------------------------------------------------------------------------------
# Define the data models
# ------------------------------------------------------------------------------------------------

class ExtractedData(BaseModel):
    pages: List[int] = Field(description="The pages at which the information was found. Number the pages according to the pdf document (starting at 0), not as shown in the document itself.")
    quality: Literal["high", "medium", "low"] = Field(description="The quality of the extracted data. High means that the data is extracted with high accuracy, medium means that the data is extracted with medium accuracy, and low means that the data is extracted with low accuracy.")

class ValuePoint(BaseModel):
    year: int = Field(description="The year of the data point.")
    value: float = Field(description="The value of the data point.")

class FinancialMetrics(BaseModel):
    year: int = Field(description="The year of the financial data.")
    revenue: Optional[float] = Field(None, description="Revenue for the year.")
    ebitda: Optional[float] = Field(None, description="EBITDA for the year.")
    margin: Optional[float] = Field(None, description="Margin for the year.")
    debt: Optional[float] = Field(None, description="Debt at the year-end.")
    type: Literal["actual", "forecast"] = Field(
        description="Indicates whether this is actual historical data or forecast data."
    )

class FinancialData(ExtractedData):
    data: List[FinancialMetrics] = Field(
        description="Time series of actual and forecast financial data by year.")
    currency: str = Field(
        description="The currency of the financial values. It must be a currency in ISO format (EUR, USD, ...) and can also include m (million) or k (thousands).")

class Financials(BaseModel):
    financial_data: FinancialData

class CompanyName(ExtractedData):
    value: str = Field(description="Name of the company.")

class CompanyDescription(ExtractedData):
    value: str = Field(description="Description of the company.")

class CompanyStrategy(ExtractedData):
    value: str = Field(description="The strategy of the company.")

class CompanyBusinessModel(ExtractedData):
    value: str = Field(description="The business model of the company, or how does the company earn money.")

class CompanyMarket(ExtractedData):
    value: str = Field(description="The market in which the company is active, including a description.")

class CompanyClients(ExtractedData):
    value: str = Field(description="The clients of the company, including a description.")

class CompanyProducts(ExtractedData):
    value: str = Field(description="The products or services the company sells, including a description.")

class Employee(ExtractedData):
    name: str = Field(description="The name of the employee.")
    role: str = Field(description="The role of the employee.")
    description: str = Field(description="The description of the employee (past experience, education, ...).")

class TopManagement(BaseModel):
    employees: List[Employee] = Field(description="The Top management / the executive team / the most important employees of the company.")
    pages: List[int] = Field(description="The pages at which the information was found.")

class CompanyBase(BaseModel):
    name: CompanyName
    description: CompanyDescription
    strategy: CompanyStrategy
    business_model: CompanyBusinessModel
    market: CompanyMarket
    clients: CompanyClients
    products: CompanyProducts
    top_management: TopManagement
    financials: Financials

class Company(CompanyBase):
    id: str = Field(description="The id of the company.")

# ------------------------------------------------------------------------------------------------
# Define Data Extraction mechanism
# ------------------------------------------------------------------------------------------------
prompt = "Extract the structured data from the following pdf file."

@threaded
def extract_company_data(company_id):
    file_path = f"data/pdf/{company_id}.pdf"
    doc = client.files.upload(file=file_path)

    response = client.models.generate_content(model=model_id, contents=[prompt, doc], config={'response_mime_type': 'application/json', 'response_schema': CompanyBase, 'temperature': 0.0})

    # company is an object of type Company
    company_base = response.parsed
    company = Company(id=company_id, **company_base.model_dump())

    # Ensure pkl directory exists
    os.makedirs("data/pkl", exist_ok=True)
    filename_pkl = f"data/pkl/{company_id}.pkl"

    # Save company object
    with open(filename_pkl, "wb") as f:
        pickle.dump(company, f)

    return company_id

@patch
def __ft__(self:Employee):
    employee = (Card(
        Div(
            DivFullySpaced(
                H4(self.name),
                quality_indicator(self)
            ),
            P(self.role, cls='italic')
        ),
        P(self.description)
    , cls='mt-4 rounded-lg'))
    return employee

@patch
def __ft__(self:FinancialData):
    years = sorted(set(item.year for item in self.data))
    return Table(
        Tr(Th("Metric"), *[Th(f"{y}" + ("E" if any(d.type == "forecast" and d.year == y for d in self.data) else "")) for y in years]),
        Tr(Td("Revenue"), *[Td(next((str(d.revenue) for d in self.data if d.year == y and d.revenue is not None), "-")) for y in years]),
        Tr(Td("EBITDA"), *[Td(next((str(d.ebitda) for d in self.data if d.year == y and d.ebitda is not None), "-")) for y in years]),
        Tr(Td("Margin"), *[Td(next((str(d.margin) for d in self.data if d.year == y and d.margin is not None), "-")) for y in years]),
        Tr(Td("Debt"), *[Td(next((str(d.debt) for d in self.data if d.year == y and d.debt is not None), "-")) for y in years]),
        caption=f"All values in {self.currency}"
    )

def quality_indicator(field: ExtractedData):
    """Creates a quality indicator dot with tooltip for any ExtractedData field"""
    return Div(
        cls=f"w-3 h-3 rounded-full {'bg-green-500' if field.quality == 'high' else 'bg-orange-500' if field.quality == 'medium' else 'bg-red-500'}",
        **{"uk-tooltip": "title: AI extraction confidence: " + field.quality + "; pos: top"}
    )

@patch
def __ft__(self:Company):
    title = H2(self.name.value, cls='mt-4')
    company_id = self.id
    main = (
        Card(
            DivFullySpaced(
                DivHStacked(H3("Description"), copy_button(company_id, "description")),
                quality_indicator(self.description)
            ),
            Div(f"{self.description.value} (See pages: {', '.join(map(str, self.description.pages))})")
        , cls='mt-4 rounded-lg'),
        Card(
            DivFullySpaced(
                DivHStacked(H3("Business Model"), copy_button(company_id, "business_model")),
                quality_indicator(self.business_model)
            ),
            Div(self.business_model.value)
        , cls='mt-4 rounded-lg'),
        Card(
            DivFullySpaced(
                DivHStacked(H3("Market"), copy_button(company_id, "market")),
                quality_indicator(self.market)
            ),
            Div(self.market.value)
        , cls='mt-4 rounded-lg'),
        Card(
            DivFullySpaced(
                DivHStacked(H3("Clients"), copy_button(company_id, "clients")),
                quality_indicator(self.clients)
            ),
            Div(self.clients.value)
        , cls='mt-4 rounded-lg'),
        Card(
            DivFullySpaced(
                DivHStacked(H3("Products"), copy_button(company_id, "products")),
                quality_indicator(self.products)
            ),
            Div(self.products.value)
        , cls='mt-4 rounded-lg'),
        Card(H3("Top Management"),
        Grid(*self.top_management.employees, cols_max=3), cls='mt-4 rounded-lg'),
        Card(
            DivFullySpaced(
                DivHStacked(H3("Financial Data"), copy_button(company_id, "financials")),
                quality_indicator(self.financials.financial_data)
            ),
            Div(self.financials.financial_data)
        , cls='mt-4 rounded-lg')
    )
    return Titled(title, main)

# ------------------------------------------------------------------------------------------------
# Define the web application
# ------------------------------------------------------------------------------------------------
hdrs = Theme.blue.headers()
app, rt = fast_app(hdrs=hdrs)

def clickable_logo():
    return A(
        Img(
            src='/assets/images/aipe_logo_white.svg',
            alt='AIPE Logo',
            cls='h-8 w-auto'
        ),
        href='/',
        cls='no-underline'
    )

def get_company_list():
    # Get all pkl files from data/pkl directory
    pkl_dir = Path("data/pkl")
    company_data = []

    # List all pkl files and extract company names
    for pkl_file in pkl_dir.glob("*.pkl"):
        with open(pkl_file, "rb") as f:
            company = pickle.load(f)
            # Create tuple of (name, link) using the company name from the pkl file
            company_data.append((
                company.name.value,  # Company name from the Company class structure
                f"/company/{pkl_file.stem}"  # Link based on filename without extension
            ))
    return company_data

def company(company_id: str):
    """
    Load a company from its pkl file using just the filename (without extension)
    Args:
        company_id (str): Name of the pkl file without extension (e.g., 'company_object_ac')
    Returns:
        Company: The loaded company object
    """
    try:
        with open(f"data/pkl/{company_id}.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        # You might want to handle this error differently depending on your needs
        raise FileNotFoundError(f"Company file {company_id}.pkl not found in data/pkl/")

def company_sidebar():
    companies = get_company_list()

    company_items = [Li(A(name, href=link)) for name, link in companies]

    add_button = Li(
        A(
            DivLAligned(
                UkIcon('circle-plus'),
                P("Add New")
            ),
            href='/company/new',
            cls="hover:text-primary"
        )
    )
    company_items.append(add_button)

    sidebar = Div(
        id="sidebar-nav",
        uk_offcanvas="mode: slide"
    )(
        Div(
            cls="uk-offcanvas-bar mt-16"  # Added margin-top to push it below navbar
        )(
            NavContainer(
                NavHeaderLi(H3("Companies")),
                *company_items,
                cls=NavT.secondary
            )
        )
    )

    return sidebar

def navbar():
    toggle_button = Button(
        UkIcon('menu', height=30, width=30),
        cls=(ButtonT.primary, "uk-light"),
        uk_toggle="target: #sidebar-nav"
    )

    return NavBar(
        #A("Page1", href='/rt1'),
        #A("Page2", href='/rt2'),
        #A("Page3", href='/rt3'),
        brand=DivLAligned(toggle_button, clickable_logo()),
        cls="bg-primary text-white"
    )

def nav():
    return (
        navbar(),
        company_sidebar()
    )

def copy_button(company_id: str, field_name: str):
    return Button(UkIcon('copy', height=15, width=15), id=f"copy-button-{field_name}", cls="uk-btn-ghost p-2 rounded-lg", hx_get=f"/copy/{company_id}/{field_name}", hx_target=f"#copy-button-{field_name}", hx_swap="innerHTML")

def upload():
    return Div(
        Form(
            UploadZone(
                DivCentered(Span("Upload Zone"), UkIcon("upload")),
                accept=".pdf",
                name="pdf-file",
                id="upload-zone",
                hx_post="/upload-file",
                hx_target="#file-status",
                hx_trigger="change"
            ),
            method="POST",
            enctype="multipart/form-data",  # Critical for file uploads
            hx_encoding="multipart/form-data",  # HTMX-specific encoding
            id="upload-form"
        ),
        # Status area to show selected file
        Div(
            P("No file selected", cls=TextT.muted),
            id="file-status"
        ),
        # The DivCentered stays in the initial render
        DivCentered(
            Button(
                "Start extraction",
                type="submit",
                id="extraction-button",  # The button ID is what matters for OOB
                cls=ButtonT.primary,
                disabled=True
            ),
            cls="mt-4"
        )
    , cls="mt-4")

@rt("/upload-file", methods=["POST"])
async def handle_file_select(request):
    form = await request.form()
    file = form.get('pdf-file')

    if not file or not getattr(file, 'filename', None):
        return Div(
            P("No file selected", cls=TextT.muted),
            id="file-status"
        )

    # Save the uploaded file
    file_content = file.file.read()  # Get the file content
    temp_path = f"data/temp/{file.filename}"  # Create a temporary path

    # Ensure the temp directory exists
    os.makedirs("data/temp", exist_ok=True)

    # Save the file
    with open(temp_path, "wb") as f:
        f.write(file_content)

    return (
        Div(
            P(f"Selected file: {file.filename}", cls=TextT.success),
            id="file-status"
        ),
        # Just return the button - it will replace the existing button with same ID
        Button(
            "Start extraction",
            id="extraction-button",
            cls=ButtonT.primary,
            disabled=False,
            hx_post=f"/extract?filename={file.filename}",  # Your future endpoint
            hx_target="#file-status",  # Where to show extraction progress/results
            hx_swap_oob="true"
        )
    )

@rt("/extract", methods=["POST"])
async def handle_extraction(request):
    filename = request.query_params.get('filename')  # Get filename from query params
    print(f"Debug: Received filename: {filename}")  # Add debug print

    if not filename:
        return Div(
            P("Error: No file specified", cls=TextT.error),
            id="file-status"
        )

    file_path = f"data/temp/{filename}"
    if not os.path.exists(file_path):
        return Div(
            P("Error: File not found", cls=TextT.error),
            id="file-status"
        )

    # Generate a random company_id (=filename)
    company_id = f"{uuid.uuid4()}".replace("-", "")
    filename_pdf = f"data/pdf/{company_id}.pdf"

    # Save pdf file
    os.makedirs("data/pdf", exist_ok=True)
    os.rename(file_path, filename_pdf)  # Simple file move

    extract_company_data(company_id)

    return extract_company_data_status(company_id)

def extract_company_data_status(company_id):
    if os.path.exists(f"data/pkl/{company_id}.pkl"):
        return Div(
            P(f"Extraction complete", cls=TextT.info),
            id="file-status",
            hx_get=f"/company/{company_id}",
            hx_target="body",
            hx_swap="outerHTML",
            hx_trigger='load'
        )
    else:
        return Div(
            DivLAligned(Loading(size=20), P("Extracting data...", cls=TextT.info)),
            id="file-status",
            hx_get=f"/extract-company-data/{company_id}",
            hx_target="#file-status",
            hx_swap="innerHTML",
            hx_trigger='every 5s'
            )

@rt("/extract-company-data/{company_id}")
def get(company_id: str):
    return extract_company_data_status(company_id)

@rt("/copy/{company_id}/{field_name}")
def get(company_id: str, field_name: str):
    field = getattr(company(company_id), field_name)
    # Special treatment for data (must be pastable into Excel)
    if hasattr(field, 'financial_data'):
        value = format_for_excel_clipboard(field.financial_data.data)
    else:
        value = field.value
    pyperclip.copy(value)
    return UkIcon('check', height=15, width=15, hx_get=f"/restore-icon/{field_name}", hx_target=f"#copy-button-{field_name}", hx_swap="innerHTML", hx_trigger="load delay:1s")

@rt("/restore-icon/{field_name}")
def get(field_name: str):
    return UkIcon('copy', height=15, width=15)

@rt
def index():
    return (
        nav(),
        Container(
            Div(
                H1("DataExtractPro", cls="text-4xl font-bold text-primary text-center"),
                H3("Automated Company Information Extraction", cls="text-xl text-gray-600 text-center mt-2"),
                cls="mt-8 mb-6"
            ),
            Img(
                src='/assets/images/cover_page.jpeg',
                alt='Cover Image',
                cls='w-3/4 mx-auto mt-4 rounded-lg shadow-lg'
            ),
            DivCentered(
                A(
                    Button(
                        DivLAligned(
                            UkIcon('circle-plus'),
                            P("Create New Company")
                        ),
                        cls=ButtonT.primary
                    ),
                    href='/company/new',
                    cls="no-underline mt-8"
                )
            ),
            cls="mx-auto max-w-5xl"
        )
    )

@rt("/company/new")
def new_company():
    return nav(), Container(DivCentered(H3("Data Extraction", cls="mt-4"), P("Upload a pdf file (like an annual report or a CIM) and click on 'Start Extraction' to start the extraction process.", cls="mt-4")), upload(), cls="mx-auto max-w-5xl")

@rt("/company/{company_id}")
def company_page(company_id: str):
    return nav(), Container(company(company_id), cls="mx-auto max-w-5xl")

def format_for_excel_clipboard(metrics_list):
    # Convert list of objects to DataFrame
    df = pd.DataFrame([{
        'year': m.year,
        'revenue': m.revenue,
        'ebitda': m.ebitda,
        'margin': m.margin,
        'debt': m.debt if m.debt is not None else '',
        'type': m.type
    } for m in metrics_list])

    # Use pivot instead of pivot_table to avoid aggregation issues
    # First, set year as the index
    df_indexed = df.set_index('year')

    # Transpose to get years as columns
    df_transposed = df_indexed.transpose()

    # Clean up any NaN values
    df_transposed = df_transposed.fillna('')

    # Convert to tab-separated string
    excel_ready_string = df_transposed.to_csv(sep='\t')

    return excel_ready_string

def main():
    # To start the server (in http://localhost:8001/)
    serve(host='0.0.0.0', port=8001, reload=True)

if __name__ == "__main__":
    main()