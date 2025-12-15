import json
import os

import yaml

from cuga.backend.llm.utils.helpers import get_caller_directory_path


def get_path_relative_to_dir(file, path):
    current_directory = os.path.dirname(os.path.abspath(file))
    return os.path.join(current_directory, path)


def read_yaml_file(file_path, relative=True):
    if relative:
        source_path = get_caller_directory_path()
        file_path = os.path.join(source_path, file_path)
    with open(file_path, 'r') as file:
        content = file.read()
        # Expand environment variables in the content
        expanded_content = os.path.expandvars(content)
        data = yaml.safe_load(expanded_content)

    return data


def read_json_file(file_path):
    """
    Read and parse a JSON file from the specified path.

    Args:
        file_path (str): Path to the JSON file

    Returns:
        dict: The parsed JSON data
    """
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {file_path}")
    except Exception as e:
        print(f"Error reading file: {e}")
