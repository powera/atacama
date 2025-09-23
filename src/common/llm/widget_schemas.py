from common.llm.types import Schema, SchemaProperty

DUAL_FILE_WIDGET_SCHEMA = Schema(
    "DualFileWidget",
    "A React widget with separate code and data files",
    {
        "code_file": SchemaProperty(
            "object",
            "The main React component file",
            properties={
                "content": SchemaProperty("string", "The React component code"),
                "imports": SchemaProperty("array", "External dependencies used", required=False, items={"type": "string"})
            }
        ),
        "data_file": SchemaProperty(
            "object",
            "The data file containing datasets, constants, or configuration",
            properties={
                "content": SchemaProperty("string", "The data file content (JavaScript export)"),
                "type": SchemaProperty("string", "Type of data file", enum=["javascript", "json"], default="javascript")
            }
        ),
        "description": SchemaProperty("string", "Brief description of what the widget does", required=False),
        "dependencies": SchemaProperty("array", "External dependencies needed", required=False, items={"type": "string"})
    }
)

SINGLE_FILE_WIDGET_SCHEMA = Schema(
    "SingleFileWidget",
    "A React widget in a single file",
    {
        "code": SchemaProperty("string", "The complete React component code"),
        "description": SchemaProperty("string", "Brief description of what the widget does", required=False),
        "dependencies": SchemaProperty("array", "External dependencies needed", required=False, items={"type": "string"})
    }
)

WIDGET_IMPROVEMENT_SCHEMA = Schema(
    "WidgetImprovement",
    "Improved widget with potentially multiple files",
    {
        "main_code": SchemaProperty("string", "The improved main React component code"),
        "data_file": SchemaProperty("string", "The improved data file content", required=False),
        "additional_files": SchemaProperty(
            "object",
            "Other files that were modified",
            required=False,
            additional_properties=True
        ),
        "changes_made": SchemaProperty("string", "Summary of changes made", required=False),
        "files_modified": SchemaProperty(
            "array",
            "List of file types that were modified",
            required=False,
            items={"type": "string", "enum": ["main_code", "data_file", "additional"]}
        )
    }
)