from pydantic import BaseModel
from openai import OpenAI
import argparse
import dotenv
import json
import logging
import os
import pdfplumber
import sqlite3

# Get the OpenAI API key from the .env file.
dotenv.load_dotenv()

# Constants
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_TXT_OUTPUT_PATH = "output/drug_text.txt"
DEFAULT_DRUG_INFO_OUTPUT_PATH = "output/drug_info.json"
DEFAULT_DATABASE_PATH = "output/drug_database.db"
LAST_PARSED_PDF_PATH = "output/last_parsed_pdf_path.txt"
LOG_PATH = "output/process_drug_data.log"
CRITERIA_MINIMUM_WORD_COUNT = 15

logger = logging.getLogger(__name__)
logging.basicConfig(filename=LOG_PATH, encoding="utf-8", level=logging.DEBUG)


# This class will provide the template that tells the AI model what information to look for and how to format it.
class DrugCriteria(BaseModel):
    drug_brand_name: str
    drug_generic_name: str
    initial_criteria_text: str
    continuation_criteria_text: str

    def to_dict(self):
        return {
            "drug_brand_name": self.drug_brand_name,
            "drug_generic_name": self.drug_generic_name,
            "initial_criteria_text": self.initial_criteria_text,
            "continuation_criteria_text": self.continuation_criteria_text
        }


def save_string_to_file(string, path):
    """Save string to a text file at the location given by path.
    :param string: The string to write.
    :param path: The file to write it to.
    """
    try:
        with open(path, "w") as file:
            file.write(string)
    except Exception as err:
        logger.exception(f"Failed to write to {path}")
        raise


def load_string(path):
    """Load a string from a file at the provided path. Logs errors."""
    try:
        with open(path, "r") as file:
            result = file.read()
    except Exception as err:
        logger.exception(f"Failed to read from {path}")
        raise

    return result

def json_dump_to_file(object, path):
    """Dump an object as JSON into a file at the provided path. Logs errors.

    :param object: The object to dump.
    :param path: The path of the file to dump into.
    """
    try:
        with open(path, "w") as file:
            json.dump(object, file)
    except Exception as err:
        logger.exception(f"Failed to dump {object} as json to {path}")
        raise


def load_json(path):
    """Load a JSON object from a file at the provided path. Logs errors."""
    try:
        with open(path, "r") as file:
            result = json.load(file)
    except Exception as err:
        logger.exception(f"Failed to load {path} as json")
        raise

    return result


def count_words(string):
    """Count the words in a string."""
    return len(string.split())


def extract_text_from_pdf(pdf_path):
    """Parse the text of a PDF and return that text as a string.

    :param pdf_path: The path of the PDF to parse.
    :return: The text of the PDF.
    """
    try:
        # Open the PDF
        with pdfplumber.open(pdf_path) as pdf:
            # Convert each page of the PDF to text.
            page_texts = (page.extract_text_simple() for page in pdf.pages)

           # Join the text of each page into a single string.
            text = "\n".join(page_texts)
    except Exception as err:
        logger.exception(f"Failed to parse text from {pdf_path=}")
        raise

    # Save the path of pdf that was most recently parsed.
    # This ensures that we can still propagate the source_url through the pipeline even when the pipeline steps are
    # run separately.
    save_string_to_file(pdf_path, LAST_PARSED_PDF_PATH)

    return text


