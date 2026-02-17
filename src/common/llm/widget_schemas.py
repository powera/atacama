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
                "imports": SchemaProperty(
                    "array", "External dependencies used", required=False, items={"type": "string"}
                ),
            },
        ),
        "data_file": SchemaProperty(
            "object",
            "The data file containing datasets, constants, or configuration",
            properties={
                "content": SchemaProperty("string", "The data file content (JavaScript export)"),
                "type": SchemaProperty(
                    "string", "Type of data file", enum=["javascript", "json"], default="javascript"
                ),
            },
        ),
        "description": SchemaProperty(
            "string", "Brief description of what the widget does", required=False
        ),
        "dependencies": SchemaProperty(
            "array", "External dependencies needed", required=False, items={"type": "string"}
        ),
    },
)

SINGLE_FILE_WIDGET_SCHEMA = Schema(
    "SingleFileWidget",
    "A React widget in a single file",
    {
        "code": SchemaProperty("string", "The complete React component code"),
        "description": SchemaProperty(
            "string", "Brief description of what the widget does", required=False
        ),
        "dependencies": SchemaProperty(
            "array", "External dependencies needed", required=False, items={"type": "string"}
        ),
    },
)


def create_widget_improvement_schema(include_data_file: bool = True) -> Schema:
    """
    Create a dynamic widget improvement schema based on whether data file is expected.

    Args:
        include_data_file: Whether to include data_file in the schema

    Returns:
        Schema object for widget improvement
    """
    properties = {"main_code": SchemaProperty("string", "The improved main React component code")}

    # Only add data_file if it's expected
    if include_data_file:
        properties["data_file"] = SchemaProperty("string", "The improved data file content")

    return Schema(
        "WidgetImprovement", "Improved widget with main code and optionally data file", properties
    )


# Default schema for backward compatibility (includes data_file)
WIDGET_IMPROVEMENT_SCHEMA = create_widget_improvement_schema(include_data_file=True)
