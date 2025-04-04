# LLM-Driven Web Form Filling Agent

This project implements a web agent capable of navigating to a specified URL and automatically filling out a form with provided data. The agent uses an LLM to analyze the form structure and intelligently map the provided data to appropriate form fields.

## Features

- Navigates to a specified URL
- Analyzes form structure using Selenium
- Uses OpenAI's GPT-4 to create a mapping strategy for data fields to form elements
- Intelligently fills form fields with provided data
- Performs a pre-submission check to ensure form data is correct
- Takes a screenshot of the submission result

## Requirements

- Python 3.8+
- Selenium WebDriver
- Chrome or ChromeDriver
- OpenAI API key

## Installation

1. Clone this repository:
```
git clone https://github.com/yourusername/llm-web-form-agent.git
cd llm-web-form-agent
```

2. Install the required dependencies:
```
pip install -r requirements.txt
```

3. Set up your OpenAI API key:
```
export OPENAI_API_KEY="your-api-key"
```

## Usage

Run the script with:

```
python form_filling_agent.py --url "https://mendrika-alma.github.io/form-submission/" --data_file "your_data.json"
```

Or use the default mock data:

```
python form_filling_agent.py
```

### Command Line Arguments

- `--url`: URL of the form to fill (default: "https://mendrika-alma.github.io/form-submission/")
- `--data_file`: JSON file containing form data (optional, uses mock data if not provided)
- `--api_key`: OpenAI API key (optional, uses environment variable if not provided)

## How It Works

1. **Form Analysis**: The agent first analyzes the form structure by extracting all form elements and their attributes.

2. **Mapping Strategy**: It then uses an LLM to create a mapping strategy that matches the provided data fields to appropriate form elements.

3. **Form Filling**: The agent fills the form using the mapping strategy, handling different input types appropriately.

4. **Pre-Submission Check**: Before submitting, the agent asks the LLM to review the filled data to ensure completeness and compliance with requirements.

5. **Submission**: Finally, the agent submits the form and takes a screenshot of the result.

## Design Considerations

- **Flexibility**: The agent is designed to be flexible and can handle minor changes in form structure.
- **Safety**: The agent performs a pre-submission check to ensure the form data is correct and doesn't include signing as a representative.
- **Error Handling**: The agent includes error handling to gracefully handle exceptions during the form filling process.

## Future Improvements

- Support for more complex form elements (file uploads, captchas, etc.)
- Better handling of multi-page forms
- Enhanced error recovery mechanisms
- Support for different browsers
