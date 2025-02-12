import getpass

print("Running set_openai_api_key.py")

try:
    openai_api_key = getpass.getpass(prompt="Enter your OpenAI API key:\n")
except Exception as err:
    print(f"Exception occurred getting input: {err=}")
    exit(1)

try:
    with open(".env", "w") as file:
        file.write(f'OPENAI_API_KEY={openai_api_key}')
except Exception as err:
    print(f"Exception occurred while writing API key to file: {err=}")
    exit(1)