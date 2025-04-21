#!/bin/bash

# Run this script from the project root directory (containing api/ and deployment/)

# Directory containing Lambda handlers and the shared folder
API_DIR="api"
# Directory containing the shared code
SHARED_DIR="shared"
# Temporary directory for staging zip contents
TEMP_DIR="deployment_temp"

# Check if api directory exists
if [ ! -d "$API_DIR" ]; then
  echo "Error: API directory '$API_DIR' not found. Run script from project root."
  exit 1
fi

# Loop through each Python file directly in the api/ directory
# Exclude __init__.py if you have one
for f in "$API_DIR"/*.py; do
  if [ -f "$f" ]; then
    # Extract original filename without extension (e.g., create_game)
    filename=$(basename "$f" .py)

    # --- Prepare temporary staging directory ---
    echo "--- Processing $filename ---"
    rm -rf "$TEMP_DIR" # Clean up previous temp dir
    mkdir "$TEMP_DIR"

    # Copy the specific handler file and RENAME it to lambda_function.py
    cp "$f" "$TEMP_DIR/lambda_function.py"
    echo "Copied handler: $f -> $TEMP_DIR/lambda_function.py"

    # Copy the entire 'shared' directory to the root of temp dir
    if [ -d "$API_DIR/$SHARED_DIR" ]; then
      cp -r "$API_DIR/$SHARED_DIR" "$TEMP_DIR/"
      echo "Copied shared directory: $API_DIR/$SHARED_DIR -> $TEMP_DIR/$SHARED_DIR"
    else
      echo "Warning: Shared directory '$API_DIR/$SHARED_DIR' not found."
    fi

    # --- Create the deployment zip ---
    # Important: Change directory to the temp dir to zip contents correctly
    (
      cd "$TEMP_DIR" || exit 1 # Enter temp dir or exit if failed
      # Zip file goes to parent dir (project root)
      zip_file="../deployment_${filename}.zip"
      echo "Creating zip file: $zip_file"
      # Zip the *contents* of the current directory (TEMP_DIR)
      zip -r "$zip_file" . -x ".DS_Store" "*__pycache__*"
      if [ $? -ne 0 ]; then
        echo "Error: Failed to create zip file for $filename"
        # Exit the subshell on zip failure
        exit 1
      fi
    )
    # Capture the exit status of the subshell (which includes the zip command)
    subshell_exit_status=$?

    # Check if the subshell (including zip) failed
    if [ $subshell_exit_status -ne 0 ]; then
        echo "Error: Subshell failed during zip creation for $filename. Skipping update."
        # Clean up temp dir and continue to next file
        rm -rf "$TEMP_DIR"
        continue
    fi

    # --- Check if zip file exists ---
    if [ ! -f "deployment_${filename}.zip" ]; then
        echo "Error: Zip file deployment_${filename}.zip was not found after creation."
        rm -rf "$TEMP_DIR" # Clean up temp dir
        continue # Skip to next function
    fi

    # --- Update Lambda Function ---
    # Convert filename underscores to dashes for the AWS function name
    aws_function_name="${filename//_/-}"
    echo "Updating function: blef-$aws_function_name" # Include the 'blef-' prefix here
    aws lambda update-function-code --function-name "blef-$aws_function_name" --zip-file "fileb://deployment_${filename}.zip"

    if [ $? -eq 0 ]; then
        echo "Successfully updated blef-$aws_function_name."
    else
        echo "Error: Failed to update blef-$aws_function_name."
        # Consider adding retry logic or specific error handling
    fi

    # --- Clean up individual zip file ---
    rm "deployment_${filename}.zip"
    echo "Removed temporary zip file deployment_${filename}.zip."
    echo "-----------------------------"

  fi
done

# Clean up temp directory
rm -rf "$TEMP_DIR"
echo "Deployment process finished. Temporary directory removed."