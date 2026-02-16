#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <directory_path> <output_file>"
  exit 1
fi

# Assign arguments to variables
directory_path="$1"
output_file="$2"

# Create CSV file and add the concise header
echo "path_tarred,size_path_tarred_mb,path_tar_file,size_tar_file_mb,first_in_tar,size_match,paths_match" > "$output_file"

# Function to convert bytes to MB (whole numbers)
convert_to_mb() {
  echo $(($1 / (1024 * 1024)))
}

# Loop through directories in the specified path and compare sizes
for dir in "${directory_path}"*/*; do 
  if [ -d "$dir" ]; then
    # Get size of the directory (in bytes)
    folder_size=$(du -sb "$dir" | cut -f1)
    
    # Define the tar file path
    tar_file="${dir}.pod5.tar"
    
    # Get size of the corresponding tar file (in bytes)
    tar_size=$(du -sb "$tar_file" 2>/dev/null | cut -f1)
    
    # Get the first folder in the tar file to confirm contents and trim trailing '/'
    first_in_tar=$(tar -tf "$tar_file" 2>/dev/null | head -n 1 | sed 's:/*$::')
    
    # Trim the trailing '/' from path_tarred and _pod5.tar from the tar file
    base_dir=$(basename "$dir" | sed 's:/*$::')
    tar_base=$(basename "$tar_file" .pod5.tar)

    # Convert sizes from bytes to MB (whole numbers)
    folder_size_mb=$(convert_to_mb "$folder_size")
    tar_size_mb=$(convert_to_mb "$tar_size")

    # Compare sizes (in MB) with a tolerance of 10 MB
    size_diff=$(($folder_size_mb - $tar_size_mb))
    if [ ${size_diff#-} -le 10 ]; then
      size_match="yes"
    else
      size_match="no"
    fi

    # Check if "path_tarred", "path_tar_file", and "first_in_tar" match after trimming
    if [[ "$first_in_tar" == "$base_dir" && "$tar_base" == "$base_dir" ]]; then
      paths_match="yes"
    else
      paths_match="no"
    fi
    
    # Add the information to the CSV
    echo "$dir,$folder_size_mb,$tar_file,$tar_size_mb,$first_in_tar,$size_match,$paths_match" >> "$output_file"
  fi
done

# Print a message when the report is ready
echo "Tar report created: $output_file"