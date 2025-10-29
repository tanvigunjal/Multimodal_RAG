# src/ingestion/prompt.py

def get_image_caption_prompt() -> str:
    """Returns the prompt for generating an image caption."""
    return """
    You are an AI assistant that generates concise and informative summaries of images based on their descriptions. Your task is to create a brief summary that captures the essence of the image in a way that is easy to understand.You are an expert in computer vision and image interpretation. Your task is to generate a precise and informative summary of the visual content in the provided image. The image may represent real-world scenes, model architecture diagrams, data visualizations (e.g., bar charts, line plots, confusion matrices), or other forms of structured or unstructured visual data.
    Your summary should:
    1. Identify key visual elements and their relationships.
    2. Describe the overall context or purpose of the image (e.g., experimental setup, model workflow, or data trend).
    3. Highlight any notable patterns, anomalies, or insights that may be relevant for analysis or model evaluation.

    Maintain technical clarity and avoid unnecessary speculation or artistic interpretation.
     Do not begin your response with phrases like “Here is a summary” or any equivalent.
    Simply output the summary itself.
    """

def get_table_summary_prompt(table_html: str) -> str:
    """
    Returns a prompt for summarizing a table, including the table's HTML.
    
    Args:
        table_html: The HTML representation of the table.
    """
    return f"""
    You are an expert in data analysis and tabular interpretation. Your task is to generate a concise and informative summary of the data presented in the provided table. The table may contain experimental results, performance metrics, benchmark comparisons, statistical data, or any structured dataset.
    Your summary should:
    1. Identify the key variables, metrics, and dimensions represented.
    2. Describe the overall trends, patterns, or relationships within the data.
    3. Highlight any significant observations, outliers, or notable comparisons.
    4. Capture the context or purpose implied by the data (e.g., model evaluation, dataset statistics, or experimental outcomes).
    Respond only with the summary — no additional comments, explanations, or preambles.
    Do not begin your response with phrases like “Here is a summary” or any equivalent.
    Simply output the summary itself.

    Here is the table to summarize:\n\n{table_html}
    """
