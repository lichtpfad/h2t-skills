---
name: convert-meeting-transcript
description: "Converts DOCX meeting transcripts to Markdown with speaker name replacement. Takes input .docx file, outputs .md alongside it. Triggers: 'convert transcript', 'docx to markdown', 'convert meeting'., 'h2t-edu:convert-meeting-transcript'"
compatibility: "Requires python-docx. Input file path required."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Convert Meeting Transcript Skill

This skill converts DOCX meeting transcripts to Markdown format with automatic speaker name replacement.

## Переменные

```bash
# uv подтягивает зависимости на каждый запуск — устанавливать нечего
RUN="uv run --no-project --with python-docx --with python-dotenv python"

CLI="$RUN ${CLAUDE_SKILL_DIR}/scripts/convert_docx_to_md.py"
```

## Usage

### With speaker mappings:
```bash
$CLI transcript.docx --speakers "Speaker_00=Alice" "Speaker_01=Bob"
```

### Without speaker mappings (conversion without name replacement):
```bash
$CLI transcript.docx
```

## How it works

1. **Parse Arguments**: Accepts a DOCX file path and optional speaker name mappings
2. **Check Speaker Mappings**:
   - If mappings are provided, they are parsed automatically
   - If no mappings are provided, the user is asked whether to continue without replacements
3. **Convert Document**: Reads the DOCX file and converts it to Markdown format
4. **Replace Names**: Replaces speaker identifiers (like Speaker_00, Speaker_01) with actual names
5. **Save Output**: Saves the markdown file with the same base name as the input file

## Speaker Mapping Format

Speaker mappings should be provided in the format: `Speaker_XX=ActualName`

Examples:
- `Speaker_00=Alice`
- `Speaker_01=Bob Smith`
- `Speaker_02=Charlie`

## Output

The converted markdown file will be saved in the same directory as the input DOCX file, with a `.md` extension.

Example:
- Input: `/path/to/meeting_transcript.docx`
- Output: `/path/to/meeting_transcript.md`

## Dependencies

- `python-docx` (pip install python-docx)
- `python-dotenv` (pip install python-dotenv)
