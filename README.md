# claimable-test
Project for parsing PDFs with drug information, extracting info with AI, and inserting extracted data into a SQL database. This is my submission for Claimable's technical test.

## Setup

To set up this module, you must have Python and pip installed on your machine. Development and testing was performed with Python version 3.11.9.

1. Clone this repo to an appropriate location on your machine.
2. Open a terminal and change directory to the root of the repo.
3. Create a Python virtual environment with the following command in the terminal.

    ```
    python -m venv ./.venv
    ```

4. Activate the new virtual environment with the following command in the terminal.
    ##### For bash-style terminals
    ```
    source ./.venv/Scripts/activate
    ```
    ##### For Windows-style terminals
    ```
    .\.venv\Scripts\activate.bat
    ```
5. Install needed python packages with the following command in the terminal.
    ```
    pip install -r ./requirements.txt
    ```
6. Configure the repo to use your OpenAI API key by running the following script from the terminal:
    ```
    python set_openai_api_key.py
    ```
    Upon running the script, you should see a prompt to enter your API key. Enter it.

## How It Works

This module executes an information pipeline with multiple steps. Depending on the command arguments you use, you can execute the full pipeline automatically or individual steps manually.

### The Pipeline

The pipeline consists of three steps. 

1. The first step takes a PDF file as its input. It parses the text in the document and outputs the text as a string.

2. The second step takes that string as its input. It makes an OpenAI API query to summarize information about the drug described in the string and saves this information in a structured format. This information includes the drug's brand name, its generic name, its clinical criteria for initial prescription, its clinical criteria for continuing a prescription, and the path of the document the text was originally parsed from. This step outputs all this information in a JSON object.

3. The third step takes that JSON object as its input. It then populates a database with the information.

Regardless of whether these steps are executed together or separately, the intermediate outupts of the pipeline will be saved to files in the output directory. If a later step fails, it can be reattempted without having to repeat earlier successful steps.

## Usage

To execute the entire pipeline with one command, you can run the following command from the repo's root directory:

```
python process_drug_data.py <path-to-your-pdf>
```

To execute just the text-parsing step:

```
python process_drug_data.py --step parse-text <path-to-your-pdf>
```

To execute just the information summarization step:

```
python process_drug_data.py --step summarize-info
```

To execute just the database population step:

```
python process_drug_data.py --step populate-database
```

Note the lack of path specification in the commands for the last two steps. These steps will automatically use the default output locations of prior steps for their input.

