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

## Usage

