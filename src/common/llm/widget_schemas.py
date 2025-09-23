
from common.llm.types import Schema, SchemaProperty

# Schema for dual-file widget generation
DUAL_FILE_WIDGET_SCHEMA = Schema(
    "DualFileWidget",
    "A React widget with separate code and data files",
    {
        "code_file": SchemaProperty(
            "object",
            "The main React component code file",
            object_schema=Schema(
                "CodeFile",
                "React component code",
                {
                    "filename": SchemaProperty("string", "Name of the code file (e.g., 'MathQuiz.jsx')"),
                    "content": SchemaProperty("string", "Complete React component code"),
                    "imports": SchemaProperty("array", "External dependencies needed", required=False,
                                            items={"type": "string"}),
                    "description": SchemaProperty("string", "Brief description of the component", required=False)
                }
            )
        ),
        "data_file": SchemaProperty(
            "object", 
            "The data file containing app-specific data",
            object_schema=Schema(
                "DataFile",
                "Data file for the widget",
                {
                    "filename": SchemaProperty("string", "Name of the data file (e.g., 'greWords.js', 'lithuanianWords.js')"),
                    "content": SchemaProperty("string", "Data file content (JavaScript module export)"),
                    "format": SchemaProperty("string", "Data format type", enum=["json", "javascript", "csv"]),
                    "description": SchemaProperty("string", "Description of the data structure", required=False)
                }
            )
        ),
        "widget_title": SchemaProperty("string", "Title for the widget"),
        "widget_description": SchemaProperty("string", "Description of what the widget does"),
        "integration_notes": SchemaProperty("string", "Notes on how the code and data files work together", required=False)
    }
)

# Schema for single-file widget generation (backward compatibility)
SINGLE_FILE_WIDGET_SCHEMA = Schema(
    "SingleFileWidget", 
    "A React widget with all code in one file",
    {
        "code": SchemaProperty("string", "Complete React component code"),
        "title": SchemaProperty("string", "Widget title"),
        "description": SchemaProperty("string", "Widget description"),
        "dependencies": SchemaProperty("array", "External dependencies needed", required=False,
                                     items={"type": "string"})
    }
)