def summarize_drug_info(drug_text, source_url="Unknown"):
    """Summarize a document describing a drug using an OpenAI API query.

    Specifically, this function identifies the brand and generic names of the drug, the clinical criteria required to
    initially prescribe the drug, and the clinical criteria required to continue prescribing the drug. It returns
    a dict of this information in the following format:
    {
        "drug_brand_name": str,
        "drug_generic_name": str,
        "initial_criteria_text": str,
        "continuation_criteria_text": str,
        "source_url": str
    }

    :param drug_text: A string containing the text of a document describing a drug.
    :param source_url: A string with the path used to access the PDF that drug_text was extracted from.
    :return: A dictionary containing drug information.
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Extract the drug information from the provided document."},
                {"role": "user", "content": drug_text},
            ],
            response_format=DrugCriteria
        )
    except Exception as err:
        # API call failed. Log the error and pass it on.
        logger.exception(f"Failed to get drug info summary from OpenAI.")
        raise

    message = completion.choices[0].message

    if message.refusal:
        # OpenAI refused to answer the API call. Log the problem and raise an exception
        logger.error(f"OpenAI refused to summarize drug info: {message.refusal}")
        raise RuntimeError("OpenAI refused.")
    else:
        drug_info = message.parsed.to_dict()
        drug_info["source_url"] = source_url
        return drug_info


def validate_drug_info(drug_info):
    """Log warnings if there are anomalies in the data. Raise an error if the data is too incomplete to use at all.
    :param drug_info: A dictionary with information about a drug. Expects the same format as the return value of
    summarize_drug_info().
    """
    # Make sure we have at least one name for the drug.
    # It wouldn't do to store drug criteria without knowing what it applies to.
    if not drug_info.get("drug_brand_name") and not drug_info.get("drug_generic_name"):
        error_message = "Cannot add drug info to the database without a brand name or generic name."
        logger.error(error_message)
        raise ValueError(error_message, drug_info)
    # Log a warning if there's no brand name.
    # We don't need both names to work with the data, but we should still log the issue.
    elif not drug_info.get("drug_brand_name"):
        logger.warning("Drug info has no brand name.")
    # Log a warning if there's no generic name.
    elif not drug_info.get("drug_generic_name"):
        logger.warning("Drug info has no generic name.")

    # Log a warning if there's no initial criteria.
    if not drug_info.get("initial_criteria_text"):
        logger.warning("Drug info has no initial criteria.")
    # Log a warning if the initial criteria is present but unexpectedly short.
    elif count_words(drug_info.get("initial_criteria_text")) < CRITERIA_MINIMUM_WORD_COUNT:
        logger.warning("Drug initial criteria has fewer words than expected. It may be invalid.")

    # Log a warning if there's no continuation criteria.
    if not drug_info.get("continuation_criteria_text"):
        logger.warning("Drug info has no continuation criteria.")
    # Log a warning if the continuation criteria is present but unexpectedly short.
    elif count_words(drug_info.get("continuation_criteria_text")) < CRITERIA_MINIMUM_WORD_COUNT:
        logger.warning("Drug continuation criteria has fewer words than expected. It may be invalid.")


def add_drug_info_to_database(drug_info, database_path=DEFAULT_DATABASE_PATH):
    """Insert data about a drug into a table in a database.

    :param drug_info: A dict of the drug information to insert. Expects the same format as the return value of
    summarize_drug_info().
    :param database_path: The database to insert the data into.
    :return:
    """
    # Initialize our database tools. Create the database if it doesn't already exist.
    database_connection = sqlite3.connect(database_path)
    cursor = database_connection.cursor()

    # Create the table if it doesn't already exist.
    cursor.execute("""CREATE TABLE IF NOT EXISTS drug_criteria (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       drug_name TEXT,
       generic_drug_name TEXT,
       criteria_type TEXT CHECK( criteria_type IN ("initial", "continuation") ),
       criteria_text TEXT,
       source_url TEXT
    )""")

    new_rows = []

    # Make a tuple for the initial criteria row if we have data for it.
    if drug_info.get("initial_criteria_text"):
        new_row = ( drug_info.get("drug_brand_name"),
                    drug_info.get("drug_generic_name"),
                    "initial",
                    drug_info.get("initial_criteria_text"),
                    drug_info.get("source_url"))
        new_rows.append(new_row)

    # Make a tuple for the continuation criteria row if we have data for it
    if drug_info.get("continuation_criteria_text"):
        new_row = ( drug_info.get("drug_brand_name"),
                    drug_info.get("drug_generic_name"),
                    "continuation",
                    drug_info.get("continuation_criteria_text"),
                    drug_info.get("source_url"))
        new_rows.append(new_row)

    # Insert the new rows into the table.
    cursor.executemany("INSERT INTO drug_criteria VALUES(NULL, ?, ?, ?, ?, ?)", new_rows)

    # Commit changes and close the connection.
    database_connection.commit()
    database_connection.close()


def extract_drug_criteria_from_pdf_to_database(pdf_path,
                                               text_output_path=DEFAULT_TXT_OUTPUT_PATH,
                                               drug_info_output_path=DEFAULT_DRUG_INFO_OUTPUT_PATH,
                                               database_path=DEFAULT_DATABASE_PATH):
    """Extract information about a drug from a pdf and store information about the drug in a database.

    This function executes a pipeline of information in three main steps.
    1. It parses the text from a PDF document into a string.
    2. It uses AI to isolate the name and usage criteria of the drug described in the document.
    3. It stores the organized data in a SQLite database.

    Intermediate results are saved to paths given by arguments so that, if a later step fails, it can be manually attempted again
    without having to repeat earlier steps.

    :param pdf_path: Location of the PDF file to read from.
    :param text_output_path: File location to save intermediate data to after text extraction. Set to None to skip
        saving this step's output.
    :param drug_info_output_path:  File location to save intermediate data to after organizing drug information. Set to
        None to skip saving this step's output.
    :param database_path: File location of the SQLite database to add drug information to.
    :return:
    """
    # Parse the pdf into raw text.
    text = extract_text_from_pdf(pdf_path)

    # Save intermediate text result.
    try:
        if text_output_path is not None:
            save_string_to_file(text, text_output_path)
    except Exception as err:
        print(f"Saving intermediate text output to {text_output_path} failed.")
        print(f"See {LOG_PATH} for more details.")
        # This part was nonessential, so we can ignore the exception.

    # Collate the relevant drug data
    drug_info = summarize_drug_info(text, pdf_path)

    # Save the intermediate drug info result.
    try:
        if drug_info_output_path is not None:
            json_dump_to_file(drug_info, drug_info_output_path)
    except Exception as err:
        print(f"Saving intermediate drug info output to {drug_info_output_path} failed.")
        print(f"See {LOG_PATH} for more details.")
        # This part was nonessential, so we can ignore the exception.

    validate_drug_info(drug_info)

    add_drug_info_to_database(drug_info, database_path)


def extract_text_from_pdf_as_single_step(input_pdf_path, output_txt_path=DEFAULT_TXT_OUTPUT_PATH):
    text = extract_text_from_pdf(input_pdf_path)
    save_string_to_file(text, output_txt_path)


def summarize_drug_info_as_single_step(input_txt_path=DEFAULT_TXT_OUTPUT_PATH, drug_info_output_path=DEFAULT_DRUG_INFO_OUTPUT_PATH):
    text = load_string(input_txt_path)
    text_source = load_string(LAST_PARSED_PDF_PATH)
    drug_info = summarize_drug_info(text, text_source)
    json_dump_to_file(drug_info, drug_info_output_path)


def add_drug_info_to_database_as_single_step(input_drug_info_path=DEFAULT_DRUG_INFO_OUTPUT_PATH, output_database_path=DEFAULT_DATABASE_PATH):
    drug_info = load_json(input_drug_info_path)
    validate_drug_info(drug_info)
    add_drug_info_to_database(drug_info, output_database_path)


# This section determines how this file will behave when invoked as a script.
if __name__ == "__main__":
    # This string will display when the script is run with a --help command arg.
    description = """This script executes a pipeline that reads drug information from a PDF and inserts it into a
    database. This pipeline has multiple steps, and this script can be used to run them all together or run each step
    separately.
    """
    # Create argument parser
    parser = argparse.ArgumentParser(description=description)

    # Add arguments
    parser.add_argument("path", nargs="?", type=str, default=None, help="Path of input file.")  # Positional argument
    parser.add_argument("--step", choices=["parse-text", "summarize-info", "populate-database"], type=str,
                        help="Execute a single step of the pipeline.")  # Optional argument

    # Parse arguments
    args = parser.parse_args()

    if not args.step:
        # Without a step specified, default behavior is to run the full pipeline.
        if not args.path:
            error_message = "To run the full pipeline, you must specify a PDF path to start from."
            logger.error(error_message)
            print(error_message)
            exit(1)
        else:
            # Run the full pipeline.
            extract_drug_criteria_from_pdf_to_database(args.path)

    else:
        # The user specified a step through the command line. Identify which step.
        if args.step == "parse-text":
            if not args.path:
                error_message = "To run the text-parsing step, you must provide the path of a PDF to parse."
                logger.error(error_message)
                print(error_message)
                exit(1)
            else:
                extract_text_from_pdf_as_single_step(args.path)

        elif args.step == "summarize-info":
            if not args.path:
                message = "No filepath was provided. Script will proceed using default path."
                logger.info(message)
                print(message)
                path = DEFAULT_TXT_OUTPUT_PATH
            else:
                path = args.path

            #
            summarize_drug_info_as_single_step(path)

        elif args.step == "populate-database":
            if not args.path:
                message = "No filepath was provided. Script will proceed using default path."
                logger.info(message)
                print(message)
                path = DEFAULT_DRUG_INFO_OUTPUT_PATH
            else:
                path = args.path

            add_drug_info_to_database_as_single_step(path)
