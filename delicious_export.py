import json
import datetime

# Define file names
input_file = "delicious_export.2025.09.16_03.32.json"
output_file = "delicious_export.md"

try:
    # Specify the encoding as 'utf-8' for both reading and writing
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    markdown_lines = []
    for item in data:
        title = item.get("title", "No Title")
        url = item.get("url", "#")
        tags = item.get("tags", [])
        description = item.get("description", "")
        tags.append("deliciousexport")
        created = item.get("created", None)

        # Convert timestamp to human-readable date
        try:
            created_date = datetime.datetime.fromtimestamp(int(created)).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            created_date = "Unknown Date"

        # Format tags with double underscores
        formatted_tags = " ".join([f"#{tag.replace(' ', '')}" for tag in tags])

        # Create the markdown line
        markdown_line = f"- [{title}]({url}) ({created_date}) {formatted_tags} {description}"
        markdown_lines.append(markdown_line)

    markdown_content = "\n".join(markdown_lines)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"Successfully converted '{input_file}' to '{output_file}'.")

except FileNotFoundError:
    print(f"Error: The file '{input_file}' was not found. Please ensure the file is in the same directory as the script.")
except json.JSONDecodeError:
    print(f"Error: Could not decode the JSON file '{input_file}'. Please ensure it is a valid JSON file.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")