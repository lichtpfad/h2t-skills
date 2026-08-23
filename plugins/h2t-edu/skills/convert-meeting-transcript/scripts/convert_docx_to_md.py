#!/usr/bin/env python3
"""
Convert DOCX transcript to Markdown with speaker name replacements
"""

import argparse
import os
import sys
from pathlib import Path

from docx import Document
from dotenv import load_dotenv

load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)

def parse_speaker_mapping(speaker_args):
    """
    Parse speaker mappings from command-line arguments.
    Expected format: Speaker_00=Name1 Speaker_01=Name2
    """
    mapping = {}
    for arg in speaker_args:
        if '=' in arg:
            old_name, new_name = arg.split('=', 1)
            mapping[old_name.strip()] = new_name.strip()
    return mapping

def convert_docx_to_markdown(input_file, speaker_mapping):
    """
    Convert DOCX file to Markdown with speaker name replacements.

    Args:
        input_file: Path to input DOCX file
        speaker_mapping: Dictionary mapping old speaker names to new names

    Returns:
        Path to output markdown file
    """
    # Read the DOCX file
    print(f"Reading file: {input_file}")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    doc = Document(input_file)

    # Extract all text content
    markdown_content = []

    for paragraph in doc.paragraphs:
        text = paragraph.text

        # Replace speaker names
        for old_name, new_name in speaker_mapping.items():
            text = text.replace(old_name, new_name)

        markdown_content.append(text)

    # Join all paragraphs with newlines
    final_content = '\n'.join(markdown_content)

    # Generate output filename (same base name, .md extension)
    base_name = os.path.splitext(input_file)[0]
    output_file = f"{base_name}.md"

    # Save as markdown file
    print(f"Writing to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print("Successfully converted to markdown!")
    print(f"Output file: {output_file}")

    return output_file

def main():
    parser = argparse.ArgumentParser(
        description='Convert DOCX meeting transcript to Markdown with speaker name replacement',
        epilog='Example: %(prog)s transcript.docx --speakers "Speaker_00=Alice" "Speaker_01=Bob"'
    )

    parser.add_argument(
        'input_file',
        help='Path to input DOCX file'
    )

    parser.add_argument(
        '--speakers',
        nargs='*',
        default=[],
        help='Speaker name mappings in format: Speaker_00=Name1 Speaker_01=Name2'
    )

    args = parser.parse_args()

    # Parse speaker mappings
    speaker_mapping = parse_speaker_mapping(args.speakers)

    if not speaker_mapping:
        print("Warning: No speaker mappings provided. File will be converted without name replacements.")
        print("Provide speaker mappings with: --speakers 'Speaker_00=Name1' 'Speaker_01=Name2'")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Conversion cancelled.")
            sys.exit(0)
    else:
        print(f"Speaker mappings: {speaker_mapping}")

    # Convert the file
    try:
        convert_docx_to_markdown(args.input_file, speaker_mapping)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
