"""

A set of functions useful for building code - not to be included in release builds

- generate_requirements
- extract_todos

"""

import subprocess

import os

def generate_requirements():
    try:
        subprocess.run(['pipreqs', '.', '--force'], check=True)
        print("Requirements file generated successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error generating requirements file: {e}")


def extract_todos(directory, todo_file='todo.txt'):
    """
    Extracts comments containing 'TODO' or 'todo' from Python files in the given directory
    and writes them into a todo file with the format:
    file_name:line_number: comment

    :param directory: Directory to scan for Python files
    :param todo_file: The name of the file to store TODOs (default is 'todo.txt')
    """
    with open(todo_file, 'w') as todo_output:
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):  # Check if it's a Python file
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r') as f:
                            for lineno, line in enumerate(f, start=1):
                                if 'TODO' in line or 'todo' in line:
                                    # Write the filename, line number, and comment to the todo file
                                    todo_output.write(f"{file_path}:{lineno}: {line.strip()}\n")
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")

    print(f"TODOs have been extracted to {todo_file}.")
